import uuid
import gradio as gr
from webui.chat_with_agent_api import chat_with_agent
from webui.knowledgebase_api import create_kb, delete_kb, upload_docs, list_kbs, update


# 定义一个生成唯一会话 ID 的函数
def generate_session_id():
    return str(uuid.uuid4())
# 获取会话信息显示
def get_session_info(session_id):
    return f"{session_id[:8]}..." if session_id else ""
# 重置会话（新建对话）
def reset_conversation():
    new_session_id = generate_session_id()
    return new_session_id, [], None, f"{new_session_id[:8]}..."

# 在 Gradio 应用加载时生成新的会话ID
def on_app_load():
    session_id = generate_session_id()
    return session_id


with gr.Blocks(fill_width=True, fill_height=True) as demo:
    # 使用 on_load 事件来生成会话ID
    session_state = gr.State(value=on_app_load)

    with gr.Tab("🤖 AIcode"):
        gr.Markdown("## 🤖 AIcode")

        with gr.Row():
            with gr.Column(scale=1, variant="panel") as sidebar_left:
                sys_prompt = gr.Textbox(
                    label="系统提示语",
                    value="You are a helpful assistant. Answer questions in chinese !"
                    )
                # history_len = gr.Slider(minimum=-1, maximum=10, value=-1, step=1, label="保留历史消息的数量")
                temperature = gr.Slider(
                    minimum=0.01, 
                    maximum=2.0, 
                    value=0.5, 
                    step=0.01, 
                    label="temperature"
                    )
                max_tokens = gr.Slider(
                    minimum=64, 
                    maximum=1024, 
                    value=512, 
                    step=8, 
                    label="max_length")
                stream = gr.Checkbox(
                    label="stream", 
                    value=True, 
                    info="逐步显示回答内容")
                
                # 新增：会话控制区域
                gr.Markdown("---")
                gr.Markdown("### 💬 会话控制")
                session_info_display = gr.Textbox(
                    label="当前会话 ID", 
                    value="", 
                    interactive=False,
                    info="每个会话独立保存对话历史"
                )
                # 新增：新建对话按钮
                new_chat_btn = gr.Button("🆕 新建对话", variant="primary", size="lg")

            with gr.Column(scale=10) as main:
                chatbot = gr.Chatbot(height=600, type="messages", show_copy_button=True)
                gr.ChatInterface(fn=chat_with_agent,
                                 multimodal=True,
                                 type="messages",
                                 theme="soft",
                                 chatbot=chatbot,
                                 additional_inputs=[
                                     sys_prompt,
                                    #  history_len,
                                     temperature,
                                     max_tokens,
                                     stream,
                                     session_state,  # 使用 session_state 组件来传递会话ID
                                 ],
                                 examples=[
                                     [{"text": "你好，请介绍一下你自己"}],
                                     [{"text": "今天天气怎么样？"}],
                                     [{"text": "讲个笑话听听"}],
                                     [{"text": "帮我分析一下上传的文档"}]
                                 ],
                                 )
                
        # 绑定新建对话按钮的事件
        new_chat_btn.click(
            fn=reset_conversation,
            inputs=[],
            outputs=[session_state, chatbot, gr.State(), session_info_display],
            queue=False
        ).then(
            fn=lambda: gr.Files(label="选择文件", visible=True),
            inputs=[],
            outputs=[],
        )
        
        # 更新会话信息显示
        session_state.change(
            fn=get_session_info,
            inputs=[session_state],
            outputs=[session_info_display]
        )

    # 知识库操作页
    with gr.Tab("知识库管理"):
        gr.Markdown("## 📚 知识库管理")

        with gr.Row():
            kb_name = gr.Textbox(label="知识库名称", placeholder="请输入知识库名称")
        with gr.Row():
            kb_info = gr.Textbox(label="知识库描述", placeholder="请输入知识库描述")
        with gr.Row():
            # 隐藏的消息框，用于显示操作结果
            # message_box = gr.Markdown(visible=False)
            # 消息框，用于显示操作结果
            message_box = gr.Markdown("等待操作...")
        with gr.Row():
            create_button = gr.Button("创建知识库")
            delete_button = gr.Button("删除知识库")
        # 获取模拟的知识库列表
        kbs_result = list_kbs()
        kbs = kbs_result['choices'] if kbs_result and 'choices' in kbs_result else []

        # kbs = list_kbs()['choices']
        with gr.Row():
            kb_name_upload = gr.Dropdown(label="选择知识库", choices=kbs, interactive=True)
        with gr.Row():
            file_uploaded = gr.Files(label="已选择的文件", visible=False)
        with gr.Row():
            file_upload = gr.Files(label="选择文件")

        with gr.Row():
            chunk_size = gr.Number(label="知识库中单段文本最大长度(chunk_size)", value=128, minimum=1, maximum=800)
            chunk_overlap = gr.Number(label="知识库中相邻文本重合长度(chunk_overlap)", value=20, minimum=0, maximum=400)
        with gr.Row():
            upload_button = gr.Button("上传并向量化")
        with gr.Row():
            # 隐藏的消息框，用于显示操作结果
            upload_message_box = gr.Markdown("等待上传...")

        create_button.click(create_kb,
                    [kb_name, kb_info],
                   [message_box, kb_name, kb_info]).then(fn=list_kbs,
                                                                outputs=kb_name_upload)

        delete_button.click(delete_kb,
                    [kb_name_upload],
                   [message_box, kb_name]).then(fn=list_kbs,
                                                       outputs=kb_name_upload)

        file_upload.upload(fn=update, inputs=[file_upload], outputs=[file_uploaded, file_upload])

        upload_button.click(upload_docs, [kb_name_upload, file_uploaded, chunk_size, chunk_overlap],
                            [upload_message_box, file_uploaded])



# 调试时添加的代码
if __name__ == "__main__":
    print("启动模拟UI界面...")
    print("访问地址: http://127.0.0.1:7860")

    # 启动应用，添加一些参数确保正确运行
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,  # 添加这个
        debug=True,
        prevent_thread_lock=True
    )