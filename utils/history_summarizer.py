
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from configs.setting_1 import chat_model_name, api_key, base_url
from typing import List, Dict, Tuple

class HistorySummarizer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=chat_model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,    #低温度确保摘要的稳定性和一致性
            max_tokens=300
        )
        self.summary_threshold = 8  # 超过8条消息开始摘要
        self.keep_recent = 4        # 保留最近4条具体对话
    
    async def compress(self, full_history: List[Dict], current_query: str) -> Tuple[str, Dict]: #返回格式化的历史字符串和统计信息
        """压缩历史：早期历史生成摘要，保留最近对话"""
        if not full_history or len(full_history) <= self.summary_threshold:
            return self._format(full_history), {"mode": "full"}
        
        # 分离最近对话和早期历史
        recent = full_history[-self.keep_recent:]
        early = full_history[:-self.keep_recent]
        
        # 为早期历史生成摘要
        summary = await self._summarize(early)
        
        # 组合最终历史
        recent_text = self._format(recent)
        final = f"【历史摘要】\n{summary}\n\n【最近对话】\n{recent_text}" if summary else recent_text
        
        stats = {
            "mode": "compressed",
            "total": len(full_history),
            "early": len(early),
            "recent": len(recent),
            "summary_length": len(summary)
        }
        print(f"📄 摘要内容: {summary}")
        return final, stats
    
    async def _summarize(self, history: List[Dict]) -> str:
        """生成摘要"""
        if not history:
            return ""
        
        history_text = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in history])
        
        prompt = f"请对以下完整的对话历史进行摘要，每段摘要不超过10个字，涵盖所有讨论过的话题：\n{history_text}"
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return response.content
        except:
            return f"[共{len(history)}条历史对话]"
    
    def _format(self, history: List[Dict]) -> str:
        """格式化对话"""
        return "\n\n".join([f"{m['role']}:{m['content']}" for m in history if m.get('content')])


# 全局实例
summarizer = HistorySummarizer()