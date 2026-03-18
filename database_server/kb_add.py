"""
添加/更新知识库：add_kb_to_db()
删除知识库：del_kb_from_db()
查询所有知识库：list_kb_from_db()
"""
from database_server.database import KnowledgeBase    # 数据模型
from sqlalchemy.exc import IntegrityError   # 数据库完整性错误
from sqlalchemy.orm import Session          # 数据库会话

def add_kb_to_db(session: Session, kb_name: str, kb_info: str):
    try:
        # 查询是否存在相同名称的知识库
        kb = session.query(KnowledgeBase).filter(KnowledgeBase.kb_name.ilike(kb_name)).first()

        if not kb:
            # 如果不存在，创建新的知识库实例
            kb = KnowledgeBase(kb_name=kb_name, kb_info=kb_info)
            session.add(kb)
            session.commit()
            print(f"KnowledgeBase '{kb_name}' created successfully.")
        else:
            # 如果存在，更新知识库信息
            kb.kb_info = kb_info
            session.commit()
            print(f"KnowledgeBase '{kb_name}' updated successfully.")
    except IntegrityError as e:
        session.rollback()
        print(f"IntegrityError: {e}")
    except Exception as e:
        session.rollback()
        print(f"An error occurred: {e}")
def del_kb_from_db(session: Session, kb_name: str):
    try:
        # 查询是否存在指定名称的知识库
        # 通过filter_by方法查询名称为kb_name的知识库是否存在。
        kb_to_delete = session.query(KnowledgeBase).filter_by(kb_name=kb_name).first()

        if kb_to_delete:
            # 如果存在，删除知识库
            session.delete(kb_to_delete)
            session.commit()
            print(f"KnowledgeBase '{kb_name}' deleted successfully.")
        else:
            print(f"KnowledgeBase '{kb_name}' does not exist.")
    except IntegrityError as e:
        session.rollback()
        print(f"IntegrityError: {e}")
    except Exception as e:
        session.rollback()
        print(f"An error occurred: {e}")

# 通过 filter_by 方法查询名称为 kb_name 的知识库是否存在。
def list_kb_from_db(session: Session):
    #通过 session.query(KnowledgeBase).all() 获取所有知识库记录
    all_kbs = session.query(KnowledgeBase).all()
    # 使用列表推导式，将每条记录转换为字典形式，将所有字典转换为列表。

    kbs_list = [
        {
            # "id": kb.id,
            "kb_name": kb.kb_name,
            "kb_info": kb.kb_info
        }
        for kb in all_kbs
    ]
    return kbs_list

'''
以上三个函数未改变向量数据库，而是对数据库进行操作
仅改变存放在SQL数据库中对于知识库的描述
'''