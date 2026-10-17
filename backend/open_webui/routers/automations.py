"""automations 路由 = 引擎适配投影(F15 / 完整方案 D21)。

**架构契约:定时任务的定义/调度/溯源唯一正本 = 引擎(K1,自带 every 时钟)。**
fork automation 表禁用(F12 已置 ``automations.enable=False``——本地调度闸仍在
utils/automations.scheduler_worker_loop,只读不动),本路由 8 个 handler 的路径与
请求/响应形状原样保留(前端零改),体内全部改为引擎调用:

- GET    /list          → GET    /api/automations?status=active|paused&limit
- POST   /create        → POST   /api/automations {name,prompt,tier,schedule,schedule_raw}
- GET    /{id}          → GET    /api/automations(list 内按 id 定位;引擎契约无单查端点)
- POST   /{id}/update   → PATCH  /api/automations/{id} {name?|prompt?|tier?|schedule?|enabled?}
- POST   /{id}/toggle   → list 定位后 PATCH {enabled: 取反}(同上,无单查)
- POST   /{id}/run      → POST   /api/automations/{id}/fire
- DELETE /{id}/delete   → DELETE /api/automations/{id}
- GET    /{id}/runs     → GET    /api/automations/{id}/runs

**automations.enable 门槛摘除**:fork 定义面已整体弃用,门槛只剩"挡投影页"的
副作用(F12 置 false 后整页 403)——保留 get_verified_user 登录门槛即可。

引擎不可达/5xx → 502(不降级回 fork 表——降级即复活双写);引擎 4xx 原码透传。
响应适配回 AutomationResponse 形状:last_run/next_runs 引擎不预演,Optional 置
null(前端 `next_runs?.[0] ?? next_run_at` 已容忍);时间统一投成 fork 的 ns;
模型 id ↔ 档位映射:banyan-fast → tier fast,其余 → heavy(投影回程 fast →
banyan-fast,heavy → banyan-duty)。

rrule ↔ schedule 翻译(引擎冻结契约 schedule_json,见 translate_rrule):
- FREQ=HOURLY[;INTERVAL=n]           → {kind:'interval',seconds:3600n}
- FREQ=DAILY(无 BYxxx)[;INTERVAL=n] → {kind:'interval',seconds:86400n}
- FREQ=DAILY;BYHOUR[/BYMINUTE]       → {kind:'daily',time:'HH:MM'}
- FREQ=WEEKLY;BYDAY=MO,WE[;BYHOUR..] → {kind:'weekly',days:[...],time}
- FREQ=MONTHLY;BYMONTHDAY=n[..时刻]  → {kind:'monthly',day:n,time}
- DTSTART=<..>;COUNT=1               → {kind:'at',ts:<epoch 秒>}
- 裸 INTERVAL=<秒>(≥300)            → {kind:'interval',seconds}(引擎任意间隔
  的原样回程,保证投影→编辑→更新的往返不失真)
- 其余(CUSTOM/不可表达)→ ValueError → 400 明示;凡可翻译的原 rrule 始终随
  ``schedule_raw={'rrule': 原串}`` 兜底上报(引擎侧溯源不丢)。
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from open_webui.events import EVENTS, publish_event
from open_webui.models.automations import AutomationForm, AutomationResponse, AutomationRunModel
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

PAGE_ITEM_COUNT = 30

#: 引擎契约单页上限(投机取全量以模拟 fork 分页;防御性封顶)
_ENGINE_LIST_CAP = 500

#: 引擎会话/任务访问沿用 env 直连(与 banyan_chat_adapter 同款)
_API_TIMEOUT = 10.0


############################
# Engine client (env 直连)
############################


def _engine_base_url() -> str:
    return os.environ.get('BANYAN_ENGINE_URL', 'http://localhost:8420').rstrip('/')


def _engine_headers() -> dict:
    headers = {'Accept': 'application/json'}
    token = os.environ.get('BANYAN_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


async def _engine_call(method: str, path: str, *, params: dict = None, json: dict = None):
    """引擎轻量调用:不可达/5xx → 502(不沉回 fork 表),4xx 原码透传。"""
    url = f'{_engine_base_url()}{path}'
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(_API_TIMEOUT)) as client:
            resp = await client.request(method, url, headers=_engine_headers(), params=params, json=json)
    except httpx.HTTPError as e:
        raise HTTPException(502, detail=f'banyan engine unreachable ({method} {path}): {e}')
    if resp.status_code >= 500:
        raise HTTPException(502, detail=f'banyan engine error {resp.status_code}: {resp.text[:200]}')
    if resp.status_code >= 400:
        try:
            detail = resp.json().get('detail') or resp.text[:200]
        except Exception:
            detail = resp.text[:200]
        raise HTTPException(resp.status_code, detail=detail)
    if not resp.content:
        return {}
    return resp.json()


async def _engine_list(status: Optional[str] = None, limit: int = _ENGINE_LIST_CAP) -> tuple[list, int]:
    """GET /api/automations → (items, total);契约 {items,total}。"""
    params = {'limit': limit}
    if status in ('active', 'paused'):
        params['status'] = status
    payload = await _engine_call('GET', '/automations', params=params)
    if isinstance(payload, list):
        return payload, len(payload)
    items = payload.get('items') or []
    try:
        total = int(payload.get('total'))
    except (TypeError, ValueError):
        total = len(items)
    return items, total


async def _engine_get_item(automation_id: str) -> Optional[dict]:
    """按 id 定位(引擎契约无单查端点,list 内找)。"""
    items, _ = await _engine_list(limit=_ENGINE_LIST_CAP)
    for item in items:
        if str(item.get('id')) == str(automation_id):
            return item
    return None


############################
# rrule ↔ schedule 翻译(纯函数)
############################


_WEEKDAY_CODES = {'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'}


def _parse_ints(value: Optional[str]) -> Optional[list[int]]:
    if value is None or value == '':
        return None
    try:
        return [int(v) for v in str(value).split(',') if v.strip() != '']
    except ValueError:
        return None


def _parse_dtstart_ts(value: str) -> Optional[int]:
    """DTSTART(YYYYMMDD[THHMMSS[Z]])→ epoch 秒;Z=UTC,naive 按本地时区。"""
    raw = value.strip()
    is_utc = raw.upper().endswith('Z')
    if is_utc:
        raw = raw[:-1]
    for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
        try:
            dt = datetime.strptime(raw, fmt)
            if is_utc:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def _parse_hhmm(parts: dict) -> str:
    """BYHOUR/BYMINUTE → 'HH:MM';单一时刻才可表达,否则 None。"""
    hours = _parse_ints(parts.get('BYHOUR')) or [0]
    minutes = _parse_ints(parts.get('BYMINUTE')) or [0]
    if len(hours) != 1 or len(minutes) != 1 or not (0 <= hours[0] <= 23) or not (0 <= minutes[0] <= 59):
        return None
    return f'{hours[0]:02d}:{minutes[0]:02d}'


def rrule_to_schedule(rrule: str) -> dict:
    """fork rrule → 引擎 schedule_json(冻结契约)。

    不可翻译(CUSTOM/多值/UNTIL/COUNT>1 等)抛 ValueError——调用方回 400 明示。
    """
    raw = (rrule or '').strip()
    if not raw:
        raise ValueError('rrule 为空')
    body = raw[6:] if raw.upper().startswith('RRULE:') else raw
    parts: dict[str, str] = {}
    for seg in body.split(';'):
        key, _, value = seg.strip().partition('=')
        if value != '':
            parts[key.upper()] = value

    # 一次性:DTSTART + COUNT=1 → at(绝对时刻)
    if parts.get('DTSTART') and parts.get('COUNT') == '1':
        ts = _parse_dtstart_ts(parts['DTSTART'])
        if ts is not None:
            return {'kind': 'at', 'ts': ts}

    # 裸 INTERVAL=<秒>:引擎任意间隔(interval)的原样表达(≥300 由契约保证)
    if set(parts) == {'INTERVAL'}:
        seconds = (_parse_ints(parts['INTERVAL']) or [None])[0]
        if seconds is not None and seconds >= 300:
            return {'kind': 'interval', 'seconds': seconds}

    freq = (parts.get('FREQ') or '').upper()
    interval_vals = _parse_ints(parts.get('INTERVAL') or '1')
    interval = interval_vals[0] if interval_vals else 0
    bydays = [d.strip().upper() for d in (parts.get('BYDAY') or '').split(',') if d.strip()]
    bymonthday = (_parse_ints(parts.get('BYMONTHDAY')) or [None])[0]
    has_by_time = parts.get('BYHOUR') is not None or parts.get('BYMINUTE') is not None
    time = _parse_hhmm(parts)

    if freq == 'HOURLY' and interval >= 1 and not bydays and bymonthday is None and not has_by_time:
        return {'kind': 'interval', 'seconds': 3600 * interval}

    if freq == 'DAILY':
        if not bydays and bymonthday is None and not has_by_time and interval >= 1:
            return {'kind': 'interval', 'seconds': 86400 * interval}
        if not bydays and bymonthday is None and has_by_time and time is not None and interval == 1:
            return {'kind': 'daily', 'time': time}

    if freq == 'WEEKLY' and bydays and all(d in _WEEKDAY_CODES for d in bydays) and interval == 1:
        if not has_by_time or time is not None:
            return {'kind': 'weekly', 'days': bydays, 'time': time or '00:00'}

    if freq == 'MONTHLY' and bymonthday is not None and not bydays and interval == 1:
        if not has_by_time or time is not None:
            return {'kind': 'monthly', 'day': bymonthday, 'time': time or '00:00'}

    raise ValueError(f"rrule 不可翻译为引擎调度(CUSTOM):'{rrule}'——仅支持 HOURLY/DAILY/WEEKLY+BYDAY/MONTHLY+BYMONTHDAY/一次性")


def _hhmm_to_rule(time: str) -> str:
    hour, _, minute = (time or '00:00').partition(':')
    return f'BYHOUR={int(hour):02d};BYMINUTE={int(minute):02d}'


def schedule_to_rrule(schedule: Optional[dict]) -> str:
    """引擎 schedule_json → 可回程的 fork rrule(投影 data.rrule;往返稳定)。"""
    if not isinstance(schedule, dict):
        return ''
    kind = schedule.get('kind')
    try:
        if kind == 'interval':
            seconds = int(schedule.get('seconds') or 0)
            if seconds <= 0:
                return ''
            if seconds % 3600 == 0:
                return f'FREQ=HOURLY;INTERVAL={seconds // 3600}'
            return f'INTERVAL={seconds}'
        if kind == 'daily':
            return f"FREQ=DAILY;{_hhmm_to_rule(schedule.get('time'))}"
        if kind == 'weekly':
            days = ','.join(d for d in schedule.get('days') or [] if d)
            if not days:
                return ''
            return f"FREQ=WEEKLY;BYDAY={days};{_hhmm_to_rule(schedule.get('time'))}"
        if kind == 'monthly':
            day = int(schedule.get('day') or 0)
            if not 1 <= day <= 31:
                return ''
            return f"FREQ=MONTHLY;BYMONTHDAY={day};{_hhmm_to_rule(schedule.get('time'))}"
        if kind == 'at':
            ts = int(schedule.get('ts') or 0)
            if ts <= 0:
                return ''
            # 本地 naive 序列化——rrule_to_schedule 的 naive 解析同用本地时区,往返稳定
            return f"DTSTART={datetime.fromtimestamp(ts).strftime('%Y%m%dT%H%M%S')};COUNT=1"
    except (TypeError, ValueError):
        return ''
    return ''


############################
# 引擎 item → AutomationResponse 投影
############################


def _to_ns(value) -> Optional[int]:
    """引擎时间(epoch 秒,容错毫秒/ns)→ fork 的 ns。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v < 1e11:
        return int(v * 1e9)
    if v < 1e14:
        return int(v * 1e6)
    return int(v)


def _model_to_tier(model_id: Optional[str]) -> str:
    """fork 模型 id → 引擎档位:banyan-fast → fast,其余 → heavy。"""
    return 'fast' if model_id == 'banyan-fast' else 'heavy'


def _tier_to_model(tier) -> str:
    return 'banyan-fast' if tier == 'fast' else 'banyan-duty'


def _project_run(run: Optional[dict], automation_id: str) -> Optional[AutomationRunModel]:
    if not isinstance(run, dict):
        return None
    created = _to_ns(run.get('created_at') or run.get('ts')) or 0
    return AutomationRunModel(
        id=str(run.get('id') or f'{automation_id}-{created}'),
        automation_id=str(automation_id),
        chat_id=run.get('chat_id'),
        status=str(run.get('status') or 'unknown'),
        error=run.get('error'),
        created_at=created,
    )


def _project_automation(item: dict, user_id: str) -> AutomationResponse:
    """引擎 item → AutomationResponse(前端 AutomationResponse 形状,零改消费)。

    last_run/next_runs:引擎不预演未来 → next_runs 置 null(Optional 容忍,
    前端回落 next_run_at);last_run 有则投 AutomationRunModel。
    """
    schedule = item.get('schedule') or {}
    schedule_raw = item.get('schedule_raw') or {}
    rrule = str(schedule_raw.get('rrule') or '') or schedule_to_rrule(schedule)
    automation_id = str(item.get('id'))
    last_run = _project_run(item.get('last_run'), automation_id)
    created = _to_ns(item.get('created_at')) or 0
    return AutomationResponse(
        id=automation_id,
        user_id=user_id,
        folder_id=None,  # 引擎无 folder 维度
        name=str(item.get('name') or ''),
        data={
            'prompt': str(item.get('prompt') or ''),
            'model_id': _tier_to_model(item.get('tier')),
            'rrule': rrule,
        },
        meta=None,
        is_active=bool(item.get('enabled', True)),
        last_run_at=(last_run.created_at if last_run else None),
        next_run_at=_to_ns(item.get('next_run')),
        created_at=created,
        updated_at=_to_ns(item.get('updated_at')) or created,
        last_run=last_run,
        next_runs=None,
    )


############################
# GetAutomationItems (paginated)
############################


@router.get('/list')
async def get_automation_items(
    request: Request,
    query: Optional[str] = None,
    status: Optional[str] = None,
    folder_id: Optional[str] = None,  # 引擎无 folder 维度,接受并忽略
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
):
    page = max(1, page or 1)
    # 引擎契约只有 status/limit:取前 page×30 条再本地切片,模拟 fork 分页
    items, total = await _engine_list(status=status, limit=min(page * PAGE_ITEM_COUNT, _ENGINE_LIST_CAP))
    if query:
        needle = query.lower()
        items = [i for i in items if needle in str(i.get('name') or '').lower()]
    skip = (page - 1) * PAGE_ITEM_COUNT
    return {
        'items': [_project_automation(i, user.id) for i in items[skip : skip + PAGE_ITEM_COUNT]],
        'total': total,
    }


############################
# CreateNewAutomation
############################


@router.post('/create', response_model=AutomationResponse)
async def create_new_automation(
    request: Request,
    form_data: AutomationForm,
    user=Depends(get_verified_user),
):
    target = (form_data.data.target or None) if form_data.data else None
    if target is not None and target.type == 'channel':
        raise HTTPException(400, detail='引擎 automations 不支持频道投递(target.type=channel)')

    try:
        schedule = rrule_to_schedule(form_data.data.rrule)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    item = await _engine_call(
        'POST',
        '/automations',
        json={
            'name': form_data.name,
            'prompt': form_data.data.prompt,
            'tier': _model_to_tier(form_data.data.model_id),
            'schedule': schedule,
            'schedule_raw': {'rrule': form_data.data.rrule},  # 原 rrule 兜底,溯源不丢
        },
    )
    # 契约 POST 体无 enabled:建后即停用补一次 PATCH
    if form_data.is_active is False:
        item = await _engine_call('PATCH', f"/automations/{item.get('id')}", json={'enabled': False}) or item
    await publish_event(
        request,
        EVENTS.AUTOMATION_CREATED,
        actor=user,
        subject_id=str(item.get('id')),
        data={'name': form_data.name, 'is_active': form_data.is_active is not False},
    )
    return _project_automation(item, user.id)


############################
# GetAutomationById
############################


@router.get('/{id}', response_model=AutomationResponse)
async def get_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    item = await _engine_get_item(id)
    if item is None:
        raise HTTPException(404, detail='Automation not found')
    return _project_automation(item, user.id)


############################
# UpdateAutomationById
############################


@router.post('/{id}/update', response_model=AutomationResponse)
async def update_automation_by_id(
    request: Request,
    id: str,
    form_data: AutomationForm,
    user=Depends(get_verified_user),
):
    target = (form_data.data.target or None) if form_data.data else None
    if target is not None and target.type == 'channel':
        raise HTTPException(400, detail='引擎 automations 不支持频道投递(target.type=channel)')

    patch: dict = {}
    if form_data.name:
        patch['name'] = form_data.name
    if form_data.data:
        if form_data.data.prompt:
            patch['prompt'] = form_data.data.prompt
        patch['tier'] = _model_to_tier(form_data.data.model_id)
        if form_data.data.rrule:
            # 空串(如一次性 at 投影失败)不携带 schedule/raw,保留引擎现值
            try:
                patch['schedule'] = rrule_to_schedule(form_data.data.rrule)
            except ValueError as e:
                raise HTTPException(400, detail=str(e))
            patch['schedule_raw'] = {'rrule': form_data.data.rrule}
    patch['enabled'] = form_data.is_active is not False

    item = await _engine_call('PATCH', f'/automations/{id}', json=patch)
    if not item:
        item = await _engine_get_item(id)
    if item is None:
        raise HTTPException(404, detail='Automation not found')
    await publish_event(
        request,
        EVENTS.AUTOMATION_UPDATED,
        actor=user,
        subject_id=str(item.get('id')),
        data={'name': item.get('name'), 'is_active': bool(item.get('enabled', True))},
    )
    return _project_automation(item, user.id)


############################
# ToggleAutomationById
############################


@router.post('/{id}/toggle', response_model=AutomationResponse)
async def toggle_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    item = await _engine_get_item(id)
    if item is None:
        raise HTTPException(404, detail='Automation not found')
    toggled = await _engine_call('PATCH', f'/automations/{id}', json={'enabled': not item.get('enabled', True)})
    item = toggled or {**item, 'enabled': not item.get('enabled', True)}
    await publish_event(
        request,
        EVENTS.AUTOMATION_ENABLED if item.get('enabled', True) else EVENTS.AUTOMATION_DISABLED,
        actor=user,
        subject_id=str(item.get('id')),
        subject_type='automation',
        data={'name': item.get('name')},
    )
    return _project_automation(item, user.id)


############################
# RunAutomationById
############################


@router.post('/{id}/run')
async def run_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    item = await _engine_get_item(id)
    if item is None:
        raise HTTPException(404, detail='Automation not found')
    await _engine_call('POST', f'/automations/{id}/fire')
    await publish_event(
        request,
        EVENTS.AUTOMATION_RUN_STARTED,
        actor=user,
        subject_id=str(item.get('id')),
        data={'name': item.get('name')},
    )
    return _project_automation(item, user.id)


############################
# DeleteAutomationById
############################


@router.delete('/{id}/delete')
async def delete_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
):
    await _engine_call('DELETE', f'/automations/{id}')
    await publish_event(
        request,
        EVENTS.AUTOMATION_DELETED,
        actor=user,
        subject_id=id,
    )
    return True


############################
# GetAutomationRuns
############################


@router.get('/{id}/runs', response_model=list[AutomationRunModel])
async def get_automation_runs(
    request: Request,
    id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
):
    payload = await _engine_call('GET', f'/automations/{id}/runs')
    runs = payload.get('items') if isinstance(payload, dict) else payload
    runs = runs or []
    return [
        projected
        for run in runs[skip : skip + limit]
        if (projected := _project_run(run, id)) is not None
    ]
