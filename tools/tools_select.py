from langchain_core.tools import Tool, StructuredTool
from tools.code_interpreter import code_interpreter
from tools.weather_check import weather_check
from tools.web_search import web_search
from tools.knowledge_search import knowledgebas_search
from tools.get_time import get_time

# 将API工具封装成Langchain的Tool对象
tools = [
    Tool(
        name="weather check",
        func=weather_check.run,
        description="查询指定城市的实时天气信息。输入必须是具体城市名（如'北京'、'上海'）。如果返回'ERROR:MISSING_CITY'，直接向用户询问'请问您想了解哪个城市的天气？'。ONLY use this tool for current weather queries."
    ),
    
    Tool(
        name="web search",
        func=web_search.run,
        description="搜索互联网上的最新资讯、新闻、文章。适用于查找事件信息、人物资料、产品评测等通用搜索需求。输入是搜索关键词。Do NOT use for weather or time queries."
    ),

    Tool(
        name="knowledge search",
        func=knowledgebas_search.run,
        description="在本地知识库中检索特定主题的内容。输入格式：'知识库名称，查询问题'（例如：'产品文档，如何使用登录功能'）。" \
        "使用此工具前，必须确保：1) 已上传相关文档并创建了知识库；2) 知识库名称准确无误。" \
        "ONLY use when user asks about content that should be in a knowledge base."
    ),

    Tool(
        name="get time",
        func=get_time.run,
        description="获取当前系统时间（年 - 月-日 小时：分钟：秒）。输入始终为空字符串。Use this tool ONLY when user asks about current time, date, or what time it is."
    ),
    
    Tool(
        name="code interpreter",
        func=code_interpreter.run,
        description="执行 Python 代码进行计算、数据分析、图表绘制等。输入必须是有效的 Python 代码字符串。Use for mathematical calculations, data processing, plotting charts, or any task requiring code execution."
    ),
]
