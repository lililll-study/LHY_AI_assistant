import base64   #base64编解码，用于处理图像数据
import os
import re   #正则表达式，用于代码清理
from uuid import uuid4  #生成唯一ID
from codeboxapi import CodeBox  #代码执行沙箱，安全运行代码
from configs.setting_1 import MEDIA_DIR   # 配置文件中的媒体目录路径

'''
代码解释器实现：
用于安全的执行代码并输出图像等

'''
class CodeInterpreter:
    def __init__(self):
        self.output_files = ""
        self.output_codes = ""
        # 创建codebox实例，使用本地密钥，能够提供安全隔离的py环境
        self.codebox = CodeBox(api_key="local")
        self.codebox.start()

    # 添加获取 output_files 的方法
    def get_outputs(self):
        # 获取代码执行的结果
        # 返回生成图像文件URL，执行原始代码
        return self.output_files, self.output_codes


    def run(self, code: str):
        # 执行py代码并输出，
        # 返回文本输出或图像处理消息
        clean_code = re.sub(r'(```python|```py|```)\s*', '', code, flags=re.IGNORECASE)
        # 去除首尾的空白字符
        clean_code = clean_code.strip()
        # 去除多余的空行
        lines = [line for line in clean_code.split('\n') if line.strip()]
        # 将处理后的行重新组合成字符串
        cleaned_code = '\n'.join(lines)
        output = self.codebox.run(cleaned_code)

        # 检查输出类型：如果为png图像
        if output.type == "image/png":
            filename = f"{MEDIA_DIR}/image-{uuid4()}.png" #生成唯一文件名，防止冲突，uuid4()随机生成唯一标识符
            decoded_image = base64.b64decode(output.content)   # 对图片进行base64解码

            # 将解码后的数据写入文件
            with open(filename, 'wb') as file:
                file.write(decoded_image)

            # 生成图片的URL，用于前端访问
            #os.path.basename(filename)获取文件名
            image_url = f"/media/{os.path.basename(filename)}"
            # 保存输出信息到实例变量
            self.output_files = image_url
            self.output_codes = code

            # 返回提示信息（前端会处理图片显示）
            return f"Image got send to the user."
        else: # 如果为文本输出则直接返回内容
            return output.content


code_interpreter = CodeInterpreter()
