# chat/mcp_client.py
from langchain.tools import BaseTool
from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import Field
import json
import asyncio
from typing import List, Optional

class MCPClientManager:
    def __init__(self, server_url: str = "http://127.0.0.1:8000/sse"):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.client = None
        self.tools: List[BaseTool] = []
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """确保客户端已初始化（幂等操作）"""
        if self._initialized and self.session:
            return
        
        async with self._lock:  # 防止并发初始化
            if self._initialized:  # 双重检查
                return
            
            try:
                print("🚀 初始化全局MCP客户端...")
                self.client = sse_client(self.server_url)
                read, write = await self.client.__aenter__()
                self.session = await ClientSession(read, write).__aenter__()
                await self.session.initialize()
                
                # 获取工具列表并创建LangChain工具
                tools_response = await self.session.list_tools()
                self.tools = []
                for tool in tools_response.tools:
                    mcp_tool = MCPServerTool(
                        session=self.session,
                        name=tool.name,
                        description=tool.description
                    )
                    self.tools.append(mcp_tool)
                
                self._initialized = True
                print(f"✅ 全局MCP客户端初始化成功，加载了 {len(self.tools)} 个工具")
                for tool in self.tools:
                    print(f"  - {tool.name}")
                    
            except Exception as e:
                print(f"❌ MCP初始化失败: {e}")
                # 清理可能的部分初始化资源
                await self._cleanup()
                raise
    
    async def get_tools(self) -> List[BaseTool]:
        """获取工具列表（确保已初始化）"""
        await self.ensure_initialized()
        return self.tools
    
    async def _cleanup(self):
        """内部清理方法"""
        if self.session:
            await self.session.__aexit__(None, None, None)
            self.session = None
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None
        self._initialized = False
    
    async def close(self):
        """关闭客户端连接"""
        await self._cleanup()
        print("🔌 全局MCP客户端已关闭")

class MCPServerTool(BaseTool):
    session: ClientSession = Field(description="MCP会话")
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, **kwargs):
        raise NotImplementedError("MCPServerTool 不支持同步调用，请使用异步模式")
    
    async def _arun(self, **kwargs):
        try:
            print(f"🔧 调用工具: {self.name}, 参数: {kwargs}")
            
            if not kwargs:
                kwargs = {}
            
            if self.name == "get_time":
                kwargs = {}
            
            result = await self.session.call_tool(self.name, arguments=kwargs)
            
            # 提取返回的文本
            response_text = ""
            if hasattr(result, 'content') and result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        response_text = str(item.text)
                        break
                    elif hasattr(item, 'type') and item.type == 'text':
                        response_text = str(item.text)
                        break
            
            if not response_text:
                response_text = str(result)
            
            # ===== 关键修改：统一返回格式 =====
            # 根据工具名称和返回内容，添加适当的标记
            
            # 如果是天气工具且返回错误码
            if self.name == "weather" and "ERROR:MISSING_CITY" in response_text:
                return f"【需要用户输入】请问您想查询哪个城市的天气？"
            
            # 如果是知识库搜索且返回格式错误
            if self.name == "knowledge_search" and "【格式错误】" in response_text:
                return "【需要用户输入】" + response_text
            
            # 如果是正常返回，添加【查询结果】标记
            return f"【查询结果】{response_text}"
            
        except Exception as e:
            print(f"❌ 工具 {self.name} 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return f"【系统错误】工具调用失败: {str(e)}"

# 创建全局单例
mcp_manager = MCPClientManager()