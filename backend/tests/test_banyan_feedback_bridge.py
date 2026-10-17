"""banyan 评分桥单测(F15 / D22)。

importlib 直载 ``open_webui/routers/evaluations.py``(open_webui.* 以桩注入;
models/feedbacks 与 utils/banyan_chat_adapter 载真实文件,保真实 FeedbackForm/
RatingData/SnapshotData/FeedbackModel 形状与 sess_ 判定),引擎 HTTP 以假
httpx 桩掉。

覆盖(D22 契约):
- sess_* 会话评分 → POST 引擎 /api/feedback(conv_id/message_row_id/rating/
  reason;reason 缺省时 details 摘要),成功返回合成 FeedbackModel(id='fbx-*'),
  fork feedback 表零写入(写即炸桩证明);
- 非 sess_ 存量会话 → 原路径零改(Feedbacks.insert 被调,引擎零调用);
- snapshot.chat(竞技场快照)不桥接,走原路径;
- 引擎不可达/5xx → 502 且不沉库(可重试);引擎 404(未知 conv)原码透传;
- update 路径同桥(fork 无 fbx 行可更,引擎按 conv/message 幂等落账)。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_feedback_bridge.py -q
"""

import asyncio
import importlib.util
import json
import pathlib
import sys
import types

from pydantic import BaseModel
from sqlalchemy import JSON as _JSON
from sqlalchemy.orm import declarative_base as _declarative_base

# 先经真实包解析预载 chat_id:本文件注入的 open_webui.* 桩是非包模块,
# 会遮蔽真实包的子模块解析;test_banyan_conv/chat_adapter 直载 banyan_conv
# 时按真包导入 open_webui.utils.chat_id——先入 sys.modules 即不受桩影响。
import open_webui.utils.chat_id  # noqa: F401  # noqa: E402

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _load_module(path: pathlib.Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _stub(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _run(coro):
    return asyncio.run(coro)


# ── 真实 models/feedbacks(形状正本)──


async def _nop(*a, **k):
    return None


_db = _stub('open_webui.internal.db', Base=_declarative_base(), JSONField=_JSON, get_async_db_context=None, get_async_session=None)
_users = _stub('open_webui.models.users', User=object, UserModel=object, Users=types.SimpleNamespace())
_stub('open_webui')
_stub('open_webui.models')
_real_feedbacks = _load_module(_BACKEND / 'open_webui' / 'models' / 'feedbacks.py', 'open_webui_models_feedbacks_under_test')
sys.modules['open_webui.models.feedbacks'] = _real_feedbacks

# ── 真实 banyan_chat_adapter(is_engine_chat)──
sys.modules['open_webui.utils.banyan_chat_adapter'] = _load_module(
    _BACKEND / 'open_webui' / 'utils' / 'banyan_chat_adapter.py', 'banyan_chat_adapter_under_test'
)

# ── evaluations 其余依赖桩 ──
_EVENTS = types.SimpleNamespace(
    FEEDBACK_CREATED='feedback.created',
    FEEDBACK_UPDATED='feedback.updated',
    FEEDBACK_DELETED='feedback.deleted',
    FEEDBACK_DELETED_ALL='feedback.deleted_all',
)
_PUBLISHED = []


async def _publish_event(*args, **kwargs):
    _PUBLISHED.append(kwargs)


_stub('open_webui.constants', ERROR_MESSAGES=types.SimpleNamespace(DEFAULT=lambda **k: 'error', NOT_FOUND='not found', UNAUTHORIZED='unauthorized'))
_stub('open_webui.env', MPS_INFERENCE_LOCK=None, USE_SLIM=True)
_stub('open_webui.events', EVENTS=_EVENTS, publish_event=_publish_event)
_stub('open_webui.retrieval')
_stub('open_webui.retrieval.utils', cosine_similarity=lambda *a, **k: 0.0)
_stub('open_webui.models.config', Config=types.SimpleNamespace())
_stub('open_webui.utils')
_stub('open_webui.utils.auth', get_verified_user=lambda: None, get_admin_user=lambda: None)

ev = _load_module(_BACKEND / 'open_webui' / 'routers' / 'evaluations.py', 'evaluations_router_under_test')

USER = types.SimpleNamespace(id='u1', role='admin', name='Owner')
REAL_HTTPX = ev.httpx

# ── fork 表写桩(boom=写即炸;记录=原路径回显)──


class _StubFeedbacks:
    boom = True
    calls = []
    result = None

    @classmethod
    async def insert_new_feedback(cls, user_id, form_data, db=None):
        cls.calls.append(('insert', user_id))
        if cls.boom:
            raise AssertionError('fork feedback 表被写(D22 要求零写入)')
        return cls.result

    @classmethod
    async def update_feedback_by_id(cls, id, form_data, db=None):
        cls.calls.append(('update', id))
        if cls.boom:
            raise AssertionError('fork feedback 表被写(D22 要求零写入)')
        return cls.result

    @classmethod
    async def update_feedback_by_id_and_user_id(cls, id, user_id, form_data, db=None):
        cls.calls.append(('update_as_user', id))
        if cls.boom:
            raise AssertionError('fork feedback 表被写(D22 要求零写入)')
        return cls.result


ev.Feedbacks = _StubFeedbacks


class _Resp:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self):
        return self._payload


_CAPS = []


def _install_httpx(outcomes):
    """假 httpx:post 按 outcomes 逐个回放(异常原样抛);调用进 _CAPS。"""
    _CAPS.clear()
    outcomes = list(outcomes)

    class _Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            _CAPS.append({'url': url, 'headers': headers, 'json': json})
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    ev.httpx = types.SimpleNamespace(
        AsyncClient=_Client, Timeout=lambda t: t, HTTPError=REAL_HTTPX.HTTPError, ConnectError=REAL_HTTPX.ConnectError
    )


def _form(chat_id='sess_abc', message_id='row1', snapshot=None, **data_kwargs):
    return _real_feedbacks.FeedbackForm(
        type='rating',
        data=_real_feedbacks.RatingData(**{'rating': -1, 'model_id': 'banyan-duty', **data_kwargs}),
        meta={'chat_id': chat_id, 'message_id': message_id} if chat_id else {'note': 'legacy'},
        snapshot=snapshot,
    )


# ── sess_* → 引擎 ──


def test_sess_rating_posts_to_engine_and_synthesizes():
    _StubFeedbacks.boom = True  # fork 表写即炸:桥接路径必须零写入
    _install_httpx([_Resp(200, {'ok': True})])
    feedback = _run(ev.create_feedback(request=None, form_data=_form(reason='答错了'), user=USER, db=None))

    assert len(_CAPS) == 1
    body = _CAPS[0]['json']
    assert body == {'conv_id': 'sess_abc', 'message_row_id': 'row1', 'rating': -1, 'reason': '答错了'}
    assert _CAPS[0]['url'].endswith('/api/feedback')
    assert feedback.id.startswith('fbx-')  # 合成回显,不落 fork 表
    assert feedback.type == 'rating' and feedback.data['rating'] == -1
    assert feedback.meta == {'chat_id': 'sess_abc', 'message_id': 'row1'}
    assert feedback.snapshot is None
    assert _StubFeedbacks.calls == []  # 零 fork 表写入
    assert _PUBLISHED == []  # 桥接路径不发 fork 事件(引擎侧自有事件流)


def test_reason_falls_back_to_details_summary():
    _install_httpx([_Resp(200, {'ok': True})])
    feedback = _run(ev.create_feedback(request=None, form_data=_form(details={'issues': '错', 'n': 2}), user=USER, db=None))
    body = _CAPS[0]['json']
    assert body['reason'] == json.dumps({'issues': '错', 'n': 2}, ensure_ascii=False)  # details 摘要
    assert feedback.id.startswith('fbx-')


def test_sess_rating_long_reason_truncated_is_engine_side_not_required():
    """reason 透传不截断(200 字截断只用于 details 摘要路径)。"""
    _install_httpx([_Resp(200, {'ok': True})])
    _run(ev.create_feedback(request=None, form_data=_form(reason='长' * 300), user=USER, db=None))
    assert len(_CAPS[0]['json']['reason']) == 300


# ── 非 sess_ 存量 → 原路径零改 ──


def test_legacy_chat_goes_original_path():
    _StubFeedbacks.boom = False
    _StubFeedbacks.calls = []
    _StubFeedbacks.result = _real_feedbacks.FeedbackModel(
        id='fb-legacy', user_id='u1', version=0, type='rating', data={'rating': -1}, meta={}, created_at=1, updated_at=1
    )
    _install_httpx([])  # 引擎零调用
    feedback = _run(ev.create_feedback(request=None, form_data=_form(chat_id='old-local-chat'), user=USER, db=None))

    assert feedback.id == 'fb-legacy'  # 原路径产物,非合成
    assert _StubFeedbacks.calls == [('insert', 'u1')]
    assert _CAPS == []


def test_snapshot_chat_not_bridged():
    _StubFeedbacks.boom = False
    _StubFeedbacks.calls = []
    _StubFeedbacks.result = _real_feedbacks.FeedbackModel(id='fb-snap', user_id='u1', version=0, type='rating', created_at=1, updated_at=1)
    _install_httpx([])
    feedback = _run(ev.create_feedback(request=None, form_data=_form(snapshot={'chat': {'id': 'arena'}}), user=USER, db=None))
    assert feedback.id == 'fb-snap'  # 竞技场快照走原路径
    assert _CAPS == []


# ── 引擎不可达/错误 → 502/透传,不沉库 ──


def test_engine_unreachable_maps_502_without_sinking():
    _StubFeedbacks.boom = True
    _StubFeedbacks.calls = []
    _install_httpx([REAL_HTTPX.ConnectError('connection refused')])
    import fastapi

    try:
        _run(ev.create_feedback(request=None, form_data=_form(), user=USER, db=None))
        raise AssertionError('expected 502')
    except fastapi.HTTPException as e:
        assert e.status_code == 502
    assert _StubFeedbacks.calls == []  # 不沉库,可重试


def test_engine_5xx_maps_502():
    _install_httpx([_Resp(500, {'detail': 'boom'})])
    import fastapi

    try:
        _run(ev.create_feedback(request=None, form_data=_form(), user=USER, db=None))
        raise AssertionError('expected 502')
    except fastapi.HTTPException as e:
        assert e.status_code == 502


def test_engine_unknown_conv_404_propagates():
    _install_httpx([_Resp(404, {'detail': 'conv not found'})])
    import fastapi

    try:
        _run(ev.create_feedback(request=None, form_data=_form(), user=USER, db=None))
        raise AssertionError('expected 404')
    except fastapi.HTTPException as e:
        assert e.status_code == 404 and 'conv not found' in e.detail


# ── update 路径同桥 ──


def test_update_feedback_bridges_for_engine_chats():
    _StubFeedbacks.boom = True
    _StubFeedbacks.calls = []
    _install_httpx([_Resp(200, {'ok': True})])
    feedback = _run(ev.update_feedback_by_id(request=None, id='fbx-prev', form_data=_form(rating=1, reason='改好评'), user=USER, db=None))
    assert _CAPS[0]['json'] == {'conv_id': 'sess_abc', 'message_row_id': 'row1', 'rating': 1, 'reason': '改好评'}
    assert feedback.id.startswith('fbx-')
    assert _StubFeedbacks.calls == []  # fork 无 fbx 行可更:零写入
