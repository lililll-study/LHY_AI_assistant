from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from chat.chat_routes import chat_router
from knowledgebase_server.kb_routes import kb_router
from fastapi.staticfiles import StaticFiles
from configs.setting_1 import MEDIA_DIR


app = FastAPI()

# 2. 配置CORS跨域资源共享--使得前端能够访问后端数据
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源（开发环境方便调试，生产环境应限制）
    allow_credentials=True,# 允许携带凭据（如cookies、授权头）
    allow_methods=["*"], # 允许所有HTTP方法（GET、POST、PUT等）
    allow_headers=["*"],# 允许所有请求头
)

# 3. 注册路由模块
# 将各个共模块的路由挂载到主应用中
# 这样来自客户端的请求就可以分发到对应的处理函数
app.include_router(chat_router) #处理聊天相关API
app.include_router(kb_router)   #处理知识库相关API

# 挂载静态文件目录:
# 用于将一个完整的子应用或静态文件目录挂载到指定的路径上。
# app.mount(路径, 应用或目录, name="名称")
# 当ai助手生成图片，保存在本地MEDIA_DIR路径中，这样使得浏览器能够访问本地的图片文件
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=6605,
        log_level="info",
    )
