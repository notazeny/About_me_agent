"""生成层：把检索到的片段拼成提示词，调用 DeepSeek 生成带出处的回答。"""
import asyncio
import json
import queue
import threading

import aiohttp

from . import config, persona


def build_prompt(query: str, retrieved_chunks, history=None):
    """根据问题与检索片段构造提示词；可携带最近几轮对话历史作为上下文。

    history: [{role, content}, ...]，role 为 'user' / 'assistant'。
    """
    history_text = ""
    if history:
        recent = history[-(config.MAX_HISTORY_TURNS * 2):]   # 一轮 = user + assistant 两条
        history_text = "\n\n".join(
            ("用户" if m["role"] == "user" else "助手") + "：" + m["content"] for m in recent
        )

    context_parts = []
    sources = []
    for i, c in enumerate(retrieved_chunks):
        context_parts.append(f"【资料片段 {i + 1}】（来自《{c['source']}》）：\n{c['text']}")
        sources.append(c["source"])
    context = "\n\n".join(context_parts)
    source_list = "、".join(dict.fromkeys(sources))  # 去重且保持顺序

    parts = []
    if history_text:
        parts.append(f"【对话历史】（仅作上下文参考，不要照搬）\n{history_text}")
    parts.append(f"【资料】\n{context}")
    parts.append(f"【用户问题】\n{query}")
    parts.append(
        "【要求】\n"
        "1. 确实参考了【资料】作答时，回答末尾注明引用来源，格式为：— 引用自《"
        + source_list + "》；若回答「没准备好」，则不要添加引用来源。\n"
        "2. 回答要简洁、准确、条理清晰。"
    )
    return "\n\n".join(parts)


def should_refuse(chunks, threshold=config.RERANK_CONFIDENCE_THRESHOLD):
    """检索结果为空，或 top-1 分数低于阈值时，返回 True（应拒答、不调 LLM）。

    chunks: 检索结果列表（走 rerank 后每个带 score；没走 rerank 可能没有 score）
    """
    # 空结果 → return True
    if not chunks:
        return True
    # 取 chunks[0].get("score")；若是 None → return False（没有分数信息，交给提示词兜底）
    s=chunks[0].get("score")
    # 必须是 `is not None`：`!= None` 在 Python 里调用的是 __eq__，
    # 对 numpy / 自定义对象可能返回非布尔值甚至直接报错。
    if s is not None:
        if s < threshold:    # score < threshold → return True，否则 return False
            return True
        return False
    return False



async def _produce(prompt:str, q):
    """调用 DeepSeek API，返回回答文本；出错时返回错误说明。"""
    if not config.DEEPSEEK_API_KEY:
        q.put("[错误] 尚未配置 DeepSeek API Key，请把它填入 .env 文件或设置环境变量 DEEPSEEK_API_KEY。")
        q.put(None)
        return

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": persona.build_persona_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.TEMPERATURE,
        "stream": True,
    }

    timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT, connect=10)
    async with aiohttp.ClientSession() as s:
        try:
            async with s.post(url, headers=headers, json=payload,timeout=timeout) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    q.put(f"[错误] DeepSeek 接口返回异常（状态码 {resp.status}）：{error_text[:200]}")
                    q.put(None)
                    return

                # 流式解析 SSE 数据
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()  # 去掉 "data:" 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        # 格式异常则跳过，避免中断整个流程
                        continue
                    if delta:
                        # 实时打印
                        q.put(delta)
                q.put(None)
                return

        except aiohttp.ClientConnectorError:
            q.put("[错误] 无法连接 DeepSeek 服务器，请检查网络。")
            q.put(None)
        except asyncio.TimeoutError:
            q.put("[错误] DeepSeek 请求超时，请稍后重试。")
            q.put(None)
        except aiohttp.ClientError as e:
            q.put(f"[错误] 请求异常：{str(e)}")
            q.put(None)


def generate_answer_stream(prompt: str):
    """同步生成器：桥接异步流式，逐段 yield 给前端打字机。"""
    q: queue.Queue = queue.Queue()

    def runner():
        asyncio.run(_produce(prompt, q))   # 后台线程跑事件循环

    threading.Thread(target=runner, daemon=True).start()

    while True:
        chunk = q.get()
        if chunk is None:      # 约定 None 表示结束
            break
        yield chunk


if __name__ == "__main__":
    for chunk in generate_answer_stream("请用一句话解释什么是 RAG？"):
        print(chunk, end="", flush=True)
    print()
