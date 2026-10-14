"""banyan 编排事件行透传单测（openai 转发路径，FORKING.md §2）。

本仓库尚无后端测试基建（无现成 openai 路由测试模式、后端依赖树未装），
按"最小测试"原则：
- 以 importlib 直载 ``open_webui/utils/banyan_stream.py``（纯标准库模块，
  不经 open_webui 包 __init__，避免拉起完整后端依赖树）；
- 用假上游 SSE 逐行驱动 ``banyan_passthrough_wrapper``（openai.py
  generate_chat_completion 流式返回所包的真实包装器）；
- 按 middleware 流处理循环（utils/middleware.py streaming_chat_response_handler）
  解析 SSE 行的同一套步骤解析改写行，断言其 'event' 载荷即前端
  socket 事件 ``{'type':'banyan','data':<原样>}``（与 status 同通道，
  Chat.svelte 钩点①按 type === 'banyan' 消费）。

运行：cd backend && python3 -m pytest tests/test_banyan_passthrough.py -q
"""

import asyncio
import importlib.util
import json
import pathlib
import types

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'utils' / 'banyan_stream.py'
)


def _load_banyan_stream() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location('banyan_stream_under_test', _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bs = _load_banyan_stream()


async def _fake_upstream(lines):
    for line in lines:
        yield line


def _collect(lines):
    """Drive the wrapper over a fake upstream, return emitted chunks."""

    async def run():
        return [chunk async for chunk in bs.banyan_passthrough_wrapper(_fake_upstream(lines))]

    return asyncio.run(run())


def _as_sse_event(chunk):
    """Replicate middleware's SSE consumption: data: prefix strip + JSON parse."""
    line = chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
    assert line.startswith('data:')
    return json.loads(line[len('data:') :].strip())


BANYAN_PLAN = {'type': 'plan', 'plan_id': 'plan-mock-001', 'status': 'pending'}
STANDARD_CHUNK = (
    b'data: {"id":"cmpl-1","object":"chat.completion.chunk",'
    b'"choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}\n'
)


def test_banyan_line_rewritten_to_event_wire_format():
    """假上游 SSE 含 banyan 行 → 改写为事件通道线格式，其余行逐字节原样。"""
    banyan_line = b'data:{"banyan":{"type":"plan","plan_id":"plan-mock-001","status":"pending"}}\n'
    upstream = [STANDARD_CHUNK, banyan_line, b'\n', b'data: [DONE]\n']

    out = _collect(upstream)

    assert len(out) == len(upstream)  # 行数一致：不吞行、不增行
    assert out[0] == STANDARD_CHUNK  # 标准 chunk 原样
    assert out[1] == (
        b'data: {"event":{"type":"banyan","data":{"type":"plan","plan_id":"plan-mock-001","status":"pending"}}}\n'
    )
    assert out[2] == b'\n'  # SSE 分隔行原样
    assert out[3] == b'data: [DONE]\n'


def test_rewritten_line_yields_frontend_socket_event_payload():
    """按 middleware 消费步骤解析改写行 → 前端收到 {'type':'banyan','data':<原样>}。"""
    banyan_payload = {'type': 'wave_update', 'plan_id': 'p1', 'tasks': [{'task_id': 't1', 'status': 'running'}]}
    upstream = [f'data:{json.dumps({"banyan": banyan_payload}, ensure_ascii=False)}\n'.encode('utf-8')]

    (chunk,) = _collect(upstream)
    data = _as_sse_event(chunk)

    # middleware: `if 'event' in data: await event_emitter(data.get('event', {}))`
    assert 'event' in data
    emitted = data['event']
    assert emitted['type'] == 'banyan'
    assert emitted['data'] == banyan_payload  # 载荷原样，无键改写


def test_malformed_and_foreign_lines_never_error():
    """坏 JSON / 非 banyan / 空行 / 无换行尾行：一律原样透传，不进错误路径。"""
    upstream = [
        b'data:{"banyan":{broken json\n',  # 坏 JSON 的疑似行
        b'data: {"choices":[]}\n',  # 无 banyan 键
        b'data:{"other":{"x":1}}\n',
        b'\n',
        b'event: ping\n',  # 非 data: 行
        b'data: {"trailing chunk',  # 无行尾的截断行（流中断形态）
    ]

    out = _collect(upstream)

    assert out == upstream  # 全部逐字节原样，无异常


def test_banyan_non_object_value_still_wrapped():
    """banyan 键的值非对象时也按原样包进事件载荷（消费端 unwrapBanyanEvent 自行判型）。"""
    (chunk,) = _collect([b'data:{"banyan":"scalar-is-fine"}\n'])

    assert _as_sse_event(chunk) == {'event': {'type': 'banyan', 'data': 'scalar-is-fine'}}


def test_streaming_is_line_by_line_immediate():
    """逐行即时：上游只发出第 1 行且不结束时，包装器即刻产出第 1 行（不缓冲整段）。"""

    async def stalling_upstream():
        yield b'data:{"banyan":{"type":"tool","call_id":"c1","status":"running"}}\n'
        await asyncio.sleep(3600)  # 模拟上游仍在前两行之间，永不主动结束

    async def scenario():
        wrapper = bs.banyan_passthrough_wrapper(stalling_upstream())
        first = await asyncio.wait_for(wrapper.__anext__(), timeout=1.0)
        assert first.startswith(b'data: {"event":{"type":"banyan","data":{"type":"tool"')
        return wrapper

    wrapper = asyncio.run(scenario())
    asyncio.run(wrapper.aclose())


def test_crlf_and_utf8_payload_preserved():
    """\r\n 行尾与中文载荷：JSON 语义原样，行尾保持。"""
    line = 'data:{"banyan":{"type":"subagent","title":"评审者"}}\r\n'.encode('utf-8')

    (chunk,) = _collect([line])

    assert chunk.endswith(b'}\r\n')
    data = _as_sse_event(chunk)
    assert data['event'] == {'type': 'banyan', 'data': {'type': 'subagent', 'title': '评审者'}}


def test_strip_banyan_lines_for_non_streaming_body():
    """非流式：混入正文的 banyan 行被忽略（剥离），剥离后正文仍是合法 JSON。"""
    body = '{"choices":[{"message":{"content":"ok"}}]}\ndata:{"banyan":{"type":"branch"}}\n'

    stripped = bs.strip_banyan_sse_lines(body)

    assert json.loads(stripped) == {'choices': [{'message': {'content': 'ok'}}]}
    assert 'banyan' not in stripped


def test_strip_banyan_lines_fast_path_untouched():
    """正文不含 banyan 行时原串返回（不动非流式正常路径）。"""
    body = '{"choices":[{"message":{"content":"ok"}}]}'

    assert bs.strip_banyan_sse_lines(body) == body


def test_openai_route_wiring():
    """openai.py 转发路径确实接入包装器：流式包裹、非流式剥离。"""
    source = (
        pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'routers' / 'openai.py'
    ).read_text(encoding='utf-8')

    assert 'from open_webui.utils.banyan_stream import banyan_passthrough_wrapper, strip_banyan_sse_lines' in source
    assert 'banyan_passthrough_wrapper(stream_wrapper(r))' in source  # 流式：SSE 行改写
    assert 'strip_banyan_sse_lines(response)' in source  # 非流式：忽略 banyan 行
