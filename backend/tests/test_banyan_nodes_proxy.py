"""banyan 设备互感知代理桥单测(C3b:nodes* 路由经 /banyan/api 1:1 转发)。

同仓"最小测试"模式(test_banyan_conv.py / test_banyan_feedback_bridge.py):
importlib 直载真实 ``open_webui/routers/banyan.py``(open_webui.utils.auth 桩注入、
banyan_bridge 载真实纯模块),httpx 以假 AsyncClient 桩掉(build_request/send
捕获转发实参)——直接驱动 catch-all ``banyan_proxy``,断言 C3 协议四动词
(GET/POST nodes、POST nodes/{id}/commands、DELETE nodes/{id})的
转发路径、方法、body、鉴权头(静态 token 替换 / 透传两模式)与响应回传。

C3 网络路径背景(goal-cloud 协议锁定):管理面走 webui 用户 JWT 墙 →
/banyan/api/nodes* 通配桥 → 引擎 /api/nodes*;节点自身心跳走 Caddy
/engine/* 直连引擎,不经本桥。本测试即"引擎新增 /api/nodes* 端点、
webui 后端零改动即可达前端"的回归钉子。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_nodes_proxy.py -q
"""

import asyncio
import importlib.util
import pathlib
import sys
import types

import httpx as _real_httpx
from fastapi import HTTPException

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


# ── 依赖桩:auth 桩掉(不拉后端依赖树);banyan_bridge 载真实纯模块 ──
_stub('open_webui')
_stub('open_webui.utils')
_stub('open_webui.utils.auth', get_verified_user=lambda: None)
sys.modules['open_webui.utils.banyan_bridge'] = _load_module(
    _BACKEND / 'open_webui' / 'utils' / 'banyan_bridge.py',
    'banyan_bridge_under_test',
)

banyan = _load_module(
    _BACKEND / 'open_webui' / 'routers' / 'banyan.py', 'banyan_router_under_test'
)

ENGINE = 'http://127.0.0.1:8000'
USER = types.SimpleNamespace(id='u1', role='admin')


# ── 假 httpx:build_request 捕获转发实参,send 回放预设响应 ──

_CAP: list[dict] = []
_OUTCOMES: list = []


class _FakeAsyncClient:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.closed = False

    def build_request(self, method, url, params=None, headers=None, content=None):
        req = {
            'method': method,
            'url': url,
            'params': dict(params or {}),
            'headers': dict(headers or {}),
            'content': content,
        }
        _CAP.append(req)
        return req

    async def send(self, request, stream=False):
        outcome = _OUTCOMES.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def aclose(self):
        self.closed = True


def _install_httpx(outcomes):
    _CAP.clear()
    _OUTCOMES.clear()
    _OUTCOMES.extend(outcomes)
    banyan.httpx = types.SimpleNamespace(
        AsyncClient=_FakeAsyncClient,
        Timeout=lambda *a, **k: None,
        ConnectError=_real_httpx.ConnectError,
        HTTPError=_real_httpx.HTTPError,
    )


class _FakeResponse:
    def __init__(self, status_code=200, body=b'{"ok": true}', headers=None):
        self.status_code = status_code
        self.headers = headers or {'content-type': 'application/json'}
        self._body = body

    async def aiter_bytes(self):
        yield self._body

    async def aclose(self):
        pass


class _CIDict(dict):
    """大小写不敏感 get(Starlette Headers 语义的最小仿真)。"""

    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == str(key).lower():
                return v
        return default


class _FakeRequest:
    def __init__(self, method='GET', headers=None, query=None, body=b''):
        self.method = method
        self.headers = _CIDict(headers or {})
        self.query_params = dict(query or {})
        self._body = body

    async def body(self):
        return self._body


def _proxy(path, request, static_token=''):
    """以指定鉴权模式驱动 catch-all(模块常量为调用时读,BANYAN_TOKEN 可换)。"""
    banyan.BANYAN_ENGINE_URL = ENGINE
    banyan.BANYAN_TOKEN = static_token
    return asyncio.run(banyan.banyan_proxy(path=path, request=request, user=USER))


def _drain(response):
    async def run():
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        return b''.join(chunks)

    return asyncio.run(run())


WEBUI_JWT_HEADERS = {
    'Authorization': 'Bearer webui-user-jwt',
    'content-type': 'application/json',
    'cookie': 'token=webui-session',
}


# ── C3 协议四动词:转发路径 + 鉴权头(静态 token 模式,云端部署形态)──


def test_nodes_list_get_forwarded_with_static_token():
    """GET /banyan/api/nodes → 引擎 GET /api/nodes;webui JWT 被静态 token 替换。"""
    _install_httpx([_FakeResponse(200, b'[{"node_id":"n1","online":true}]')])
    resp = _proxy('nodes', _FakeRequest('GET', WEBUI_JWT_HEADERS), static_token='engine-static')

    (req,) = _CAP
    assert req['method'] == 'GET'
    assert req['url'] == f'{ENGINE}/api/nodes'
    assert req['headers']['Authorization'] == 'Bearer engine-static'
    assert 'webui-user-jwt' not in req['headers'].get('Authorization', '')
    assert 'cookie' not in req['headers']  # 会话 cookie 不出桥
    assert req['headers']['content-type'] == 'application/json'
    assert resp.status_code == 200
    assert _drain(resp) == b'[{"node_id":"n1","online":true}]'  # 响应体原样回传


def test_register_node_post_forwarded_with_body():
    """POST /banyan/api/nodes {name} → 引擎 /api/nodes,body 原样(node_token 回执由此过桥)。"""
    body = b'{"name": "Mac-mini"}'
    _install_httpx([_FakeResponse(200, b'{"node_id":"n1","node_token":"once"}')])
    resp = _proxy(
        'nodes',
        _FakeRequest('POST', WEBUI_JWT_HEADERS, body=body),
        static_token='engine-static',
    )

    (req,) = _CAP
    assert req['method'] == 'POST'
    assert req['url'] == f'{ENGINE}/api/nodes'
    assert req['content'] == body
    assert req['headers']['Authorization'] == 'Bearer engine-static'
    assert resp.status_code == 200
    assert _drain(resp) == b'{"node_id":"n1","node_token":"once"}'


def test_node_commands_post_forwarded():
    """POST /banyan/api/nodes/{id}/commands {kind,payload} → 路径 1:1、body 原样。"""
    body = b'{"kind": "chat_turn", "payload": {"text": "hi"}}'
    _install_httpx([_FakeResponse(200, b'{"command_id": "cmd-9"}')])
    resp = _proxy(
        'nodes/mac-node-1/commands',
        _FakeRequest('POST', WEBUI_JWT_HEADERS, body=body),
        static_token='engine-static',
    )

    (req,) = _CAP
    assert req['method'] == 'POST'
    assert req['url'] == f'{ENGINE}/api/nodes/mac-node-1/commands'
    assert req['content'] == body
    assert resp.status_code == 200
    assert _drain(resp) == b'{"command_id": "cmd-9"}'


def test_delete_node_forwarded():
    """DELETE /banyan/api/nodes/{id} → 引擎 DELETE /api/nodes/{id}(吊销走同一动词)。"""
    _install_httpx([_FakeResponse(200, b'{"deleted": true}')])
    resp = _proxy(
        'nodes/mac-node-1',
        _FakeRequest('DELETE', WEBUI_JWT_HEADERS),
        static_token='engine-static',
    )

    (req,) = _CAP
    assert req['method'] == 'DELETE'
    assert req['url'] == f'{ENGINE}/api/nodes/mac-node-1'
    assert resp.status_code == 200


def test_engine_error_status_passthrough():
    """引擎 4xx/5xx 原码透传(前端 error 三态靠它,不被桥吞成 500)。"""
    _install_httpx([_FakeResponse(404, b'{"detail": "node not found"}')])
    resp = _proxy('nodes/ghost', _FakeRequest('DELETE', WEBUI_JWT_HEADERS), static_token='t')
    assert resp.status_code == 404
    assert _drain(resp) == b'{"detail": "node not found"}'


# ── 鉴权两模式:未设 BANYAN_TOKEN 时透传前端自带头 ──


def test_passthrough_mode_keeps_client_authorization():
    """BANYAN_TOKEN 未设(本地开发形态):webui 用户 JWT 原样透传给引擎。"""
    _install_httpx([_FakeResponse(200, b'[]')])
    _proxy('nodes', _FakeRequest('GET', WEBUI_JWT_HEADERS), static_token='')

    (req,) = _CAP
    assert req['headers']['Authorization'] == 'Bearer webui-user-jwt'


# ── 守卫与接线:nodes 前缀不弱化点段逃逸拦截;登录墙钉线 ──


def test_nodes_prefix_does_not_weaken_traversal_guard():
    """nodes 前缀夹带逃逸尾段仍 400(不转发)——C3 不引入新攻击面。"""
    _install_httpx([])
    try:
        _proxy('nodes/../../v1/models', _FakeRequest('GET', {}), static_token='t')
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError('穿越路径未被 400 拦截')
    assert _CAP == []  # 未发生任何转发


def test_catchall_wiring_covers_nodes_verbs_and_auth_wall():
    """源码钉线:catch-all 方法集含 DELETE(协议吊销动词),登录墙 Depends(get_verified_user)。"""
    source = (
        pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'routers' / 'banyan.py'
    ).read_text(encoding='utf-8')

    assert 'methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]' in source
    assert 'user: Any = Depends(get_verified_user)' in source  # 未登录不能借道(C2 JWT 墙)
    assert 'target_url = f"{BANYAN_ENGINE_URL}/api/{safe_path}"' in source  # 1:1 追加契约
