import asyncio
import os
import shutil
import logging
from typing import Any
from mcp import ClientSession, StdioServerParameters
from contextlib import AsyncExitStack
from mcp.client.stdio import stdio_client

class Server:
    """
    服务器类，用于管理与MCP服务器的连接和交互
    包括初始化连接、工具管理、资源访问等功能
    """
    # 1.初始化服务器实例：参数:name (str): 服务器名称；config (dict[str, Any]): 服务器配置信息，包括命令、参数和环境变量
    def __init__(self, name: str, config: dict[str, Any]) -> None:


        self.name: str = name                       # 服务器名称
        self.config: dict[str, Any] = config        # 服务器配置信息
        self.stdio_context: Any | None = None       # stdio上下文（已废弃，保留用于向后兼容）
        self.session: ClientSession | None = None   # MCP客户端会话实例
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()       # 清理操作的异步锁，确保清理操作的原子性
        self.exit_stack: AsyncExitStack = AsyncExitStack()      # 异步上下文管理器堆栈，用于管理资源的生命周期
        self._cleaned_up = False                    # 标记服务器是否已被清理

    # 2.初始化服务器连接    
    async def initialize(self) -> None:
        # shutil.which("npx")在系统的 PATH 环境变量中搜索可执行文件     判断命令是command还是npx
        command = shutil.which("npx") if self.config["command"] == "npx" else self.config["command"]     # 确定要执行的命令，如果配置中指定为"npx"则查找npx命令的路径
        if command is None: raise ValueError("The command must be a valid string and cannot be None.")
        # 配置启动子进程的参数
        server_params = StdioServerParameters(
            command=command,                    # 执行命令
            args=self.config["args"],           # 命令参数
            # 合并环境变量：将系统环境变量和配置中的环境变量合并
            env={**os.environ, **self.config["env"]} if self.config.get("env") else None)

        # ******** 1.建立和服务器的连接**********
        try:                            # 把这个上下文推入栈中（记得不用时需要及时清理）
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            read, write = stdio_transport

            # 创建一个会话上下文管理器，把这个上下文也推入栈中                       注意：此时上下文中有两个栈，一个在底部stdio_client(server_params)，一个在头部ClientSession(read, write)
            session = await self.exit_stack.enter_async_context(ClientSession(read, write)) 
            # MCP 协议的初始化握手，交换版本信息，确认双方能力。
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise
    async def list_tools(self) -> list[Any]:
        """
        列出服务器提供的所有工具
        返回:
            list[Any]: 工具列表
        """
        if not self.session: raise RuntimeError(f"Server {self.name} not initialized")  #检查是否有会话

        tools_response = await self.session.list_tools()            # 从服务器获取工具列表
        tools = []

        for item in tools_response:        # 解析工具响应数据
            if isinstance(item, tuple) and item[0] == "tools":            # 检查响应项是否为包含工具信息的元组
                            # 扩展工具列表，将服务器提供的工具转换为Tool对象
                tools.extend(Tool(tool.name, tool.description, tool.inputSchema, tool.title) for tool in item[1])
        return tools
class Tool:
    """
    工具类，用于表示和管理MCP服务器提供的工具
    包括工具的名称、描述、输入模式等信息
    """
    def __init__(
            self,
            name: str,
            description: str,
            input_schema: dict[str, Any],
            title: str | None = None,
    ) -> None:
        """
        初始化工具实例
        参数:
            name (str): 工具名称
            description (str): 工具描述
            input_schema (dict[str, Any]): 工具输入模式，定义了工具所需的参数
            title (str | None): 工具的用户可读标题（可选）
        """
        self.name: str = name
        self.title: str | None = title
        self.description: str = description
        # 工具输入模式，定义了工具所需的参数及其类型和描述
        self.input_schema: dict[str, Any] = input_schema
    def format_for_llm(self) -> str:
        """
        将工具信息格式化为适合LLM理解的字符串格式
        用于向LLM提供工具的详细信息，包括参数说明
        返回:
            str: 格式化后的工具信息字符串
        """
        # 初始化参数描述列表
        args_desc = []
        # 检查输入模式中是否包含properties字段（参数定义）
        if "properties" in self.input_schema:
            # 遍历所有参数定义
            for param_name, param_info in self.input_schema["properties"].items():
                # 构造参数描述字符串，包括参数名和描述信息
                arg_desc = f"- {param_name}: {param_info.get('description', 'No description')}"
                # 检查该参数是否为必需参数
                if param_name in self.input_schema.get("required", []):
                    # 如果是必需参数，添加(required)标记
                    arg_desc += " (required)"
                # 将参数描述添加到列表中
                args_desc.append(arg_desc)
        # 构造工具基本信息输出字符串
        output = f"Tool: {self.name}\n"
        # 如果有用户可读标题，则添加到输出中
        if self.title:
            output += f"User-readable title: {self.title}\n"
        # 构造完整的工具信息字符串，包括描述和参数列表
        output += f"""  Description: {self.description}
                        Arguments:
                        {chr(10).join(args_desc)}  
                """
        # 返回格式化后的工具信息
        return output

class ChatSession:
    """
    聊天会话类，管理多个MCP服务器和LLM客户端之间的交互
    负责处理用户输入、工具调用、LLM响应等整个聊天流程
    """
    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        """
        初始化聊天会话
        参数:
            servers (list[Server]): 服务器列表，包含所有要连接的MCP服务器
            llm_client (LLMClient): LLM客户端实例，用于与大语言模型交互
        """
        # 保存服务器列表
        self.servers: list[Server] = servers
    async def cleanup_servers(self) -> None:
        """
        清理所有服务器连接
        确保在会话结束时正确关闭所有服务器连接
        """
        # 反向遍历服务器列表进行清理（后进先出的清理顺序）
        for server in reversed(self.servers):
            try:
                # 尝试清理服务器连接
                await server.cleanup()
            except Exception as e:
                # 记录清理过程中出现的警告信息
                logging.warning(f"Warning during final cleanup: {e}")
    def extract_json(self, text: str) -> dict | None:
        """
        从文本中提取JSON对象
        用于解析LLM返回的工具调用指令
        参数:
            text (str): 包含JSON对象的文本
        返回:
            dict | None: 解析出的JSON对象，如果解析失败则返回None
        """
        # 使用栈来跟踪大括号的匹配
        stack = []
        # 记录JSON对象的起始位置
        json_start = None
        # 遍历文本中的每个字符
        for i, c in enumerate(text):
            if c == '{':
                # 遇到左大括号
                if not stack:
                    # 如果栈为空，说明这是JSON对象的开始
                    json_start = i
                # 将左大括号压入栈
                stack.append(c)
            elif c == '}' and stack:
                # 遇到右大括号且栈不为空
                # 弹出栈顶元素（应该是一个左大括号）
                stack.pop()
                # 如果栈为空且已记录起始位置，说明找到了一个完整的JSON对象
                if not stack and json_start is not None:
                    # 提取可能的JSON字符串
                    candidate = text[json_start:i + 1]
                    try:
                        # 尝试解析JSON
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # 解析失败，重置起始位置
                        json_start = None
        # 未找到有效的JSON对象
        return None
class MCPManager:
    """
    MCP管理器，负责管理多个MCP服务器实例
    """
    def __init__(self):
        self.servers: list[Server] = []
        self.tools: list[Tool] = []
        self.initialized = False

    async def add_server(self, name: str, config: dict[str, Any]):
        """
        添加MCP服务器配置
        """
        server = Server(name, config)
        self.servers.append(server)

    async def initialize(self):
        """
        初始化所有MCP服务器连接
        """
        if self.initialized:
            return
            
        for server in self.servers:
            try:
                await server.initialize()
                server_tools = await server.list_tools()
                self.tools.extend(server_tools)
                logging.info(f"Successfully connected to server {server.name}, loaded {len(server_tools)} tools")
            except Exception as e:
                logging.error(f"Failed to initialize server {server.name}: {e}")
                
        self.initialized = True

    async def cleanup_all(self):
        """
        清理所有服务器连接
        """
        for server in self.servers:
            try:
                await server.cleanup()
            except Exception as e:
                logging.error(f"Error cleaning up server {server.name}: {e}")


# 创建全局MCP管理器实例
mcp_manager = MCPManager()