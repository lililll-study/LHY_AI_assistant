from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Literal, Union, cast

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

class CustomAsyncIteratorCallbackHandler(AsyncCallbackHandler):

    queue: asyncio.Queue[str]   # 存储要输出的token队列
    done: asyncio.Event         # 标记LLM是否完成的事件

    @property
    def always_verbose(self) -> bool:
        return True

    def __init__(self) -> None:
        # 初始化队列和事件
        self.queue = asyncio.Queue()
        self.done = asyncio.Event()

        # 初始化答案前缀和答案到达标志
        self.answer_prefix_tokens = ["Final", "Answer", ":"]    # 答案前缀
        self.answer_reached = False # 是否到达答案部分
        self.last_tokens = [""] * len(self.answer_prefix_tokens)# 记录最近tokens

    async def on_llm_start( #LLM开始时的回调
        # 每次LLM开始生成时，重置所有状态，确保新的对话干净开始。
            self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        # 如果连续进行两次调用，这会重置状态
        self.done.clear()
        self.answer_reached = False #  将answer_reached设置为False

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        # 1. 更新最近tokens记录（滑动窗口）
        if token is not None and token != "":
            self.last_tokens.append(token.strip())
            if len(self.last_tokens) > len(self.answer_prefix_tokens) + 1:
                self.last_tokens.pop(0) # 保持窗口大小
            # 2. 检查是否到达答案部分
            if self.last_tokens[:-1] == self.answer_prefix_tokens:
                self.answer_reached = True
            # 3. 如果到达答案部分，将token放入队列
            if self.answer_reached:
                self.queue.put_nowait(token)
    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self.answer_reached:
            self.done.set()

    async def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.done.set()
    async def aiter(self) -> AsyncIterator[str]:
        while not self.queue.empty() or not self.done.is_set():
            # 等待队列中的下一个token，但如果done事件被设置则停止等待
            done, other = await asyncio.wait(
                [
                    # 任务1：从队列获取token
                    asyncio.ensure_future(self.queue.get()),
                    # 任务2：等待完成事件
                    asyncio.ensure_future(self.done.wait()),
                ],
                return_when=asyncio.FIRST_COMPLETED,  # 任意一个完成就返回
            )

            # 取消另一个未完成的任务
            if other:
                other.pop().cancel()

            # 提取第一个完成任务的结果
            token_or_done = cast(Union[str, Literal[True]], done.pop().result())

            # 如果提取的值是布尔值True，说明done事件被设置了
            if token_or_done is True:
                break

            # 否则，提取的值是一个token，我们yield它
            yield token_or_done