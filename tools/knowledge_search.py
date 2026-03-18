import json

import requests
from pydantic import Field
from configs.setting_1 import TIME_OUT

# 知识库搜索工具类
class KnowledgeBaseSearch:
    inputs: str = Field(description="包含知识库名称和需要查询问题的字符串")

    def run(self, inputs):
        # 解析输入：kb_name,query
        parts = inputs.split(",", 1)
        if len(parts) != 2:
            return f"【格式错误】请输入正确的格式或与之相似的格式：知识库名称，问题"
        
        kb_name = parts[0].strip()
        query = parts[1].strip()

        # # 自动添加 .faiss 后缀（如果用户没有输入）
        # if not kb_name.endswith('.faiss'):
        #     kb_name = f"{kb_name}.faiss"
        # else:
        #     kb_name = kb_name
            
        # 2. 构造API端点URL
        # 注意：这里是本地服务的地址，端口6605
        url = "http://127.0.0.1:6605/knowledgebase/search_kb"

        # 请求体数据
        data = {
            "kb_name": kb_name,
            "query": query
        }

        # 将数据转换为JSON格式
        json_data = json.dumps(data)

        # 设置请求头，指定发送的数据格式为JSON
        headers = {
            'Content-Type': 'application/json'
        }

        # 发送POST请求
        response = requests.post(url, data=json_data, headers=headers, timeout=TIME_OUT)
        if response.status_code != 200:
            return f"【系统错误】知识库服务返回错误: {response.status_code}"
        
        # 如果请求成功，解析返回数据
        result = response.json()
        # 4. **关键修改：检查是否有结果**
        if not result.get("results"):
            return f"【查询结果】在知识库 '{kb_name}' 中没有找到与“{query}”相关的信息。建议尝试其他关键词或使用网络搜索。"
        # 5. 格式化结果
        formatted = f"【查询结果】在知识库 '{kb_name}' 中找到以下信息：\n\n"
        for i, item in enumerate(result["results"], 1):
            source = item.get('source', '未知来源')
            content = item.get('content', '')
            formatted += f"{i}. 【来源】{source}\n   【内容】{content}\n\n"
        
        return formatted
        # # 获取知识库信息
        # res = "".join([f"source:\n{d['sources']} \ncontext:\n{d['page_contents']}\n" for d in data['results']])
        # return res
    
        # return f"无法获取和{query}有关信息"


knowledgebas_search = KnowledgeBaseSearch()
# 使用示例
# print(database_search.run("hqyj,黑熊精自称"))
