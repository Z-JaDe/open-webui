"""banyan automations 引擎适配投影单测(F15 / D21)。

与 test_banyan_chat_adapter.py 同款"最小测试"原则:importlib 直载
``open_webui/routers/automations.py``(open_webui.* 以桩模块注入 sys.modules,
models/automations 载真实文件以保真实 pydantic 形状),引擎 API 以假
``_engine_call`` 桩掉。

覆盖:
- rrule → schedule 翻译器全 kind(interval/daily/weekly/monthly/at/裸 INTERVAL)
  + CUSTOM/不可表达 → ValueError(路由层 400);
- schedule → rrule 回程(投影→编辑→更新往返稳定);
- 引擎 item → AutomationResponse 投影形状(tier↔model_id、ns 时间、
  last_run/next_runs Optional 容忍 null);
- handler 投影:list 分页切片+query 过滤+status 映射 / create(频道 target 400、
  CUSTOM 400、POST 体含 schedule+schedule_raw、建后即停补 PATCH)/ toggle(list
  定位+PATCH enabled 取反)/ update / runs 切片 / delete;
- _engine_call 真错误映射:引擎不可达 → 502。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_automations_projection.py -q
"""

import asyncio
import importlib.util
import json
import pathlib
import sys
import types

from pydantic import BaseModel

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


def _run(coro):
    return asyncio.run(coro)


# ── open_webui.* 桩(先于路由加载)──


class _AnyModel(BaseModel):
    model_config = {'extra': 'allow', 'protected_namespaces': ()}


def _stub(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


_EVENTS = types.SimpleNamespace(
    AUTOMATION_CREATED='automation.created',
    AUTOMATION_UPDATED='automation.updated',
    AUTOMATION_ENABLED='automation.enabled',
    AUTOMATION_DISABLED='automation.disabled',
    AUTOMATION_RUN_STARTED='automation.run_started',
    AUTOMATION_DELETED='automation.deleted',
)
_PUBLISHED = []


async def _publish_event(*args, **kwargs):
    _PUBLISHED.append(kwargs)


_stub('open_webui')
_stub('open_webui.events', EVENTS=_EVENTS, publish_event=_publish_event)
_stub('open_webui.models')
_stub('open_webui.utils')
_stub('open_webui.utils.auth', get_verified_user=lambda: None, get_admin_user=lambda: None)

# models/automations 载真实文件(真实 pydantic 形状;internal.db 桩掉)
_sqla = types.ModuleType('open_webui.internal.db')
from sqlalchemy import JSON as _JSON
from sqlalchemy.orm import declarative_base as _declarative_base

_sqla.Base = _declarative_base()
_sqla.JSONField = _JSON
_sqla.get_async_db_context = None
sys.modules['open_webui.internal.db'] = _sqla
_misc = _stub('open_webui.utils.misc', json_text_variants=lambda v: [v])
_models_automations = _load_module(_BACKEND / 'open_webui' / 'models' / 'automations.py', 'open_webui_models_automations_under_test')
sys.modules['open_webui.models.automations'] = _models_automations

ar = _load_module(_BACKEND / 'open_webui' / 'routers' / 'automations.py', 'automations_router_under_test')

#: 真引擎客户端(handler 测试会整只替换 ar._engine_call,真身在此留档)
_REAL_ENGINE_CALL = ar._engine_call

USER = types.SimpleNamespace(id='u1', role='admin')

_ENGINE_ITEM = {
    'id': 'auto1',
    'name': '每日巡检',
    'prompt': '巡检一轮',
    'tier': 'fast',
    'schedule': {'kind': 'daily', 'time': '09:30'},
    'schedule_raw': {'rrule': 'FREQ=DAILY;BYHOUR=9;BYMINUTE=30'},
    'enabled': True,
    'last_run': {'id': 'r9', 'status': 'success', 'created_at': 1700000000.5},
    'next_run': 1700003600,
    'created_at': 1700000000,
    'updated_at': 1700000001,
}


# ── rrule → schedule 翻译器(全 kind + CUSTOM 400)──


def test_translator_all_kinds():
    cases = [
        ('FREQ=HOURLY', {'kind': 'interval', 'seconds': 3600}),
        ('FREQ=HOURLY;INTERVAL=3', {'kind': 'interval', 'seconds': 10800}),
        ('FREQ=DAILY', {'kind': 'interval', 'seconds': 86400}),
        ('FREQ=DAILY;INTERVAL=2', {'kind': 'interval', 'seconds': 172800}),
        ('FREQ=DAILY;BYHOUR=9', {'kind': 'daily', 'time': '09:00'}),
        ('FREQ=DAILY;BYHOUR=9;BYMINUTE=30', {'kind': 'daily', 'time': '09:30'}),
        ('RRULE:FREQ=DAILY;BYHOUR=22', {'kind': 'daily', 'time': '22:00'}),
        ('FREQ=WEEKLY;BYDAY=MO,WE,FR;BYHOUR=8;BYMINUTE=15', {'kind': 'weekly', 'days': ['MO', 'WE', 'FR'], 'time': '08:15'}),
        ('FREQ=WEEKLY;BYDAY=TU,SA', {'kind': 'weekly', 'days': ['TU', 'SA'], 'time': '00:00'}),
        ('FREQ=MONTHLY;BYMONTHDAY=1;BYHOUR=7', {'kind': 'monthly', 'day': 1, 'time': '07:00'}),
        ('FREQ=MONTHLY;BYMONTHDAY=15', {'kind': 'monthly', 'day': 15, 'time': '00:00'}),
        ('INTERVAL=4500', {'kind': 'interval', 'seconds': 4500}),  # 裸 INTERVAL=引擎任意间隔回程
        ('DTSTART=20260101T090000;COUNT=1', {'kind': 'at', 'ts': 1767229200}),
    ]
    for rrule, want in cases:
        assert ar.rrule_to_schedule(rrule) == want, rrule


def test_translator_custom_untranslatable_rejected():
    for rrule in [
        'FREQ=MINUTELY;INTERVAL=10',
        'FREQ=WEEKLY;BYDAY=MO;INTERVAL=2;BYHOUR=9',  # WEEKLY 带 INTERVAL
        'FREQ=DAILY;BYDAY=MO',  # DAILY + BYDAY
        'FREQ=DAILY;BYHOUR=9,12',  # 多时刻
        'FREQ=MONTHLY',  # 缺 BYMONTHDAY
        'DTSTART=20260101T090000;COUNT=2',  # COUNT>1
        'FREQ=WEEKLY',  # 缺 BYDAY
        'INTERVAL=100',  # < 契约下限 300
        'FREQ=HOURLY;BYMINUTE=30',
        '',
    ]:
        try:
            ar.rrule_to_schedule(rrule)
            raise AssertionError(f'expected ValueError: {rrule!r}')
        except ValueError:
            pass


def test_translator_round_trip_stable():
    """投影→编辑器回显→再更新的往返:schedule→rrule→schedule 恒等。"""
    schedules = [
        {'kind': 'interval', 'seconds': 3600},
        {'kind': 'interval', 'seconds': 7200},
        {'kind': 'interval', 'seconds': 4500},
        {'kind': 'daily', 'time': '09:30'},
        {'kind': 'weekly', 'days': ['MO', 'FR'], 'time': '18:00'},
        {'kind': 'monthly', 'day': 1, 'time': '07:00'},
        {'kind': 'at', 'ts': 1767229200},
    ]
    for schedule in schedules:
        assert ar.rrule_to_schedule(ar.schedule_to_rrule(schedule)) == schedule, schedule


# ── 引擎 item → AutomationResponse 投影形状 ──


def test_projection_shape_fast_tier():
    response = ar._project_automation(_ENGINE_ITEM, USER.id)
    assert response.id == 'auto1'
    assert response.user_id == 'u1' and response.folder_id is None
    assert response.data['model_id'] == 'banyan-fast'  # banyan-fast→tier fast 的回程
    assert response.data['rrule'] == 'FREQ=DAILY;BYHOUR=9;BYMINUTE=30'  # 原 rrule 兜底优先
    assert response.is_active is True
    assert response.last_run_at == 1700000000500000000  # 引擎秒 → fork ns
    assert response.next_run_at == 1700003600000000000
    assert response.last_run is not None and response.last_run.status == 'success'
    assert response.next_runs is None  # 引擎不预演,Optional 置 null(前端容忍)


def test_projection_shape_heavy_defaults():
    response = ar._project_automation({'id': 2, 'name': 'n', 'prompt': 'p', 'schedule': {'kind': 'interval', 'seconds': 4500}}, USER.id)
    assert response.id == '2'
    assert response.data['model_id'] == 'banyan-duty'  # 非 fast → heavy 的回程
    assert response.data['rrule'] == 'INTERVAL=4500'  # 无 raw → schedule 合成回程 rrule
    assert response.is_active is True  # 缺 enabled 容忍为 True
    assert response.last_run is None and response.last_run_at is None


# ── handler 投影(引擎桩)──


class _EngineStub:
    def __init__(self, responses):
        self.calls = []
        self.responses = list(responses)

    async def __call__(self, method, path, *, params=None, json=None):
        self.calls.append((method, path, params, json))
        return self.responses.pop(0)


def _install(responses):
    stub = _EngineStub(responses)
    ar._engine_call = stub
    return stub


def test_handler_list_pagination_and_filters():
    items = [
        {**_ENGINE_ITEM, 'id': f'a{i}', 'name': f'任务 {i}'} | ({'name': '巡检特例'} if i == 0 else {})
        for i in range(35)
    ]
    stub = _install([{'items': items, 'total': 35}, {'items': items, 'total': 35}])
    result = _run(ar.get_automation_items(request=None, query='巡检特例', status='active', folder_id=None, page=1, user=USER))
    assert stub.calls[0][0] == 'GET' and stub.calls[0][1] == '/automations'
    assert stub.calls[0][2]['status'] == 'active' and stub.calls[0][2]['limit'] == 30  # page=1×30
    assert result['total'] == 35
    assert [i.id for i in result['items']] == ['a0']
    page2 = _run(ar.get_automation_items(request=None, query=None, status=None, folder_id=None, page=2, user=USER))
    page2_params = stub.calls[-1][2]
    assert page2_params.get('status') is None and page2_params['limit'] == 60  # status=all 不下发;取前 60 条
    assert len(page2['items']) == 5 and page2['items'][0].id == 'a30'  # 本地切片模拟 fork 分页(尾页不足 30)


def test_handler_create_translates_and_carries_raw():
    stub = _install([{**_ENGINE_ITEM, 'id': 'auto-new'}])
    form = _models_automations.AutomationForm(
        name='每日报',
        data=_models_automations.AutomationData(prompt='报数', model_id='banyan-fast', rrule='FREQ=DAILY;BYHOUR=9;BYMINUTE=30'),
    )
    response = _run(ar.create_new_automation(request=None, form_data=form, user=USER))
    method, path, params, body = stub.calls[0]
    assert (method, path) == ('POST', '/automations')
    assert body['tier'] == 'fast' and body['name'] == '每日报'
    assert body['schedule'] == {'kind': 'daily', 'time': '09:30'}
    assert body['schedule_raw'] == {'rrule': 'FREQ=DAILY;BYHOUR=9;BYMINUTE=30'}  # 原 rrule 兜底
    assert response.id == 'auto-new' and response.data['rrule'].startswith('FREQ=DAILY')


def test_handler_create_rejects_channel_target_and_custom():
    stub = _install([])
    channel_form = _models_automations.AutomationForm(
        name='c',
        data=_models_automations.AutomationData(
            prompt='p', model_id='banyan-duty', rrule='FREQ=HOURLY', target=_models_automations.AutomationTarget(type='channel', channel_id='x')
        ),
    )
    import fastapi

    try:
        _run(ar.create_new_automation(request=None, form_data=channel_form, user=USER))
        raise AssertionError('expected 400')
    except fastapi.HTTPException as e:
        assert e.status_code == 400
    custom_form = _models_automations.AutomationForm(
        name='c', data=_models_automations.AutomationData(prompt='p', model_id='banyan-duty', rrule='FREQ=MINUTELY;INTERVAL=5')
    )
    try:
        _run(ar.create_new_automation(request=None, form_data=custom_form, user=USER))
        raise AssertionError('expected 400')
    except fastapi.HTTPException as e:
        assert e.status_code == 400 and 'CUSTOM' in e.detail
    assert stub.calls == []  # 400 前不出网


def test_handler_create_inactive_patches_enabled_false():
    stub = _install([{**_ENGINE_ITEM, 'id': 'auto-q', 'enabled': True}, {**_ENGINE_ITEM, 'id': 'auto-q', 'enabled': False}])
    form = _models_automations.AutomationForm(
        name='q', is_active=False, data=_models_automations.AutomationData(prompt='p', model_id='banyan-duty', rrule='FREQ=HOURLY')
    )
    response = _run(ar.create_new_automation(request=None, form_data=form, user=USER))
    assert stub.calls[1][:2] == ('PATCH', '/automations/auto-q')  # 契约 POST 体无 enabled → 建后即停补 PATCH
    assert stub.calls[1][3] == {'enabled': False}
    assert response.is_active is False


def test_handler_toggle_negates_enabled():
    stub = _install([{'items': [{**_ENGINE_ITEM, 'enabled': True}], 'total': 1}, {**_ENGINE_ITEM, 'enabled': False}])
    response = _run(ar.toggle_automation_by_id(request=None, id='auto1', user=USER))
    assert stub.calls[1] == ('PATCH', '/automations/auto1', None, {'enabled': False})  # list 定位+取反
    assert response.is_active is False


def test_handler_update_translates_rrule():
    stub = _install([{**_ENGINE_ITEM, 'tier': 'heavy', 'name': '改名', 'prompt': '新 prompt'}])
    form = _models_automations.AutomationForm(
        name='改名',
        data=_models_automations.AutomationData(prompt='新 prompt', model_id='banyan-duty', rrule='FREQ=WEEKLY;BYDAY=MO,FR;BYHOUR=18'),
    )
    response = _run(ar.update_automation_by_id(request=None, id='auto1', form_data=form, user=USER))
    _, _, _, patch = stub.calls[0]
    assert patch['schedule'] == {'kind': 'weekly', 'days': ['MO', 'FR'], 'time': '18:00'}
    assert patch['tier'] == 'heavy' and patch['enabled'] is True
    assert patch['schedule_raw'] == {'rrule': 'FREQ=WEEKLY;BYDAY=MO,FR;BYHOUR=18'}
    assert response.data['model_id'] == 'banyan-duty'


def test_handler_runs_slices():
    runs = [{'id': f'r{i}', 'status': 'success', 'created_at': 1700000000 + i} for i in range(60)]
    _install([runs])
    page = _run(ar.get_automation_runs(request=None, id='auto1', skip=50, limit=50, user=USER))
    assert len(page) == 10 and page[0].id == 'r50'  # 本地切片模拟 skip/limit
    assert page[0].created_at == (1700000000 + 50) * 10**9


def test_handler_delete_returns_true():
    stub = _install([{'ok': True}])
    assert _run(ar.delete_automation_by_id(request=None, id='auto1', user=USER)) is True
    assert stub.calls[0][:2] == ('DELETE', '/automations/auto1')


def test_engine_call_unreachable_maps_502():
    """引擎不可达 → 502(不降级回 fork 表)。"""

    class _Boom:
        def request(self, *a, **k):
            raise ar.httpx.ConnectError('connection refused')

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    real_httpx = ar.httpx
    ar.httpx = types.SimpleNamespace(
        AsyncClient=lambda timeout: _Boom(),
        HTTPError=real_httpx.HTTPError,
        ConnectError=real_httpx.ConnectError,
        Timeout=real_httpx.Timeout,
    )
    try:
        try:
            _run(_REAL_ENGINE_CALL('GET', '/automations'))
            raise AssertionError('expected 502')
        except ar.HTTPException as e:
            assert e.status_code == 502 and 'unreachable' in e.detail
    finally:
        ar.httpx = real_httpx
