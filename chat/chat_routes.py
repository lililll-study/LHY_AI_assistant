import json
import asyncio
import os
from ast import literal_eval
from fastapi import APIRouter, UploadFile, Form
from fastapi.responses import StreamingResponse
from tools.tools_select import tools  # 自定义工具集（用于AI代理）
from typing import List, AsyncIterable

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from configs.setting_1 import chat_model_name, api_key, base_url, TIME_OUT, TEMP_FILE_STORAGE_DIR
from configs.prompt import PROMPT_TEMPLATES  # 提示词模板配置
from utils.load_docs import get_file_content  # 文档内容加载器
from utils.callback import CustomAsyncIteratorCallbackHandler  # 自定义回调处理器
from utils.history_summarizer import summarizer # 历史摘要
from database_server.kb_add import list_kb_from_db
from database_server.database import session
from tools.code_interpreter import code_interpreter
from openai import PermissionDeniedError, RateLimitError
# 在项目中添加封装好的mcp服务
from chat.mcp_client import mcp_manager
from langchain_mcp_adapters.client import MultiServerMCPClient
# ==================== 1. 路由器初始化 ====================
# 创建APIRouter实例，用于组织聊天相关的路由
# prefix="/chat": 所有路由自动添加/chat前缀
# tags=["Chat 对话"]: 在API文档中分组显示
chat_router = APIRouter(prefix="/chat", tags=["Chat 对话"])
# ==================== 2. 文件处理函数 ====================
def files_rag(files, uuid): #定义文件RAG，用于检索增强
    # 定义存储路径：临时存储目录 + 用户会话ID
    kb_file_storage_path = os.path.join(TEMP_FILE_STORAGE_DIR, uuid)
    result = []
    # 确保存储目录存在
    os.makedirs(kb_file_storage_path, exist_ok=True)

    if files:
        for file in files:
            # 保存文件到指定路径
            file_path = os.path.join(kb_file_storage_path, file.filename)
            #写入内容
            with open(file_path, "wb") as f:
                # 读取上传的文件内容并保存
                f.write(file.file.read())

    # 遍历目录中的所有文件,并读取内容
    for filename in os.listdir(kb_file_storage_path):
        file_path = os.path.join(kb_file_storage_path, filename)
        if os.path.isfile(file_path):
            file_content = get_file_content(file_path)

            # 直接将路径和内容拼接到结果字符串
            # 格式: "document:./path/to/file\ncontent:文件内容\n"
            result.append(f"document:.{file_path}\ncontent:{file_content}\n")

    # 将所有处理结果合并为一个字符串返回
    # "".表示将结果列表合并为一个字符串
    # ",".表示将结果列表合并为一个字符串，并通过逗号分隔
    return "".join(result)

# ==================== 3. AI代理聊天接口 ====================
# 定义一个post方法agent_chat
@chat_router.post("/agent_chat")
async def agent_chat(
        # FastAPI Form参数定义
        files: List[UploadFile] = None,
        query: str = Form(..., description="用户输入"),
        sys_prompt: str = Form("You are a helpful assistant.", description="系统提示"),
        # history_len: int = Form(-1, description="保留历史消息的数量"),
        history: List[str] = Form([], description="历史对话"),
        temperature: float = Form(0.5, description="LLM采样温度"),
        max_tokens: int = Form(1024, description="LLM最大tokens"),
        session_id: str = Form(None, description="会话标识")
):
    # # ============ 调试信息 ============
    # print("\n" + "="*50)
    # print(f"【后端接收】会话ID: {session_id}")
    # print(f"【后端接收】query: {query}")
    # print(f"【后端接收】history_len: {history_len}")
    # print(f"【后端接收】原始history类型: {type(history)}")
    # print(f"【后端接收】原始history长度: {len(history)}")
    # for i, item in enumerate(history):
    #     print(f"【后端接收】history[{i}]类型: {type(item)}, 值预览: {str(item)[:100]}...")
            
    # mcp_tools = await mcp_manager.get_tools() + tools
    mcp_tools = tools
    print(f"🔧 MCP 工具列表: {[tool.name for tool in mcp_tools]}")

    documents = files_rag(files, session_id)    #对上传的文件进行预处理
    # 安全地解析历史对话
    parsed_history = []
    for item in history:
        try:
            # 尝试解析字符串格式的字典
            if isinstance(item, str):
                parsed_item = literal_eval(item)
                if isinstance(parsed_item, dict) and 'role' in parsed_item and 'content' in parsed_item:
                    parsed_history.append(parsed_item)
            elif isinstance(item, dict):
                parsed_history.append(item)
        except Exception as e:
            print(f"⚠️ 解析历史消息失败：{e}, 原始数据：{item}")
            continue
    # #V3.0: 历史摘要功能
    # 替换原有的历史处理部分
    if parsed_history:
        histories, stats = await summarizer.compress(parsed_history, query)
        print(f"📊 历史压缩: {stats}")
    else:
        histories = ""
    # 3.3 定义一个异步生成器函数，用于流式输出AI响应
    async def agent_chat_iterator() -> AsyncIterable[str]:
        """
        异步生成器函数，实现流式AI对话响应
        返回：异步可迭代的字符串（JSON格式的响应块）
        """
        # 3.3.1 初始化回调处理器
        # CustomAsyncIteratorCallbackHandler用于捕获AI输出的token
        # 创建自定义的回调处理器，用于处理LLM的流式输出
        # 使用回调函数的作用：使得用户能够看到回答逐步被获取
        callback = CustomAsyncIteratorCallbackHandler()
        callbacks = [callback]  # 回调列表
        chat_model = ChatOpenAI(
            model = chat_model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            callbacks=callbacks,
            request_timeout=TIME_OUT
        )
        system_prompt = SystemMessagePromptTemplate.from_template(sys_prompt)
        human_prompt = HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATES["agent"])# 从配置加载的agent模板
        chat_prompt = ChatPromptTemplate.from_messages([system_prompt, human_prompt])

        #创建ai代理
        # ReAct(Reasoning and Acting)代理架构,结合LLM和工具使用,           # 停止序列，控制代理停止条件
        # agent = create_react_agent(chat_model, tools, chat_prompt, stop_sequence=['\nObservation:'])
        agent = create_react_agent(
            chat_model,
            mcp_tools,
            chat_prompt,
            # stop_sequence=["\nObservation:", "\n\tObservation:"]
            )
        # 创建代理执行器                                                   # 启用详细日志输出（调试用）
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=mcp_tools, 
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,  # 限制最大迭代次数，防止无限循环
            early_stopping_method='generate'  # 超限时生成最终答案
            )

        # 从数据库获取所有知识库信息
        knowledgebases = list_kb_from_db(session)
        # 整理成字符串，用于提示词上下文
        kbs = "".join([f"{kb['kb_name']} - {kb['kb_info']} \n" for kb in knowledgebases])

        # 重置代码解释器的输出状态
        code_interpreter.output_files, code_interpreter.output_codes = "", ""

        # ============ 6. 异步执行代理任务 ============
        # 创建异步任务，执行代理的推理过程
        task = asyncio.create_task(
            agent_executor.ainvoke(# 异步调用代理,放弃acall使用ainvoke
                {"input": query,  # 用户查询
                "history": histories,  # 历史对话记录
                "knowledgebases": kbs,  # 知识库信息
                "documents": documents  # 上传的文件内容
                })
        )

        # ============ 7. 流式输出生成 ============
        try:
        ## 流式输出
            async for token in callback.aiter():
                # 将每个token包装成JSON响应格式
                response_data = {"answer": token}   # 当前输出的token
                # 将响应数据转换为JSON字符串并编码为字节，然后yield输出
                yield json.dumps(response_data).encode('utf-8')
            # ============ 8. 等待任务完成 ============
            # 等待代理任务完成，设置超时时间防止任务卡住
            await asyncio.wait_for(task, TIME_OUT)

            # ============ 9. 获取代码执行结果 ============
            # 从代码解释器获取执行结果（生成的文件和代码）
            result = task.result()
            print(f"Agent 执行结果：{result}")
            output_files, output_codes = code_interpreter.get_outputs()

            # ============ 10. 发送最终结果 ============
            # 如果有文件输出，发送包含文件引用的最终消息
            # 最后将输出文件列表发送
            if output_files:
                yield json.dumps({"answer": f'\n\n{output_codes}\n\n![](http://localhost:6605{output_files})'}).encode(
                    'utf-8')
        except asyncio.TimeoutError:
            # 处理超时错误
            error_msg = "请求超时，请重试或减少复杂操作。"
            yield json.dumps({"answer": error_msg}).encode('utf-8')
            callback.done.set()
        except PermissionDeniedError as e:
            # 处理 API 权限错误（如频率限制）
            error_msg = f"API 调用受限：{str(e)}\n\n请检查 API 密钥是否有效，或等待后重试。"
            yield json.dumps({"answer": error_msg}).encode('utf-8')
            callback.done.set()
        except RateLimitError as e:
            # 处理速率限制错误
            error_msg = f"请求过于频繁：{str(e)}\n\n请稍后重试。"
            yield json.dumps({"answer": error_msg}).encode('utf-8')
            callback.done.set()
        except Exception as e:
            # 处理其他未知错误
            error_msg = f"发生错误：{str(e)}\n\n请检查输入或联系管理员。"
            yield json.dumps({"answer": error_msg}).encode('utf-8')
            callback.done.set()
            import traceback
            traceback.print_exc()
        finally:
            # 确保回调完成，防止挂起
            if not callback.done.is_set():
                callback.done.set()
            

    # ============ 11. 返回流式响应 ============
    # 创建StreamingResponse，将异步生成器的输出作为流式响应返回
    # 返回 StreamingResponse，以流的形式发送数据
    return StreamingResponse(agent_chat_iterator(), media_type="application/json")
# # 在文件末尾添加生命周期事件
# @chat_router.on_event("startup")
# async def startup_mcp_client():
#     """应用启动时初始化MCP客户端"""
#     await mcp_manager.ensure_initialized()

# @chat_router.on_event("shutdown")
# async def shutdown_mcp_client():
#     """应用关闭时清理MCP客户端"""
#     await mcp_manager.close()
