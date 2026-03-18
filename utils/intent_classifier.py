# utils/intent_classifier.py
import re
import jieba
from typing import Dict

class IntentClassifier:
    """意图识别器：分析查询意图，为动态权重分配提供依据"""
    
    def __init__(self):
        # 意图类型
        self.INTENT_TYPES = {
            "EXACT": "精确匹配意图",     # 查型号、代码、ID等
            "SEMANTIC": "语义搜索意图",  # 查概念、解释、方法等
            "FACTUAL": "事实查询意图",   # 查定义、属性、特征
            "ENTITY": "实体查询意图",    # 新增：查人物、地点、组织等实体
        }
        
        # 精确匹配模式（型号/编号/版本等）
        self.exact_patterns = [
            r'[A-Z0-9]{2,}[-_]?[A-Z0-9]+',  # 型号：iPhone-14
            r'版本|型号|代码|ID|编号|v\d+\.\d+',
            r'\d{4}-\d{2}-\d{2}',  # 日期
        ]
        
        # 语义搜索关键词
        self.semantic_keywords = ['如何', '怎么', '为什么', '解释', '原理', '方法']
        
        # 事实查询关键词（增强）
        self.factual_keywords = [
            '定义', '属性', '特征', '有哪些', '包括', '类型',
            '是什么', '什么是', '是谁', '谁是',  # 新增：人物相关
            '关系', '关联', '联系',  # 新增：关系查询
            '介绍', '简介', '描述'   # 新增：介绍类
        ]
        
        # 实体查询关键词（新增）
        self.entity_keywords = [
            '人物', '角色', '主角', '配角',  # 人物类
            '地点', '地方', '位置',  # 地点类
            '组织', '机构', '公司',  # 组织类
            '作品', '书籍', '电影',  # 作品类
        ]
        
        # 常见人物名称模式（中文人名、角色名）
        self.name_patterns = [
            r'孙悟空|唐僧|八戒|沙僧|白龙马',  # 西游记角色
            r'宋江|卢俊义|吴用|武松|林冲',    # 水浒传角色
            r'刘备|关羽|张飞|曹操|孙权',       # 三国角色
            r'贾宝玉|林黛玉|薛宝钗|王熙凤',    # 红楼梦角色
            r'[^\s]{2,4}和[^\s]{2,4}',         # X和Y（人物关系）
            r'[^\s]{2,4}与[^\s]{2,4}',          # X与Y
        ]
    
    def classify(self, query: str) -> Dict:
        """分析查询意图，返回意图类型和推荐权重"""
        query = query.strip()
        
        # 计算各意图分数
        scores = {
            "EXACT": self._score_exact(query),
            "SEMANTIC": self._score_semantic(query),
            "FACTUAL": self._score_factual(query),
            "ENTITY": self._score_entity(query)  # 新增实体查询评分
        }
        
        # 找出最高分意图
        primary_intent = max(scores, key=scores.get)
        confidence = scores[primary_intent]
        
        # 默认使用语义搜索
        if confidence < 0.3:
            primary_intent = "FACTUAL"
            confidence = 0.5
        
        # 根据意图推荐权重
        weights = self._get_weights(primary_intent)
        
        return {
            "intent": primary_intent,
            "description": self.INTENT_TYPES[primary_intent],
            "confidence": confidence,
            "scores": scores,  # 调试用
            "weights": weights
        }
    
    def _score_exact(self, query: str) -> float:
        """精确匹配意图分数"""
        score = 0.0
        for pattern in self.exact_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                score += 0.4
        # 包含数字和英文的组合
        if re.search(r'\d', query) and re.search(r'[a-zA-Z]', query):
            score += 0.3
        return min(score, 1.0)
    
    def _score_semantic(self, query: str) -> float:
        """语义搜索意图分数"""
        score = 0.0
        for keyword in self.semantic_keywords:
            if keyword in query:
                score += 0.3
        if len(query) > 20:  # 长查询倾向语义
            score += 0.2
        return min(score, 1.0)
    
    def _score_factual(self, query: str) -> float:
        """事实查询意图分数（增强版）"""
        score = 0.0
        
        # 事实关键词匹配
        for keyword in self.factual_keywords:
            if keyword in query:
                score += 0.3
                break  # 匹配到一个就够
        
        # 人物关系模式
        if re.search(r'[^\s]{2,4}和[^\s]{2,4}|[^\s]{2,4}与[^\s]{2,4}', query):
            score += 0.5  # "X和Y" 模式，强烈的事实查询信号
        
        # 常见角色名匹配
        for pattern in self.name_patterns:
            if re.search(pattern, query):
                score += 0.4
                break
        
        # 疑问词匹配
        if any(word in query for word in ['谁', '什么', '哪', '吗', '呢', '？', '?']):
            score += 0.2
        
        return min(score, 1.0)
    
    def _score_entity(self, query: str) -> float:
        """实体查询意图分数（新增）"""
        score = 0.0
        
        # 实体类型关键词
        for keyword in self.entity_keywords:
            if keyword in query:
                score += 0.4
        
        # 具体人名（2-4个中文字符）
        chinese_names = re.findall(r'[\u4e00-\u9fa5]{2,4}', query)
        if chinese_names:
            score += 0.2 * min(len(chinese_names), 2)  # 最多加0.4
        
        return min(score, 1.0)
    
    def _get_weights(self, intent: str) -> Dict:
        """根据意图返回搜索权重"""
        weights = {
            "EXACT": {"bm25": 0.8, "faiss": 0.2},     # 精确匹配优先BM25
            "SEMANTIC": {"bm25": 0.3, "faiss": 0.7},  # 语义搜索优先FAISS
            "FACTUAL": {"bm25": 0.6, "faiss": 0.4},   # 事实查询偏BM25（因为涉及具体实体）
            "ENTITY": {"bm25": 0.7, "faiss": 0.3},    # 实体查询更偏BM25
        }
        return weights.get(intent, {"bm25": 0.5, "faiss": 0.5})

# 全局实例
intent_classifier = IntentClassifier()