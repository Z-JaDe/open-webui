"""banyan conv 绑定单测（P0 会话映射，FORKING.md §3b）。

与 test_banyan_passthrough.py 同款"最小测试"原则：importlib 直载
``open_webui/utils/banyan_conv.py``（模块顶部只依赖 httpx 与纯标准库的
chat_id 判定），``open_webui.models.chats`` 的 import 在函数体内 lazy 发生——
测试向 sys.modules 注入桩模块即可隔离 WebUI 库；引擎 API 以假 _engine_call 桩掉。

覆盖：
- is_banyan_target origin 判定（引擎 /v1 连接、host 写法差异、空值）；
- resolve_conv_header 三道闸：非引擎目标 / 后台任务轮 / 未落库 chat id；
- 首条消息建会话+回写 meta，同 chat 二次解析直接命中绑定（不再打引擎）。

运行：cd backend && python3 -m pytest tests/test_banyan_conv.py -q
"""

import asyncio
import importlib.util
import pathlib
import sys
import types

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'utils' / 'banyan_conv.py'
)


def _load_banyan_conv() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location('banyan_conv_under_test', _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bc = _load_banyan_conv()

ENGINE = 'http://127.0.0.1:8000'
ENGINE_V1 = 'http://127.0.0.1:8000/v1'


class _Resp:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class _ChatRow:
    def __init__(self, meta):
        self.meta = meta


class _FakeChats:
    """chat 行存储桩：persist 由模块的 update_chat_meta_by_id 桩直接改 store。"""

    def __init__(self):
        self.store: dict[str, dict] = {}

    async def get_chat_by_id(self, chat_id):
        meta = self.store.get(chat_id)
        return None if meta is None else _ChatRow(dict(meta))


def _install_fake_chats(monkeypatch, fake):
    stub = types.ModuleType('open_webui.models.chats')
    stub.Chats = fake
    monkeypatch.setitem(sys.modules, 'open_webui.models.chats', stub)
    # 回写走模块内 _persist_conv_binding 的真实逻辑 -> 桩掉 DB 层
    async def _persist(chat_id, conv_id):
        fake.store.setdefault(chat_id, {})[bc.META_KEY] = conv_id
        return True

    monkeypatch.setattr(bc, '_persist_conv_binding', _persist)


def _install_engine(monkeypatch, responses):
    """按 (method, path 前缀) 顺序消费的引擎桩；记录调用供计数。"""
    calls: list[tuple[str, str]] = []

    async def _engine_call(method, path, **kwargs):
        calls.append((method, path))
        for i, (m, prefix, resp) in enumerate(responses):
            if m == method and path.startswith(prefix):
                responses.pop(i)
                return resp
        return _Resp(404, {'detail': 'no route'})

    monkeypatch.setattr(bc, '_engine_call', _engine_call)
    return calls


# ── is_banyan_target ──


def test_is_banyan_target_origin_match(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    assert bc.is_banyan_target(ENGINE_V1) is True
    assert bc.is_banyan_target(ENGINE) is True
    assert bc.is_banyan_target('http://localhost:8000/v1') is False  # host 写法不同
    assert bc.is_banyan_target('http://127.0.0.1:9999/v1') is False
    assert bc.is_banyan_target('') is False


# ── resolve_conv_header 三道闸 ──


def test_header_skips_non_engine_target(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    out = asyncio.run(
        bc.resolve_conv_header({'chat_id': 'chat-1'}, 'http://api.openai.com/v1')
    )
    assert out is None


def test_header_skips_task_rounds(monkeypatch):
    """后台任务轮(title/tags/query 等)不映射——防任务 prompt 污染绑定会话正本。"""
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    out = asyncio.run(
        bc.resolve_conv_header(
            {'chat_id': 'chat-1', 'task': 'title_generation'}, ENGINE_V1
        )
    )
    assert out is None


def test_header_skips_unsaved_chat_ids(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    for chat_id in ('local:abc', 'temporary:def', 'channel:x', None):
        out = asyncio.run(bc.resolve_conv_header({'chat_id': chat_id}, ENGINE_V1))
        assert out is None


# ── 建会话 + 绑定缓存 ──


def test_first_turn_creates_session_and_binds(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    fake = _FakeChats()
    fake.store['chat-1'] = {}
    _install_fake_chats(monkeypatch, fake)
    calls = _install_engine(monkeypatch, [
        ('GET', '/api/projects', _Resp(200, [
            {'key': '/private/w', 'name': 'workspace', 'sort_order': 0},
            {'key': '/other', 'name': 'other', 'sort_order': 5},
        ])),
        ('POST', '/api/projects/%2Fprivate%2Fw/sessions',
         _Resp(200, {'id': 'sess_abc123'})),
    ])

    conv = asyncio.run(bc.resolve_conv_header({'chat_id': 'chat-1'}, ENGINE_V1))
    assert conv == 'sess_abc123'
    assert ('POST', '/api/projects/%2Fprivate%2Fw/sessions') in calls
    assert fake.store['chat-1'][bc.META_KEY] == 'sess_abc123'

    # 同 chat 二次解析：直接命中 meta 绑定，不再打引擎
    conv2 = asyncio.run(bc.resolve_conv_header({'chat_id': 'chat-1'}, ENGINE_V1))
    assert conv2 == 'sess_abc123'
    assert calls.count(('POST', '/api/projects/%2Fprivate%2Fw/sessions')) == 1


def test_engine_unreachable_degrades_to_none(monkeypatch):
    """引擎不可达 → None（调用方不注入头，降级为引擎默认实例，不抛错）。"""
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    fake = _FakeChats()
    fake.store['chat-2'] = {}
    _install_fake_chats(monkeypatch, fake)

    async def _boom(method, path, **kwargs):
        raise OSError('engine unreachable')

    monkeypatch.setattr(bc, '_engine_call', _boom)
    out = asyncio.run(bc.resolve_conv_header({'chat_id': 'chat-2'}, ENGINE_V1))
    assert out is None


def test_missing_chat_row_returns_none(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    _install_fake_chats(monkeypatch, _FakeChats())
    out = asyncio.run(bc.resolve_conv_header({'chat_id': 'ghost'}, ENGINE_V1))
    assert out is None
