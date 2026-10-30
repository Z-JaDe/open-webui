"""V4W-1:goals/status/nodes 三族 GET 云端第二上游聚合单测(webui v4 跟进)。

背景:本地 webui /banyan/api 代理 → 本地引擎 → 本地 pi-goal;审查/知识 goal
在杭州云端引擎。本测钉代理层 cloud 聚合分支:

- env BANYAN_CLOUD_URL + BANYAN_V1_TOKEN 齐备时,goals/status/nodes 三族
  **GET** 请求聚合两路:本地为主 + 云端条目标记 cloud: true 合并;写操作与
  其余路径仍走本地(零行为)。
- env 缺任一 = 零行为(单上游直达,响应与现形态逐字节同源)。
- 云端不可达/非 200/坏 JSON:本地为主不失败,顶层 cloud.ok=false。

同仓"最小测试"模式(test_banyan_nodes_proxy.py):importlib 直载真实
routers/banyan.py(auth 桩),httpx 假 AsyncClient 回放双上游(_CAP 捕获
转发实参;_OUTCOMES 按 [本地, 云端] 序消费)。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_cloud_aggregate.py -q
"""

import asyncio
import importlib.util
import json
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


# ── 依赖桩:auth 桩掉;banyan_bridge 载真实纯模块 ──
_stub('open_webui')
_stub('open_webui.utils')
_stub('open_webui.utils.auth', get_verified_user=lambda: None)
sys.modules['open_webui.utils.banyan_bridge'] = _load_module(
    _BACKEND / 'open_webui' / 'utils' / 'banyan_bridge.py',
    'banyan_bridge_under_test_cloud',
)

banyan = _load_module(
    _BACKEND / 'open_webui' / 'routers' / 'banyan.py', 'banyan_router_under_test_cloud'
)

ENGINE = 'http://127.0.0.1:8000'
CLOUD = 'https://login.pyrris.com'
CLOUD_TOKEN = 'hangzhou-v1-token'
USER = types.SimpleNamespace(id='u1', role='admin')

# ── 假 httpx:build_request 捕获转发实参;send 回放预设响应(队列按序)──

_CAP: list[dict] = []
_OUTCOMES: list = []


class _FakeAsyncClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

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
        pass


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
    """双形态响应:聚合分支读 .content/.json();catch-all 流式读 aiter_bytes。"""

    def __init__(self, status_code=200, body=b'{}', headers=None):
        self.status_code = status_code
        self.headers = headers or {'content-type': 'application/json'}
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()

    @property
    def content(self):
        return self._body

    def json(self):
        return json.loads(self._body)

    async def aiter_bytes(self):
        yield self._body

    async def aclose(self):
        pass


class _CIDict(dict):
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


def _proxy(path, request, cloud=True):
    """驱动 catch-all(含 cloud 聚合判定);cloud=False 模拟 env 缺零行为形态。"""
    banyan.BANYAN_ENGINE_URL = ENGINE
    banyan.BANYAN_TOKEN = ''
    banyan.BANYAN_CLOUD_URL = CLOUD if cloud else ''
    banyan.BANYAN_V1_TOKEN = CLOUD_TOKEN if cloud else ''
    return asyncio.run(banyan.banyan_proxy(path=path, request=request, user=USER))


def _drain(response) -> bytes:
    """读响应体:StreamingResponse 走 body_iterator,聚合分支的 Response 读 body。"""
    if hasattr(response, 'body_iterator'):
        async def run():
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            return b''.join(chunks)

        return asyncio.run(run())
    return response.body


REQ = _FakeRequest('GET', {'Authorization': 'Bearer webui-jwt'})

LOCAL_GOAL = {'goalId': 'g-local', 'objective': '本地 goal', 'status': 'running'}
CLOUD_GOAL = {'goalId': 'g-cloud', 'objective': '杭州审查 goal', 'status': 'completed'}


# ── 列表族:双上游聚合 ──


def test_goals_list_merged_with_cloud_flag():
    """GET goals → 本地 goals + 云端 goals(条目 cloud: true)+ 顶层 cloud 状态。"""
    _install_httpx([
        _FakeResponse(200, {'goals': [LOCAL_GOAL]}),
        _FakeResponse(200, {'goals': [CLOUD_GOAL]}),
    ])
    resp = _proxy('goals', REQ)
    assert resp.status_code == 200
    d = json.loads(_drain(resp))
    assert [g['goalId'] for g in d['goals']] == ['g-local', 'g-cloud'], '本地在前为主'
    assert d['goals'][0].get('cloud') is not True, '本地条目不打云标'
    assert d['goals'][1]['cloud'] is True, '云端条目标 cloud: true'
    assert d['cloud']['ok'] is True and 'login.pyrris.com' in d['cloud']['host']
    assert d['cloud']['count'] == 1
    # 双上游转发实参:本地 + 云端(云端带 V1 凭证,不带 webui JWT)
    local_req, cloud_req = _CAP
    assert local_req['url'] == f'{ENGINE}/api/goals'
    assert cloud_req['url'] == f'{CLOUD}/api/goals'
    assert cloud_req['headers']['Authorization'] == f'Bearer {CLOUD_TOKEN}'
    assert 'webui-jwt' not in cloud_req['headers'].get('Authorization', '')


def test_nodes_merged_and_cards_merged():
    """GET nodes / goals/cards 同款列表合并(键名随端点)。"""
    _install_httpx([
        _FakeResponse(200, {'nodes': [{'node_id': 'n-local'}]}),
        _FakeResponse(200, {'nodes': [{'node_id': 'n-cloud'}]}),
    ])
    d = json.loads(_drain(_proxy('nodes', REQ)))
    assert [n['node_id'] for n in d['nodes']] == ['n-local', 'n-cloud']
    assert d['nodes'][1]['cloud'] is True

    _install_httpx([
        _FakeResponse(200, {'cards': [{'cardId': 'c-local'}]}),
        _FakeResponse(200, {'cards': [{'cardId': 'c-cloud'}]}),
    ])
    d = json.loads(_drain(_proxy('goals/cards', REQ)))
    assert [c['cardId'] for c in d['cards']] == ['c-local', 'c-cloud']
    assert d['cards'][1]['cloud'] is True


# ── status 族:本地为主 + 顶层 cloud 概要 ──


def test_status_local_first_with_cloud_summary():
    """GET status → 本地主响应原样 + cloud 键(云端 engine 概要);云挂不炸本地。"""
    local_status = {'engine': {'status': 'ok', 'version': '4.0'},
                    'counts': {'inbox': {}, 'plans_running': 0}}
    cloud_status = {'engine': {'status': 'ok', 'version': '4.1', 'last_seq': 9},
                    'counts': {}, 'memory': {'rss_mb': 512}}
    _install_httpx([
        _FakeResponse(200, local_status),
        _FakeResponse(200, cloud_status),
    ])
    d = json.loads(_drain(_proxy('status', REQ)))
    assert d['engine'] == local_status['engine'], '本地为主不覆盖'
    assert d['cloud']['ok'] is True
    assert d['cloud']['engine']['version'] == '4.1', '云端 engine 概要'

    # 云端不可达:本地照常 200,cloud.ok=false 诚实标注
    _install_httpx([
        _FakeResponse(200, local_status),
        _real_httpx.ConnectError('cloud down'),
    ])
    d2 = json.loads(_drain(_proxy('status', REQ)))
    assert d2['engine']['status'] == 'ok'
    assert d2['cloud']['ok'] is False


# ── 单条族:本地 404 → 云端回退;本地 200 → 不打云端 ──


def test_goal_detail_fallback_to_cloud_on_local_miss():
    """GET goals/{id}:本地 404 → 云端 200 回退(顶层+条目 cloud: true)。"""
    _install_httpx([
        _FakeResponse(404, {'detail': 'not found'}),
        _FakeResponse(200, {'goal': CLOUD_GOAL}),
    ])
    resp = _proxy('goals/g-cloud', REQ)
    assert resp.status_code == 200
    d = json.loads(_drain(resp))
    assert d['goal']['goalId'] == 'g-cloud'
    assert d['goal']['cloud'] is True
    assert d['cloud'] is True

    # convs 同款回退(转录页可看云 goal 内部会话)
    _install_httpx([
        _FakeResponse(404, {'detail': 'not found'}),
        _FakeResponse(200, {'manager': {'transcript': []}, 'subagents': [], 'reviewers': []}),
    ])
    d2 = json.loads(_drain(_proxy('goals/g-cloud/convs', REQ)))
    assert d2['cloud'] is True and 'manager' in d2


def test_goal_detail_local_hit_skips_cloud():
    """GET goals/{id} 本地 200 → 只打本地(单上游,体不加 cloud 键)。"""
    _install_httpx([_FakeResponse(200, {'goal': LOCAL_GOAL})])
    resp = _proxy('goals/g-local', REQ)
    assert resp.status_code == 200
    d = json.loads(_drain(resp))
    assert d == {'goal': LOCAL_GOAL}, '本地命中:原样透传不加键'
    assert len(_CAP) == 1 and _CAP[0]['url'] == f'{ENGINE}/api/goals/g-local'


# ── 硬边界:写操作 / 非三族 / env 缺 = 零行为 ──


def test_write_ops_never_aggregate():
    """POST goals / POST goals/cards/{id}/resolve → 只打本地(写走本地)。"""
    _install_httpx([_FakeResponse(200, {'goalId': 'g-new'})])
    resp = _proxy('goals', _FakeRequest('POST', REQ.headers, body=b'{"objective":"x"}'))
    assert resp.status_code == 200
    assert len(_CAP) == 1 and _CAP[0]['url'] == f'{ENGINE}/api/goals'
    assert _CAP[0]['method'] == 'POST'

    _install_httpx([_FakeResponse(200, {'ok': 1})])
    _proxy('goals/cards/c-cloud/resolve',
           _FakeRequest('POST', REQ.headers, body=b'{"decision":"approved"}'))
    assert len(_CAP) == 1 and _CAP[0]['url'] == f'{ENGINE}/api/goals/cards/c-cloud/resolve'


def test_non_family_get_not_aggregated():
    """GET /plans(非三族)→ 只打本地,响应原样透传。"""
    _install_httpx([_FakeResponse(200, {'plans': []})])
    resp = _proxy('plans', REQ)
    assert json.loads(_drain(resp)) == {'plans': []}
    assert len(_CAP) == 1


def test_env_missing_zero_behavior():
    """BANYAN_CLOUD_URL 缺(或 token 缺)→ 单上游 catch-all,响应=本地原样体。"""
    local_body = {'goals': [LOCAL_GOAL]}
    _install_httpx([_FakeResponse(200, local_body)])
    resp = _proxy('goals', REQ, cloud=False)
    assert resp.status_code == 200
    assert json.loads(_drain(resp)) == local_body, '零行为=现形态逐字节(无 cloud 键)'
    assert len(_CAP) == 1, '零外呼'

    # token 缺同款(单测 URL 在、token 缺的第二半;不走 _proxy——它会重设 env)
    banyan.BANYAN_ENGINE_URL = ENGINE
    banyan.BANYAN_TOKEN = ''
    banyan.BANYAN_CLOUD_URL = CLOUD
    banyan.BANYAN_V1_TOKEN = ''
    _install_httpx([_FakeResponse(200, local_body)])
    resp2 = asyncio.run(
        banyan.banyan_proxy(path='goals', request=REQ, user=USER))
    assert json.loads(_drain(resp2)) == local_body
    assert len(_CAP) == 1
    # 复位(后续用例默认 env 齐形态)
    banyan.BANYAN_V1_TOKEN = CLOUD_TOKEN


def test_cloud_non_200_degrades_to_local():
    """云端 500/坏 JSON:列表族本地照常 + cloud.ok=false(本地为主不失败)。"""
    local_body = {'goals': [LOCAL_GOAL]}
    for bad in (_FakeResponse(500, {'detail': 'boom'}),
                _FakeResponse(200, b'not-json{{{')):
        _install_httpx([_FakeResponse(200, local_body), bad])
        d = json.loads(_drain(_proxy('goals', REQ)))
        assert [g['goalId'] for g in d['goals']] == ['g-local']
        assert d['cloud']['ok'] is False
        assert d['cloud'].get('error'), '失败原因诚实标注'


def test_local_unreachable_still_502_and_traversal_guard_intact():
    """本地不可达仍 502(云端不救本地);点段逃逸仍 400 先于一切转发。"""
    _install_httpx([_real_httpx.ConnectError('local down'),
                    _FakeResponse(200, {'goals': [CLOUD_GOAL]})])
    try:
        _proxy('goals', REQ)
    except HTTPException as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError('本地不可达未 502')

    _install_httpx([])
    try:
        _proxy('goals/../../v1/models', REQ)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError('穿越路径未被 400 拦截')
    assert _CAP == []
