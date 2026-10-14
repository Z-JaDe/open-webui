"""banyan 编排事件行透传（fork 定制，见 FORKING.md §2）。

banyan 引擎在标准 OpenAI chunk 之外，于 SSE 正文混入私有行
``data:{"banyan":{...}}``（渲染协议，权威 schema 见
``src/lib/components/banyan/types.ts``）。标准 OpenAI 客户端与
middleware 的 chunk 处理都不认识它们——本模块负责把这类行改写成
Open WebUI 既有的事件通道线格式 ``data:{"event":{"type":"banyan","data":{...}}}``：
middleware 的流处理循环会将其经 event_emitter 推给前端 socket，
Chat.svelte 事件分发段（钩点①）按 ``type === 'banyan'`` 消费，
与 ``status`` 同一机制。

设计约束：
- 逐行即时：包装器对上游逐行（stream_chunks_handler 已按行对齐）
  判定并立即产出，不缓冲整段流；
- 绝不触发错误路径：无法解析的行、非 banyan 行一律原样透传；
- 非流式路径不转发编排事件（``strip_banyan_sse_lines`` 供其剥离）。

本模块仅依赖标准库，保证可在无后端依赖树的环境下单测。
"""

from __future__ import annotations

import json
from typing import AsyncIterator, Union

StreamChunk = Union[bytes, bytearray, str]

_BANYAN_EVENT_TYPE = 'banyan'


def _sse_line_payload(text: str) -> Union[str, None]:
    """Return the payload of an SSE ``data:`` line, or None if not one."""
    stripped = text.strip()
    if not stripped.startswith('data:'):
        return None
    payload = stripped[len('data:') :].strip()
    return payload or None


def _line_terminator(text: str) -> str:
    """Return the original trailing newline of *text* (SSE framing preserved)."""
    if text.endswith('\r\n'):
        return '\r\n'
    if text.endswith('\n') or text.endswith('\r'):
        return text[-1]
    return ''


def rewrite_banyan_sse_line(line: StreamChunk) -> Union[str, None]:
    """Rewrite a banyan private SSE line into the frontend event wire format.

    ``data:{"banyan":{...}}`` → ``data:{"event":{"type":"banyan","data":{...}}}``.

    Returns the replacement text (original newline preserved), or None when
    the line is not a banyan line — including undecodable or malformed JSON
    lines, which are meant to pass through untouched, never to raise.
    """
    try:
        text = line.decode('utf-8', 'replace') if isinstance(line, (bytes, bytearray)) else line
    except Exception:
        return None

    payload = _sse_line_payload(text)
    if not payload or payload == '[DONE]':
        return None

    try:
        parsed = json.loads(payload)
    except Exception:
        return None

    if not isinstance(parsed, dict) or 'banyan' not in parsed:
        return None

    event = {'event': {'type': _BANYAN_EVENT_TYPE, 'data': parsed['banyan']}}
    body = json.dumps(event, ensure_ascii=False, separators=(',', ':'))
    return f'data: {body}{_line_terminator(text)}'


async def banyan_passthrough_wrapper(stream: AsyncIterator[StreamChunk]) -> AsyncIterator[StreamChunk]:
    """Wrap an upstream SSE line stream, forwarding banyan lines as events.

    Consumed line by line: every line is inspected and yielded immediately,
    keeping the stream unbuffered. Lines that are not banyan private lines
    (standard chunks, ``[DONE]``, separators, malformed JSON) are yielded
    byte-identical.
    """
    async for line in stream:
        rewritten = rewrite_banyan_sse_line(line)
        if rewritten is not None:
            yield rewritten.encode('utf-8')
        else:
            yield line


def strip_banyan_sse_lines(text: str) -> str:
    """Drop banyan private SSE lines from a full non-streaming body.

    Used by the non-streaming response path: orchestration events are
    ignored there (never forwarded), and a JSON body that upstream
    polluted with banyan lines parses again after stripping.
    """
    if '"banyan"' not in text:
        return text
    return ''.join(
        line for line in text.splitlines(keepends=True) if rewrite_banyan_sse_line(line) is None
    )
