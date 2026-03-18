import os
'''
sqlalchemy  ORM（对象关系映射）库
create_engine:创建数据库连接引擎
Column, Integer, String: 定义表的列和数据类型
declarative_base: 声明式基类，用于定义模型
sessionmaker: 创建数据库会话工厂
configs.setting: 从配置文件导入数据库配置
'''
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from configs.setting_1 import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_DATABASE

# 确保数据库目录存在
if not os.path.exists(SQLALCHEMY_DATABASE):
    os.makedirs(SQLALCHEMY_DATABASE)

# 创建数据库引擎，这里使用的是 SQLite
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)

# 创建基类，所有模型都将继承自这个基类
# 创建一个基类，具有：
# 1. 元数据管理 (metadata)
# 2. 查询接口 (query)
# 3. 序列化支持
# 4. 表结构映射
Base = declarative_base()

# 在agent_chat函数中：
# agent_executor.acall(
#     inputs={
#         "input": query,           # 用户问题
#         "history": histories,     # 对话历史
#         "knowledgebases": kbs,    # ← 从这里来！
#         "documents": documents    # 上传的文件内容
#     }
# )

# Agent会根据knowledgebases信息知道：
# - 系统中有哪些可用的知识库
# - 每个知识库是关于什么的
# - 应该使用哪个知识库来回答问题

# 定义 KnowledgeBase 模型
class KnowledgeBase(Base):
    __tablename__ = 'knowledge_bases'  # 表名

    #数据库的表结构
    #id           - 唯一标识符
    id = Column(Integer, primary_key=True, autoincrement=True, comment="知识库ID")  # 主键
    #kb_name      - 知识库名称（如"产品文档"、"用户手册"）
    kb_name = Column(String(50), comment="知识库名称")  # 知识库名称
    #kb_info      - 知识库描述（用于Agent理解其内容）
    kb_info = Column(String(200), comment="知识库简介(用于Agent)")  # 知识库简介

    def __repr__(self):
        return f"<KnowledgeBase(id='{self.id}', kb_name='{self.kb_name}', kb_info='{self.kb_info}')>"
#
#
# 创建所有表
Base.metadata.create_all(engine)

# 创建会话
Session = sessionmaker(bind=engine)
session = Session()
