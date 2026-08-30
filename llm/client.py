"""LLM 客户端：兼容 DeepSeek / OpenAI，封装普通调用与 JSON 结构化输出。

架构（LangChain 主链路 + 原生 SDK 兜底）：
  - 默认走 LangChain（ChatOpenAI + 链式调用），配置文件 USE_LANGCHAIN 可关；
  - LangChain 失败时自动回退到 openai SDK 直连，保证服务不中断；
  - 底层实现均延迟导入（函数内部 import），确保未安装 LLM 依赖时，
    项目其余模块（规则兜底意图识别、离线验证等）仍可正常导入和运行。
"""
import json
import re
import time

from config.settings import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    USE_LANGCHAIN, LLM_MAX_RETRIES,
)
from config.logger import logger


def parse_llm_json(text: str) -> dict:
    """健壮解析 LLM 输出的 JSON。

    容忍：markdown 代码围栏(```json)、前后缀文本、双重 JSON 编码。
    解析失败抛出 ValueError。
    """
    if not text or not text.strip():
        raise ValueError("LLM 返回内容为空")
    text = text.strip()

    # 1) 去掉 ```json ... ``` 代码围栏
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    # 2) 直接解析
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 3) 提取最外层 { ... } 后解析（容忍前后缀文本）
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 4) 双重编码：整体是一个被转义的 JSON 字符串
    try:
        data = json.loads(json.loads(text))
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    raise ValueError(f"无法解析 LLM 返回的 JSON：{text[:200]}")


def _get_client():
    from openai import OpenAI  # 延迟导入
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def _normalize_messages(messages: list) -> list:
    """把 dict 格式消息统一转成 LangChain BaseMessage，方便两种后端共用。

    LangChain 调用需要 BaseMessage；openai SDK 调用时再转回 dict。
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    out = []
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content", "")
            out.append(
                SystemMessage(content=content) if m.get("role") == "system"
                else HumanMessage(content=content)
            )
        else:
            out.append(m)  # 已是 BaseMessage（如 FewShotChatMessagePromptTemplate 产物）
    return out


def _prompt_chars(messages: list) -> int:
    """统计提示词总字符数（兼容 dict 与 BaseMessage）。"""
    total = 0
    for m in messages:
        if isinstance(m, dict):
            total += len(m.get("content", ""))
        else:
            total += len(getattr(m, "content", "") or "")
    return total


def _run_langchain(messages: list, *, temperature: float, json_mode: bool,
                   start: float) -> str:
    """LangChain 主链路：ChatOpenAI 封装 + StrOutputParser 链式调用。"""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_openai import ChatOpenAI

    model_kwargs = {}
    if json_mode:
        # DeepSeek 兼容 OpenAI 的 response_format（json_object 模式）
        model_kwargs["response_format"] = {"type": "json_object"}

    llm = ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature,
        model_kwargs=model_kwargs,
        timeout=120,
        max_retries=LLM_MAX_RETRIES,  # LangChain 内置网络重试
    )
    # 链式调用：ChatOpenAI | StrOutputParser，体现 LangChain 的 Chain 思想
    chain = llm | StrOutputParser()
    lc_messages = _normalize_messages(messages)
    logger.info(
        "LLM 调用开始（LangChain）：model=%s json_mode=%s 提示词字符数=%d",
        DEEPSEEK_MODEL, json_mode, _prompt_chars(messages),
    )
    content = chain.invoke(lc_messages)
    logger.info(
        "LLM 调用完成（LangChain）：耗时=%.0fms 输出长度=%d",
        (time.perf_counter() - start) * 1000, len(content or ""),
    )
    return content


def _run_openai(messages: list, *, temperature: float, json_mode: bool,
                start: float) -> str:
    """openai SDK 直连兜底链路。"""
    client = _get_client()
    raw = [{"role": "system" if isinstance(m, dict) and m.get("role") == "system"
            else "user", "content": m.get("content", "")} for m in messages
           if isinstance(m, dict)]
    kwargs = {"model": DEEPSEEK_MODEL, "messages": raw, "temperature": temperature}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    logger.info(
        "LLM 调用开始（openai SDK 兜底）：model=%s json_mode=%s 提示词字符数=%d",
        DEEPSEEK_MODEL, json_mode, _prompt_chars(messages),
    )
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    logger.info(
        "LLM 调用完成（openai SDK）：耗时=%.0fms 输出长度=%d",
        (time.perf_counter() - start) * 1000, len(content or ""),
    )
    return content


def _call_llm(messages: list, *, temperature: float, json_mode: bool) -> str:
    """统一的 LLM 调用：自动重试 + 降级兜底，三层保障。

    1) 优先 LangChain（ChatOpenAI 自带 max_retries 网络重试）
    2) LangChain 失败自动回退 openai SDK 直连
    3) 整体仍失败时按 LLM_MAX_RETRIES 指数退避重试

    全部重试耗尽后抛出最后一次异常。
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY，请在 .env 中填写后重启服务"
        )
    start = time.perf_counter()
    last_error: Exception | None = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        # --- 1) LangChain 主链路 ---
        if USE_LANGCHAIN:
            try:
                return _run_langchain(messages, temperature=temperature,
                                      json_mode=json_mode, start=start)
            except Exception as e:
                logger.warning(
                    "LangChain 调用失败（%s: %s），回退 openai SDK",
                    type(e).__name__, e,
                )
        # --- 2) openai SDK 兜底链路 ---
        try:
            return _run_openai(messages, temperature=temperature,
                               json_mode=json_mode, start=start)
        except Exception as e:
            last_error = e
            logger.warning(
                "LLM 调用失败（第 %d/%d 次）：%s: %s",
                attempt, LLM_MAX_RETRIES, type(e).__name__, e,
            )
            if attempt < LLM_MAX_RETRIES:
                time.sleep(0.5 * attempt)  # 指数退避：0.5s → 1s → ...
    raise last_error


def chat_completion(messages: list, temperature: float = 0.7) -> str:
    """普通对话调用，返回字符串。"""
    return _call_llm(messages, temperature=temperature, json_mode=False)


def chat_json(messages: list, temperature: float = 0.3) -> str:
    """强制 JSON 结构化输出（意图识别、NL2SQL 均使用）。"""
    return _call_llm(messages, temperature=temperature, json_mode=True)
