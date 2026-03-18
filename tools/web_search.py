# 网络搜索API工具类
import requests
from pydantic import Field
from configs.setting_1 import TIME_OUT, settings
import json
class WebSearch:
    query: str = Field(description="需要网上查找的内容")

    def __init__(self, api_key=None):
        # 初始化函数，用于创建类的实例
        self.api_key = api_key or settings.web_search_api_key

    def run(self, query):
        if not query or not isinstance(query, str):
            # logger.error(f"Invalid search query: {query}")
            return "搜索关键词无效，请输入有效的搜索内容"
        
        query = query.strip()
        if not query:
            return "搜索关键词不能为空"
        #v2.0:百度搜索api
        base_url = "https://qianfan.baidubce.com/v2/ai_search/web_search"
        # 3. 构建请求体 - 只请求原始搜索结果
        payload = {
            "messages": [
                {
                    "content": query[:72],  # API限制72字符，超出会被截断 [citation:4]
                    "role": "user"
                }
            ],
            "search_source": "baidu_search_v2",  # 使用V2搜索引擎
            "resource_type_filter": [
                {"type": "web", "top_k": 5}  # 返回5条网页结果
            ],
            # 可选：按时间过滤
            # "search_recency_filter": "month",  # week/month/semiyear/year
            # 可选：指定网站搜索
            # "search_filter": {
            #     "match": {
            #         "site": ["baike.baidu.com"]  # 只在百科搜索
            #     }
            # },
            # 可选：屏蔽特定网站
            # "block_websites": ["tieba.baidu.com"]
        }
        
        # 4. 请求头 - 使用Bearer Token认证
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        # 5. 发送请求
        try:
            response = requests.post(
                base_url, 
                headers=headers,
                data=json.dumps(payload),
                timeout=TIME_OUT
            )
            response.raise_for_status()
            data = response.json()
            
            # 6. 解析返回结果
            if not data or 'references' not in data:
                return f"未找到关于'{query}'的相关信息"
            
            # 提取搜索结果列表 [citation:2][citation:4]
            references = data.get('references', [])
            
            if not references:
                return f"未找到关于'{query}'的相关信息"
            
            # 7. 格式化输出结果（纯搜索格式，无大模型总结）
            formatted_results = f"【搜索结果】{query}\n\n"
            
            for i, ref in enumerate(references[:5], 1):  # 最多显示5条
                title = ref.get('title', '无标题')
                url_link = ref.get('url', '#')
                content = ref.get('content', '')  # 搜索结果的内容摘要 [citation:2]
                website = ref.get('website', '')  # 站点名称
                date = ref.get('date', '')  # 网页日期
                
                formatted_results += f"{i}. {title}\n"
                formatted_results += f"   链接：{url_link}\n"
                if content:
                    # 限制摘要长度，避免过长
                    content_preview = content[:200] + "..." if len(content) > 200 else content
                    formatted_results += f"   摘要：{content_preview}\n"
                if website:
                    formatted_results += f"   来源：{website}"
                if date:
                    formatted_results += f" ({date})"
                formatted_results += "\n\n"
            
            return formatted_results

        except requests.exceptions.Timeout:
            return f"搜索超时，请稍后重试"
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                return "API Key无效或未授权，请检查千帆平台API Key配置"
            elif response.status_code == 429:
                return "搜索次数超限，请稍后重试或检查账户余额"
            else:
                return f"搜索服务异常：{str(e)}"
        except Exception as e:
            return f"搜索失败：{str(e)}"

        #v1.0:serpapi搜索api
        # params = {
        # # base_url = "https://serpapi.com/search"

        # # params = {
        # #     "q": query,
        # #     "api_key": self.api_key,
        # #     "engine": "baidu",  #通过Baidu搜索引擎
        # #     "rn": 3,           # 检索结果前5个
        # #     "proxy": "http://api.wlai.vip" # 代理（用了这个好像不会减使用次数）
        # }

        # # 发送请求到网络搜索API
        # try:
        #     response = requests.get(base_url, params=params, timeout=TIME_OUT)
        #     response.raise_for_status()
        #     data = response.json()
            
        #     if not data:
        #         return f"未找到关于'{query}'的相关信息"
        #     organic_results = data['organic_results'][0]['related_news'] if data['organic_results'][0].get('related_news') else data['organic_results']

        #     # 获取网络信息
        #     results = "".join([f"titles:\n{result.get('title', '')} \nlinks:\n{result.get('link', '')}\nsnippets:\n{result.get('snippet', '')}\n" for result in organic_results])
        #     return results

        # except requests.exceptions.Timeout:
        #     # logger.error(f"Web search timeout for query: {query}")
        #     return f"搜索超时，请稍后重试"


web_search = WebSearch()
