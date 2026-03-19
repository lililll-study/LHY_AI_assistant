from langchain.tools import BaseTool
from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import Field
import json

class MCPClientManager:
    def __init__(self, server_url: str = "http://127.0.0.1:8000/sse"):
        self.server_url = server_url
        self.session = None
        self.client = None
        self.tools = []
    
    async def initialize(self):
        if self.session:
            return
        try:
            self.client = sse_client(self.server_url)
            read, write = await self.client.__aenter__()
            self.session = await ClientSession(read, write).__aenter__()
            await self.session.initialize()
            
            tools_response = await self.session.list_tools()
            self.tools = []
            for tool in tools_response.tools:
                mcp_tool = MCPServerTool(
                    session=self.session,
                    name=tool.name,
                    description=tool.description
                )
                self.tools.append(mcp_tool)
            print(f"✅ 加载了 {len(self.tools)} 个MCP工具")
            for tool in self.tools:
                print(f"  - {tool.name}")
        except Exception as e:
            print(f"❌ MCP初始化失败: {e}")
    
    async def close(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self.client:
            await self.client.__aexit__(None, None, None)

class MCPServerTool(BaseTool):
    session: ClientSession = Field(description="MCP会话")
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, **kwargs):
        """同步执行（不支持）"""
        raise NotImplementedError("MCPServerTool 不支持同步调用，请使用异步模式")
    
    async def _arun(self, **kwargs):
        """异步执行工具"""
        try:
            print(f"🔧 调用工具: {self.name}, 参数: {kwargs}")
            
            # 处理无参数的情况
            if not kwargs:
                kwargs = {}
            
            # 对于 get_time 工具，确保传递空参数
            if self.name == "get_time":
                kwargs = {}
            
            # 调用MCP工具
            result = await self.session.call_tool(self.name, arguments=kwargs)
            
            # 解析返回结果
            if hasattr(result, 'content') and result.content:
                # 尝试提取文本内容
                for item in result.content:
                    if hasattr(item, 'text'):
                        return str(item.text)
                    elif hasattr(item, 'type') and item.type == 'text':
                        return str(item.text)
                return str(result.content)
            
            return str(result)
            
        except Exception as e:
            print(f"❌ 工具 {self.name} 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return f"工具调用失败: {str(e)}"

mcp_manager = MCPClientManager()