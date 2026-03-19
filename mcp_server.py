# mcp_server.py
import os
import sys
from fastmcp import FastMCP

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入你的工具
from tools.weather_check import weather_check
from tools.web_search import web_search
from tools.knowledge_search import knowledgebas_search
from tools.get_time import get_time
from tools.code_interpreter import code_interpreter

# 创建MCP服务器实例
mcp = FastMCP("My Tools Server")

# ==================== 天气工具 ====================
@mcp.tool(
    name="weather",
    description="查询指定城市的实时天气信息"
)
def get_weather(city: str) -> str:
    """
    查询天气，返回标准化的结果格式
    """
    result = weather_check.run(city)
    
    # # 处理特殊返回码
    # if result == "ERROR:MISSING_CITY":

    #     return "请问您想了解哪个城市的天气？"
    
    return result

# ==================== 网络搜索工具 ====================
@mcp.tool(
    name="web_search",
    description="搜索互联网上的最新资讯、新闻、文章"
)
def search_web(query: str) -> str:
    """
    网络搜索
    
    Args:
        query: 搜索关键词
    
    Returns:
        搜索结果
    """
    return web_search.run(query)

# ==================== 知识库搜索工具 ====================
@mcp.tool(
    name="knowledge_search",
    description="在本地知识库中检索特定主题的内容"
)
def search_knowledgebase(kb_name: str, query: str) -> str:
    """
    知识库搜索
    
    Args:
        kb_name: 知识库名称
        query: 查询问题
    
    Returns:
        检索结果
    """
    # 格式化为工具要求的输入格式
    input_str = f"{kb_name},{query}"
    result = knowledgebas_search.run(input_str)
    
    # # 处理格式错误
    # if "【格式错误】" in result:
    #     return "请输入正确的格式：知识库名称,问题（例如：wukong,孙悟空和唐僧的关系）"
    
    return result

# ==================== 时间工具 ====================
@mcp.tool(
    name="get_time",
    description="获取当前系统时间"
)
def current_time() -> str:
    """
    获取当前时间
    """
    return get_time.run("")  # 传入空字符串

# ==================== 代码解释器工具 ====================
@mcp.tool(
    name="code_interpreter",
    description="执行 Python 代码进行计算、数据分析、图表绘制等"
)
def run_code(code: str) -> str:
    """
    执行Python代码
    
    Args:
        code: 有效的Python代码字符串
    
    Returns:
        代码执行结果
    """
    return code_interpreter.run(code)

# # ==================== 资源（可选） ====================
# # 如果你想把知识库作为资源暴露，可以这样：
# @mcp.resource("kb://{kb_name}/info")
# def get_kb_info(kb_name: str) -> str:
#     """获取知识库的基本信息"""
#     # 这里可以从你的数据库查询知识库信息
#     return f"知识库 '{kb_name}' 的信息"

# # ==================== 提示词（可选） ====================
# @mcp.prompt()
# def search_strategy(topic: str) -> str:
#     """生成搜索策略提示词"""
#     return f"""
# 请帮我搜索关于“{topic}”的信息。你可以：
# 1. 先用网络搜索了解基本情况
# 2. 如果有相关的知识库，再用知识库搜索深入查询
# 3. 如果需要计算或分析数据，使用代码解释器
# """

# ==================== 启动服务器 ====================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="启动MCP服务器")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="传输协议: stdio(默认)或sse"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="SSE模式下的监听地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="SSE模式下的监听端口"
    )
    
    args = parser.parse_args()
    
    if args.transport == "stdio":
        # stdio模式（用于Claude Desktop等本地客户端）
        mcp.run(transport="stdio")
    else:
        # SSE模式（用于远程访问）
        mcp.run(
            transport="sse"
        )