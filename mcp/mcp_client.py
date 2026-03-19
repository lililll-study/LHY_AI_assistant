import asyncio
import json
import os
import shutil
import logging
from contextlib import AsyncExitStack
from typing import Any
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters

from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Configuration:
    def __init__(self) -> None:
        self.load_env()
        self._api_key = os.getenv("API_KEY")
        self._base_url = os.getenv("BASE_URL")
        self._model = os.getenv("MODEL")
    @staticmethod
    def load_env() -> None:
        # 从当前目录的.env文件加载环境变量
        load_dotenv()
    @staticmethod
    def load_config(file_path: str) -> dict[str, Any]:
        with open(file_path, "r") as f:
            return json.load(f)# 将JSON文件内容解析为Python字典并返回

    @property
    def llm_api_key(self) -> str:
        """
                API密钥属性，提供对LLM API密钥的访问
        返回:
                    str: API密钥字符串
        异常
            ValueError: 当API密钥未在环境变量中设置时抛出
        """
        # 检查API密钥是否存在
        if not self.api_key:
            # 如果API密钥不存在，抛出值错误异常
            raise ValueError("LLM_API_KEY not found in environment variables")
        # 返回API密钥
        return self.api_key
    @property
    def base_url(self) -> str:
        """
        基础URL属性，提供对LLM服务基础URL的访问
        返回:
            str: 基础URL字符串
        异常:
            ValueError: 当基础URL未在环境变量中设置时抛出
        """
        # 检查基础URL是否存在
        if not self._base_url:
            # 如果基础URL不存在，抛出值错误异常
            raise ValueError("LLM_BASE_URL not found in environment variables")
        # 返回基础URL
        return self._base_url
    @property
    def model(self) -> str:
        """
        模型名称属性，提供对LLM模型名称的访问
        返回:
            str: 模型名称字符串
        异常:
            ValueError: 当模型名称未在环境变量中设置时抛出
        """
        # 检查模型名称是否存在
        if not self._model:
            # 如果模型名称不存在，抛出值错误异常
            raise ValueError("LLM_MODEL not found in environment variables")
        # 返回模型名称
        return self._model

class Server:
    """
    服务器类，用于管理与MCP服务器的连接和交互
    包括初始化连接、工具管理、资源访问等功能
    """
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        """
        初始化服务器实例
        参数:
            name (str): 服务器名称
            config (dict[str, Any]): 服务器配置信息，包括命令、参数和环境变量
        """
        # 服务器名称
        self.name: str = name
        # 服务器配置信息
        self.config: dict[str, Any] = config
        # stdio上下文（已废弃，保留用于向后兼容）
        self.stdio_context: Any | None = None
        # MCP客户端会话实例
        self.session: ClientSession | None = None
        # 清理操作的异步锁，确保清理操作的原子性
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        # 异步上下文管理器堆栈，用于管理资源的生命周期
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        # 标记服务器是否已被清理
        self._cleaned_up = False
    async def initialize(self) -> None:
        """
        初始化服务器连接
        建立与MCP服务器的连接并初始化会话
        """
        # 确定要执行的命令，如果配置中指定为"npx"则查找npx命令的路径
        command = shutil.which("npx") if self.config["command"] == "npx" else self.config["command"]
        # 检查命令是否有效
        if command is None:
            # 如果命令无效，抛出值错误异常
            raise ValueError("The command must be a valid string and cannot be None.")
        # 创建服务器参数对象
        server_params = StdioServerParameters(
            command=command,                    # 执行命令
            args=self.config["args"],           # 命令参数
            # 合并环境变量：将系统环境变量和配置中的环境变量合并
            env={**os.environ, **self.config["env"]} if self.config.get("env") else None,
        )
        try:
            # 使用stdio_client建立与服务器的连接，并将其添加到上下文管理器堆栈中
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            # 获取读写流
            read, write = stdio_transport
            # 创建客户端会话并将其添加到上下文管理器堆栈中
            session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            # 初始化会话
            await session.initialize()
            # 保存会话实例
            self.session = session
        except Exception as e:
            # 记录初始化错误日志
            logging.error(f"Error initializing server {self.name}: {e}")
            # 执行清理操作
            await self.cleanup()
            # 重新抛出异常
            raise
    async def list_tools(self) -> list[Any]:
        """
        列出服务器提供的所有工具
        返回:
            list[Any]: 工具列表
        """
        # 检查会话是否已初始化
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        # 从服务器获取工具列表
        tools_response = await self.session.list_tools()
        # 初始化工具列表
        tools = []
        # 解析工具响应数据
        for item in tools_response:
            # 检查响应项是否为包含工具信息的元组
            if isinstance(item, tuple) and item[0] == "tools":
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
class LLMClient:
    """
    大语言模型客户端类，用于与LLM API进行交互
    封装了OpenAI API的调用逻辑，提供简单的接口获取模型响应
    """
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        """
        初始化LLM客户端
        参数:
            api_key (str): LLM API密钥，用于身份验证
            base_url (str): LLM服务的基础URL，用于指定API端点
            model (str): 要使用的模型名称
        """
        # 创建OpenAI客户端实例，配置API密钥和基础URL
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        # 保存要使用的模型名称
        self.model = model
    def get_response(self, messages: list[dict[str, str]]) -> str:
        """
        获取LLM的响应
        参数:
            messages (list[dict[str, str]]): 消息历史列表，包含角色和内容
                                       格式: [{"role": "system/user/assistant", "content": "消息内容"}, ...]
        返回:
            str: LLM生成的响应内容，如果发生错误则返回错误信息
        """
        try:
            # 调用OpenAI Chat Completions API获取响应
            response = self.client.chat.completions.create(
                model=self.model,        # 指定要使用的模型
                messages=messages,       # 传递消息历史
                # 可以在这里添加其他参数，如temperature、max_tokens等
            )
            # 返回模型生成的内容（第一个选择项的消息内容）
            return response.choices[0].message.content
        except Exception as e:
            # 记录错误日志
            logging.error(f"Error getting LLM response: {str(e)}")
            # 返回友好的错误信息
            return f"I encountered an error: {str(e)}. Please try again."
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
        # 保存LLM客户端实例
        self.llm_client: LLMClient = llm_client
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
    async def process_llm_response(self, llm_response: str) -> str:
        """
        处理LLM的响应，包括工具调用的解析和执行
        参数:
            llm_response (str): LLM生成的响应文本
        返回:
            str: 处理后的响应，可能是工具执行结果或原始LLM响应
        """
        try:
            # 从LLM响应中提取JSON对象（工具调用指令）
            tool_call = self.extract_json(llm_response)
            # 检查是否包含有效的工具调用
            if tool_call and "tool" in tool_call and "arguments" in tool_call:
                # 记录工具调用信息
                logging.info(f"Executing tool: {tool_call['tool']}")
                logging.info(f"With arguments: {tool_call['arguments']}")
                # 在所有服务器中查找并执行指定的工具
                for server in self.servers:
                    # 获取服务器上的工具列表
                    tools = await server.list_tools()
                    # 检查当前服务器是否提供指定的工具
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            # 执行工具调用
                            result = await server.execute_tool(tool_call["tool"], tool_call["arguments"])
                            # 检查是否有进度信息并记录
                            if isinstance(result, dict) and "progress" in result:
                                progress = result["progress"]
                                total = result["total"]
                                percentage = (progress / total) * 100
                                logging.info(f"Progress: {progress}/{total} ({percentage:.1f}%)")
                            # 返回工具执行结果
                            return f"Tool execution result: {result}"
                        except Exception as e:
                            # 记录工具执行错误
                            error_msg = f"Error executing tool: {str(e)}"
                            logging.error(error_msg)
                            return error_msg
                # 如果没有找到提供该工具的服务器
                return f"No server found with tool: {tool_call['tool']}"
            # 如果没有工具调用，返回原始LLM响应
            return llm_response
        except json.JSONDecodeError:
            # JSON解析失败，返回原始LLM响应
            return llm_response
    async def print_servers_overview(self) -> None:
        """
        打印所有服务器的概览信息
        包括每个服务器提供的工具、资源和提示词
        """
        # 遍历所有服务器
        for server in self.servers:
            # 打印服务器名称
            print(f"\n===== Server: {server.name} =====")
            try:
                # 如果服务器会话未初始化，则先初始化
                if not server.session:
                    await server.initialize()
                # 获取并打印服务器提供的工具列表
                tools = await server.list_tools()
                print("Tools:")
                for tool in tools:
                    print(f" - {tool.name}: {tool.description}")
                # 尝试获取并打印服务器提供的资源列表
                try:
                    resources = await server.list_resources()
                    if resources:
                        print("Resources:")
                        for r in resources:
                            print(f" - {r}")
                    else:
                        print("Resources: None")
                except Exception:
                    print("Resources: Not supported")
                # 尝试获取并打印服务器提供的提示词列表
                try:
                    prompts = await server.list_prompts()
                    if prompts:
                        print("Prompts:")
                        for p in prompts:
                            print(f" - {p}")
                    else:
                        print("Prompts: None")
                except Exception:
                    print("Prompts: Not supported")
            except Exception as e:
                # 打印服务器信息获取过程中的错误
                print(f"Error retrieving info from server {server.name}: {e}")
    async def start(self) -> None:
        """
        启动聊天会话主循环
        处理用户输入、LLM交互和工具调用的完整流程
        """
        try:
            # 初始化所有服务器连接
            for server in self.servers:
                try:
                    # 尝试初始化服务器
                    await server.initialize()
                except Exception as e:
                    # 记录初始化错误并清理所有服务器
                    logging.error(f"Failed to initialize server: {e}")
                    await self.cleanup_servers()
                    return
            # 收集所有服务器提供的工具
            all_tools = []
            for server in self.servers:
                # 获取服务器上的工具列表
                tools = await server.list_tools()
                # 将工具添加到总工具列表中
                all_tools.extend(tools)
            # 格式化所有工具的描述信息
            tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
            # 构造系统消息，告知LLM可用的工具
            system_message = (
                "You are a helpful assistant with access to these tools:\n\n"
                f"{tools_description}\n"
                "Choose the appropriate tool based on the user's question. "
                "If no tool is needed, reply directly.\n\n"
                "IMPORTANT: When you need to use a tool, you must ONLY respond with "
                "the exact JSON object format below, nothing else:\n"
                "{\n"
                '    "tool": "tool-name",\n'
                '    "arguments": {\n'
                '        "argument-name": "value"\n'
                "    }\n"
                "}\n\n"
                "After receiving a tool's response:\n"
                "1. Transform the raw data into a natural, conversational response\n"
                "2. Keep responses concise but informative\n"
                "3. Focus on the most relevant information\n"
                "4. Use appropriate context from the user's question\n"
                "5. Avoid simply repeating the raw data\n\n"
                "Please use only the tools that are explicitly defined above."
            )
            # 初始化消息历史，包含系统消息
            messages = [{"role": "system", "content": system_message}]
            # 主聊天循环
            while True:
                try:
                    # 获取用户输入
                    user_input = input("You: ").strip().lower()
                    # 检查是否需要退出
                    if user_input in ["quit", "exit"]:
                        logging.info("\nExiting...")
                        break
                    # 将用户输入添加到消息历史中
                    messages.append({"role": "user", "content": user_input})
                    # LLM响应处理循环
                    while True:
                        # 获取LLM的响应
                        llm_response = self.llm_client.get_response(messages)
                        # 处理LLM响应（包括可能的工具调用）
                        processed_response = await self.process_llm_response(llm_response)
                        # 检查是否为工具执行结果
                        if processed_response == llm_response or not processed_response.startswith(
                                "Tool execution result:"):
                            # 如果不是工具执行结果，直接输出并结束本轮对话
                            print(f"Assistant: {processed_response}")
                            messages.append({"role": "assistant", "content": processed_response})
                            break
                        else:
                            # 如果是工具执行结果，将其作为系统消息添加到历史中，继续下一轮处理
                            messages.append({"role": "assistant", "content": llm_response})
                            messages.append({"role": "system", "content": processed_response})
                            # 继续循环以处理工具执行结果
                            continue
                except KeyboardInterrupt:
                    # 处理用户中断（Ctrl+C）
                    logging.info("\nExiting...")
                    break
        finally:
            # 确保在任何情况下都清理服务器连接
            await self.cleanup_servers()
async def main() -> None:
    """
    主函数，程序的入口点
    负责初始化配置、创建服务器和LLM客户端、启动聊天会话
        """
    # 创建配置管理器实例，加载环境变量
    config = Configuration()
    # 从servers_config.json文件中加载服务器配置
    server_config = config.load_config("servers_config.json")
    # 根据配置创建服务器实例列表
    # 遍历配置中的所有MCP服务器，为每个服务器创建一个Server对象
    servers = [Server(name, srv_config) for name, srv_config in 
    server_config["mcpServers"].items()]
    # 创建LLM客户端实例，使用配置中的API密钥、基础URL和模型名称
    llm_client = LLMClient(api_key=config._api_key, base_url=config._base_url, 
    model=config._model)
    # 创建聊天会话实例，传入服务器列表和LLM客户端
    chat_session = ChatSession(servers, llm_client)
    try:
        # 打印所有服务器的概览信息（工具、资源、提示词等）
        await chat_session.print_servers_overview()
        # 启动聊天会话主循环
        await chat_session.start()
    finally:
        # 确保在程序退出前清理所有服务器连接
        await chat_session.cleanup_servers()
if __name__ == "__main__":
    """
    程序执行入口
    当脚本直接运行时执行main函数
        """
    # 运行异步主函数
    asyncio.run(main())