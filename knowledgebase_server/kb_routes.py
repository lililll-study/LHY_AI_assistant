# Description: 知识库管理API，使用硅基流动Embedding模型和本地FAISS向量存储库
# 进行知识库的创建、删除、文件上传、文件删除、搜索等操作。
import os
import shutil
from typing import List

import jieba
# from langchain_openai import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from .loader.loader import data_loader
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastapi import HTTPException, APIRouter, Body, UploadFile, File, Form
from database_server.database import session
from database_server.kb_add import add_kb_to_db, del_kb_from_db
from configs.setting_1 import KB_DIR, FILE_STORAGE_DIR, embedding_model_path
from utils.intent_classifier import intent_classifier
#初始化知识库的API路由前缀
kb_router = APIRouter(prefix="/knowledgebase", tags=["knowledge Bases Management"])


# 确保知识库目录存在
if not os.path.exists(KB_DIR):
    os.makedirs(KB_DIR)

# 创建一个嵌入对象（你可以根据需要调整）
# 封装硅基流动的API嵌入模型
class CustomEmbeddingModel(Embeddings):
    def __init__(self, model, model_name):
        self.model = model
        self.model_name = model_name
    # 批量文本向量化+
    def embed_documents(self, texts):
        return [self.model.client.create(model=self.model_name, input=text).data[0].embedding for text in texts]
    # 单个查询向量化
    def embed_query(self, text):
        return self.model.client.create(model=self.model_name, input=text).data[0].embedding
# embedding = OpenAIEmbeddings(
#             api_key="sk-nyckurexksxypavebrzykejulyomtrtfypwtsxtbtugnrxuq",
#             base_url="https://api.siliconflow.cn/v1",
#             )
# embedding_model = CustomEmbeddingModel(embedding, "BAAI/bge-large-zh-v1.5")
embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_path)

# 创建知识库的API
@kb_router.post("/create_kb")
async def create_kb(
        kb_name: str = Body(..., description="知识库名称"),
        kb_info: str = Body("", description="知识库内容简介，用于Agent选择知识库。"),

):
    # 创建空的知识库（向量数据库）
    # 创建空FAISS -> 保存到本地 -> 记录到数据库
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")

    # 检查知识库是否已经存在
    if os.path.exists(kb_path):
        raise HTTPException(status_code=400, detail="知识库已经存在")
    # 创建空的FAISS向量库
    doc = Document(page_content="init", metadata={})
    vector_store = FAISS.from_documents([doc], embedding_model, normalize_L2=True)
    # 删除初始化文档
    ids = list(vector_store.docstore._dict.keys())
    vector_store.delete(ids)

    # 保存到磁盘
    vector_store.save_local(kb_path)
    # 记录到SQL数据库

    add_kb_to_db(session, kb_name, kb_info)

    return {"message": f"知识库 '{kb_name}' 创建成功！"}

# 删除知识库的API
@kb_router.delete("/delete_kb")
async def delete_kb(kb_name: str):
    # 删除知识库：删除 向量库+原始文件+数据库记录
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    kb_files_path = os.path.join(FILE_STORAGE_DIR, kb_name)
    # 检查知识库是否存在
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database not found")

    # 删除知识库
    shutil.rmtree(kb_path)
    # 删除知识库关联文件
    if os.path.exists(kb_files_path):
        shutil.rmtree(kb_files_path)

    del_kb_from_db(session, kb_name)

    return {"message": f"Database '{kb_name}' deleted successfully"}

# 列出所有知识库的API
@kb_router.get("/list_kbs")
async def list_kbs():
    kb_files = [f for f in os.listdir(KB_DIR) if f.endswith(".faiss")]
    return {"knowledgebases": kb_files}

@kb_router.post("/upload_docs")
async def upload_docs(
        files: List[UploadFile] = File(...),
        kb_name: str = Form(..., description="知识库名称"),
        chunk_size: int = Form(128, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Form(20, description="知识库中相邻文本重合长度"),
):
    # 上传文档到知识库：保存文件 + 文本分割 + 向量化 + 添加到向量库
    # 1.验证知识库存在
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database not found")

    # 2.创建文件存储目录
    kb_file_storage_path = os.path.join(FILE_STORAGE_DIR, kb_name)
    # 检查知识库对应的文件存储文件夹是否存在，不存在则创建
    os.makedirs(kb_file_storage_path, exist_ok=True)

    updated_file = []
    for file in files:
        # 保存原始文件
        file_path = os.path.join(kb_file_storage_path, file.filename)
        file_content = file.file.read()

        with open(file_path, "wb") as f:
            f.write(file_content)

        # 加载和分割文档
        # 解析文本文件内容并分割成小块
        loader = data_loader().get_loader(file_path) #根据源文件选择加载器
        docs = loader.load()# 将文档加载为一个文档对象列表
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size,   #定义分割器的分割参数，每个快的大小，重叠字符数，分隔符
                                                       chunk_overlap=chunk_overlap,
                                                       separators=[
        "\n## ",           # 二级标题（最重要，每个景区大块）
        "\n### ",          # 三级标题（每个具体景点）
        "\n\n",            # 段落空行
        "\n",              # 换行
        "。",              # 句子结束
        "，",              # 逗号分隔
        " ",               # 空格
        ""                 # 最后手段
        ], )
        # 将文档分割为多个块
        chunks = text_splitter.split_documents(docs)    #使用分割器对文档进行分割

        # 加载知识库（向量库）
        vectorstore = FAISS.load_local(kb_path, embedding_model, allow_dangerous_deserialization=True)
        # 将文件内容向量化并添加到知识库
        vectorstore.add_documents(chunks)

        # 保存更新后的知识库
        vectorstore.save_local(kb_path)
        updated_file.append(file.filename)

    return {"message": f"File '{updated_file}' added to database '{kb_name}' successfully"}

@kb_router.post("/delete_docs")
async def delete_docs(
        file_names: List[str] = Body(..., examples=[["test.txt"]]),
        kb_name: str = Body(..., description="知识库名称"),
):
    # 从知识库删除特定文件
    # 删除原始文件 + 从向量库删除对应向量
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")
    kb_file_storage_path = os.path.join(FILE_STORAGE_DIR, kb_name)

    # 检查知识库是否存在
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail=f"知识库 {kb_name} 不存在")

    # 加载知识库
    vector_store = FAISS.load_local(kb_path, embedding_model,
                                    allow_dangerous_deserialization=True)

    failed_files = {}
    success_files = []
    for file_name in file_names:
        file_path = os.path.join(kb_file_storage_path, file_name)
        # 检查文件是否存在
        if not os.path.exists(file_path):
            failed_files[file_name] = f"未找到文件 {file_name}"
            continue

        # 尝试删除文件
        try:
            os.remove(file_path)
            ids = [
                k
                for k, v in vector_store.docstore._dict.items()
                if v.metadata.get("source").lower() == file_path.lower()
            ]
            if len(ids) > 0:
                vector_store.delete(ids)
                success_files.append(file_name)
            else:
                failed_files[file_name] = f"文件 {file_name} 在向量存储中找不到"
        except Exception as e:
            failed_files[file_name] = str(e)

    # 保存更新后的向量存储
    try:
        vector_store.save_local(kb_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存向量存储时出错: {str(e)}")

    response = {
        "success": success_files,
        "failed": failed_files
    }

    return response

@kb_router.post("/search_kb")
async def search_kb(
        kb_name: str = Body(..., description="知识库名称"),
        query: str = Body(..., description="问题"),
        top_k: int = Body(3, description="返回的相似文档数量")
):
    # 搜索知识库中的相关内容：
    # 使用混合搜索：50%BM25（关键词搜索）+50%FAISS（语义搜索）
    kb_path = os.path.join(KB_DIR, f"{kb_name}.faiss")

    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database not found")

    # 加载知识库
    vector_store = FAISS.load_local(kb_path, embedding_model,
                                    allow_dangerous_deserialization=True)

    #**意图识别
    intent_result = intent_classifier.classify(query)
    weights = intent_result["weights"]
    # 根据意图调整返回数量
    if intent_result["intent"] == "EXACT":
        actual_top_k = min(top_k, 2)
    elif intent_result["intent"] == "SEMANTIC":
        actual_top_k = max(top_k, 4)
    else:
        actual_top_k = top_k
    # 创建检索器
    docs = list(vector_store.docstore._dict.values())
    faiss_retriever = vector_store.as_retriever(search_kwargs={"k": actual_top_k})
    bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=jieba.lcut_for_search)
    bm25_retriever.k = actual_top_k

    # 混合检索
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever], 
        weights=[weights["bm25"], weights["faiss"]]
    )
    # # 使用 FAISS 进行相似度检索，设置查找的相关文档数为2，考虑到响应时间和回答效率等因素
    # faiss_retriever = vector_store.as_retriever(search_kwargs={"k": 2})
    # docs = list(vector_store.docstore._dict.values())
    # # 使用 BM25 进行相似度检索，设置查找的相关文档数为2，考虑到响应时间和回答效率等因素
    # bm25_retriever = BM25Retriever.from_documents(docs, preprocess_func=jieba.lcut_for_search)
    # bm25_retriever.k = 2  # 设置 BM25 检索器返回的文档数量
    # # 设置混合检索模型，权重0.5 0.5
    # ensemble_retriever = EnsembleRetriever(
    #     retrievers=[bm25_retriever, faiss_retriever], weights=[0.5, 0.5]
    # )

    # 根据输入来执行检索
    contexts = ensemble_retriever.invoke(query)
    return {
        "results": [
            {
                "source": context.metadata.get("source", ""),
                "content": context.page_content
            } for context in contexts
        ],
        "found": len(contexts) > 0,  # 增加明确标志
        "intent": intent_result  # 返回意图信息便于调试
    }
    # # 将检索结果进行格式化，将字典结果整合为一个列表
    # contexts = {
    #     "results": [
    #         {
    #         "sources": context.metadata.get("source", ""),
    #         "page_contents": context.page_content
    #         } for context in contexts],
    # }
    # return contexts