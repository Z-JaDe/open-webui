"""banyan chats 路由适配器(完整方案 §4.5 D16' 零双写,F7)。

**架构契约:对话引擎单写单存,WebUI 消息零存储。** chat id 即引擎会话 id
(``sess_*``):chats 路由不再有第二行——

- create → 引擎 POST /api/projects/{default}/sessions,返回 ``sess_*`` 直接作
  chat id(WebUI 库零行);
- get    → 引擎会话 meta+行 → 投影成 Open WebUI Chat 形状(userInput/
  assistantText/toolCall/ticket/marker 行 → 消息 + ``banyanEvents[]``;行是
  超集,零信息损失);
- save   → **no-op**:完成的完成流不持久化,消息唯一落点=引擎行(唯一写入
  发生在转发调用经引擎时);
- update/delete → 引擎 PATCH(title/pinned/archived/read 列已齐);删除=
  archived=true(置态留史,不物理删);
- list   → 引擎会话列表投影(全部引擎会话可见,"引擎跑完 WebUI 就识别"的字面
  实现)。

旧副本(非 sess_ 的 WebUI 本地 chat)走原路径只读到自然淘汰,不迁移——见
banyan_conv.py(绑定机制随 chat id=会话 id 退役,仅为存量 chat 保留)。

引擎访问沿用 env 直连(BANYAN_ENGINE_URL / BANYAN_TOKEN,httpx)——与
banyan_conv/banyan 代理桥同源;不经 /banyan/api 桥(那是前端通道)。模块顶部
只依赖 httpx 与标准库(WebUI 库的 import 一律函数内 lazy),保证可按
test_banyan_conv.py 同款 importlib 方式单测。

投影形状对齐:
- Chat JSON → open_webui.models.chats.ChatResponse + Chat.svelte loadChat 消费
  (chat.history.messages 映射 + chat.messages 平铺,convertMessagesToHistory 兼容);
- banyanEvents → src/lib/components/banyan/types.ts(BanyanToolEvent/
  BanyanSubagentEvent;ts 为 epoch ms)——ticket 行按引擎 v1 编排线的同款映射
  (banyan/human/v1_api.py frame_lines:ticket→subagent)投影,marker 行前端
  无渲染分支(BanyanEvents.svelte switch 忽略未知 type),数据保留不丢。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx

log = logging.getLogger(__name__)

#: 引擎会话 id 前缀 = 引擎 chat_store.create_session 的 id 形态("sess_"+hex12)
ENGINE_CHAT_PREFIX = 'sess_'
#: 引擎 API 轻量调用超时(秒)
_API_TIMEOUT = 10.0
#: 缺省档位显示名(引擎 /v1/models 命名默认;行不携带档位,投影统一用它)
DEFAULT_MODEL_ID = 'banyan-duty'
#: 行全量回补的单页上限(引擎 /api/sessions/{id}/rows 的 limit 夹在 1..200)
_ROWS_PAGE = 200
#: 行回补页数上限(200×100=2 万行)——单机会话远达不到,防御引擎异常时兜底退出
_ROWS_MAX_PAGES = 100
#: 列表全量拉取上限(无分页参数的侧栏全列表;单机数据量小,注释声明非流式分页)
_LIST_MAX = 2000


def is_engine_chat(chat_id: Any) -> bool:
    """chat id 是否为引擎会话(D16':chat id 即引擎会话 id)。"""
    return isinstance(chat_id, str) and chat_id.startswith(ENGINE_CHAT_PREFIX)


# ── 引擎 HTTP(env 直连,沿用 banyan_conv 同款模式)──


def engine_base_url() -> str:
    return os.environ.get('BANYAN_ENGINE_URL', 'http://localhost:8000').rstrip('/')


def _engine_headers() -> dict[str, str]:
    headers = {'Accept': 'application/json'}
    token = os.environ.get('BANYAN_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


async def _engine_call(method: str, path: str, **kwargs) -> httpx.Response:
    url = f'{engine_base_url()}{path}'
    async with httpx.AsyncClient(timeout=httpx.Timeout(_API_TIMEOUT)) as client:
        return await client.request(method, url, headers=_engine_headers(), **kwargs)


def is_banyan_target(url: str) -> bool:
    """openai 连接 URL 是否指向引擎(origin 相等;与 banyan_conv 同语义)。"""
    try:
        engine = urlparse(engine_base_url())
        target = urlparse(url or '')
        return bool(target.netloc) and (engine.scheme, engine.netloc) == (
            target.scheme,
            target.netloc,
        )
    except Exception:
        return False


async def default_project_key() -> Optional[str]:
    """引擎默认项目 key(引擎 _default_conv 用 realpath(workspace) 作 key,
    sort_order 最小;每次默认轮 upsert,列表首项即它)。"""
    r = await _engine_call('GET', '/api/projects')
    if r.status_code != 200:
        log.warning('banyan_chat_adapter: 项目列表不可得(%s %s)', r.status_code, r.text[:200])
        return None
    projects = r.json()
    if not isinstance(projects, list) or not projects:
        log.warning('banyan_chat_adapter: 引擎无项目,无法建会话')
        return None
    return min(projects, key=lambda p: p.get('sort_order', 0)).get('key')


# ── 行 → 消息/banyanEvents 投影(纯函数,单测核心)──


def _ms(ts: Optional[float]) -> Optional[int]:
    """引擎行 ts(epoch 秒,浮点)→ epoch ms(前端 types.ts 时间约定)。"""
    return int(ts * 1000) if ts else None


def row_to_event(row: dict) -> Optional[dict]:
    """toolCall/ticket/marker 行 → 前端 banyanEvents 事件(types.ts 形状)。

    - toolCall → BanyanToolEvent{type:'tool',call_id,name,args_summary,status:
      running|ok|error,output_summary}(行落库时工具已收口,status=error→error,
      其余→ok;行无 started_at,只有 ended_at=行 ts);
    - ticket → BanyanSubagentEvent{type:'subagent',subagent_id,work_id,title,
      latest_action,status}(引擎 v1 编排线同款映射:ticket→subagent,work_id
      = ticket_id 保 /work/{id}/cancel 可达;state done/cancelled/failed→
      done/stopped/failed,其余按 running);
    - marker → 透传保留{type:'marker',marker,text}(前端无渲染分支,数据不丢)。
    其他 kind 返回 None(调用方忽略)。
    """
    kind = row.get('kind')
    data = row.get('data') or {}
    ts = _ms(row.get('ts'))
    if kind == 'toolCall':
        args = data.get('args')
        output = data.get('output')
        return {
            'type': 'tool',
            'call_id': row.get('row_id') or '',
            'name': str(data.get('tool') or ''),
            'args_summary': (
                json.dumps(args, ensure_ascii=False, default=str)[:200] if args else ''
            ),
            'status': 'error' if row.get('status') == 'error' else 'ok',
            'output_summary': str(output)[:400] if output else '',
            'ended_at': ts,
            'ts': ts,
        }
    if kind == 'ticket':
        state = str(data.get('state') or 'running')
        status = {'done': 'done', 'cancelled': 'stopped', 'failed': 'failed'}.get(state, 'running')
        ticket_id = str(data.get('ticket_id') or row.get('row_id') or '')
        return {
            'type': 'subagent',
            'subagent_id': ticket_id,
            'work_id': ticket_id,
            'title': data.get('title'),
            'latest_action': data.get('latest_action'),
            'status': status,
            'ts': ts,
        }
    if kind == 'marker':
        return {
            'type': 'marker',
            'marker': data.get('marker'),
            'text': data.get('text'),
            'ts': ts,
        }
    return None


def rows_to_chat_messages(rows: list[dict], *, model_id: str = DEFAULT_MODEL_ID) -> list[dict]:
    """引擎行(升序)→ Open WebUI 消息平铺列表(线性树)。

    - userInput → user 消息(confirmed===false 标 pending:echo 待确认态);
    - assistantText → assistant 消息(status=streaming → done=False 进行中;
      error/cancelled → error 键);
    - toolCall/ticket/marker → 按行序归入当前(最近一条)assistant 消息的
      banyanEvents[];其前无 assistant 消息时合成空壳承载(事件不丢)。
    id=引擎 row_id,parentId 沿线性链——前端 convertMessagesToHistory 直接建树。
    """
    messages: list[dict] = []
    state = {'last_id': None, 'assistant': None}

    def _attach(event: dict, ts: int) -> None:
        holder = state['assistant']
        if holder is None:  # 事件先于任何 assistantText(异常序):合成空壳承载
            holder = {
                'id': f'evt_{len(messages)}_{ts}',
                'parentId': state['last_id'],
                'childrenIds': [],
                'role': 'assistant',
                'content': '',
                'model': model_id,
                'done': True,
                'timestamp': ts,
            }
            messages.append(holder)
            state['last_id'] = holder['id']
            state['assistant'] = holder
        holder.setdefault('banyanEvents', []).append(event)

    for row in rows:
        kind = row.get('kind')
        data = row.get('data') or {}
        ts = int(row.get('ts') or time.time())
        row_id = row.get('row_id') or f'row_{ts}_{len(messages)}'
        status = row.get('status')
        if kind == 'userInput':
            message = {
                'id': row_id,
                'parentId': state['last_id'],
                'childrenIds': [],
                'role': 'user',
                'content': str(data.get('text') or ''),
                'timestamp': ts,
                'done': True,
            }
            if data.get('confirmed') is False:
                message['pending'] = True  # echo 待确认(引擎 §4.3 协议)
            messages.append(message)
            state['last_id'] = row_id
            state['assistant'] = None
        elif kind == 'assistantText':
            message = {
                'id': row_id,
                'parentId': state['last_id'],
                'childrenIds': [],
                'role': 'assistant',
                'content': str(data.get('text') or ''),
                'model': model_id,
                'modelName': model_id,
                'timestamp': ts,
                'done': status != 'streaming',
            }
            if status == 'error':
                message['error'] = {'content': message['content']}
            elif status == 'cancelled':
                message['error'] = {'content': None, 'cancelled': True}
            messages.append(message)
            state['last_id'] = row_id
            state['assistant'] = message
        elif kind in ('toolCall', 'ticket', 'marker'):
            event = row_to_event(row)
            if event is not None:
                _attach(event, ts)
        # 其余 kind(未来引擎扩展):行是超集,跳过不炸

    # 补齐 childrenIds 链(线性树):loadChat 直接消费 chat.history(不走
    # convertMessagesToHistory),父节点的 childrenIds 需投影侧自建——
    # 首条 parentId=null,其余父恰一子。
    by_id = {m['id']: m for m in messages}
    for m in messages:
        parent = by_id.get(m.get('parentId'))
        if parent is not None:
            parent['childrenIds'].append(m['id'])
    return messages


def project_session(meta: dict, rows: list[dict], *, user_id: str) -> dict:
    """引擎会话 meta+行 → Open WebUI Chat JSON(ChatResponse 兼容)。

    history.messages=id→消息映射(前端 loadChat 首选形态),messages=同批对象
    平铺(convertMessagesToHistory 兼容);current_message_id/currentId=末条。
    files/variables 等安全缺省;meta 只传 {}(引擎 meta_json 是引擎内部纪要,
    不进 WebUI)。"""
    messages = rows_to_chat_messages(rows, model_id=DEFAULT_MODEL_ID)
    messages_map = {m['id']: m for m in messages}
    current_id = messages[-1]['id'] if messages else None
    title = str(meta.get('title') or '')
    chat_payload = {
        'id': meta.get('id'),
        'title': title,
        'models': [DEFAULT_MODEL_ID],
        'history': {'messages': messages_map, 'currentId': current_id},
        'messages': messages,
        'params': {},
        'files': [],
        'share_mode': None,
    }
    return {
        'id': meta.get('id'),
        'user_id': user_id,
        'title': title,
        'chat': chat_payload,
        'updated_at': int(meta.get('updated_at') or time.time()),
        'created_at': int(meta.get('created_at') or time.time()),
        'share_id': None,
        'archived': bool(meta.get('archived')),
        'pinned': bool(meta.get('pinned')),
        'meta': {},
        'variables': {},
        'folder_id': None,
        'tasks': None,
        'summary': None,
        'current_message_id': current_id,
    }


def project_session_summary(meta: dict) -> dict:
    """引擎会话行 → ChatTitleIdResponse 形状(列表项;pinned 由调用方过滤)。"""
    return {
        'id': meta.get('id'),
        'title': str(meta.get('title') or ''),
        'updated_at': int(meta.get('updated_at') or 0),
        'created_at': int(meta.get('created_at') or 0),
        'archived': bool(meta.get('archived')),
        'pinned': bool(meta.get('pinned')),
    }


# ── 引擎会话读取(详情+行全量回补)──


async def fetch_session(sess_id: str) -> Optional[dict]:
    """GET /api/sessions/{id}:meta+尾窗行(引擎 TAIL_LIMIT=50)。404→None。"""
    r = await _engine_call('GET', f'/api/sessions/{quote(sess_id, safe="")}')
    if r.status_code != 200:
        return None
    return r.json()


async def fetch_all_rows(sess_id: str, detail: dict) -> list[dict]:
    """尾窗行 + /rows 上滚补页 → 全量行(升序;行是超集,零信息损失)。
    单机数据量小,补页循环有 _ROWS_MAX_PAGES 防御上限。"""
    rows: list[dict] = list(detail.get('rows') or [])
    total = int(detail.get('total') or len(rows))
    pages = 0
    while rows and len(rows) < total and pages < _ROWS_MAX_PAGES:
        before_seq = rows[0].get('seq', 0)
        r = await _engine_call(
            'GET',
            f'/api/sessions/{quote(sess_id, safe="")}/rows',
            params={'before_seq': before_seq, 'limit': _ROWS_PAGE},
        )
        pages += 1
        if r.status_code != 200:
            log.warning('banyan_chat_adapter: 行补页失败 %s@%s(%s)', sess_id, before_seq, r.status_code)
            break
        older = r.json().get('rows') or []
        if not older:
            break
        rows = older + rows
    return rows


async def get_chat(sess_id: str, user_id: str) -> Optional[dict]:
    """引擎会话 → Chat JSON(投影);会话不存在或引擎不可达 → None。"""
    try:
        detail = await fetch_session(sess_id)
        if detail is None:
            return None
        meta = detail.get('meta') or {}
        rows = await fetch_all_rows(sess_id, detail)
        return project_session(meta, rows, user_id=user_id)
    except Exception as e:  # 引擎不可达等——投影失败降级为 404,不炸路由
        log.warning('banyan_chat_adapter: 读取会话 %s 异常: %s', sess_id, e)
        return None


async def get_session_meta(sess_id: str) -> Optional[dict]:
    """只取会话 meta(pinned/archived 翻转等轻量用途)。"""
    try:
        detail = await fetch_session(sess_id)
        return (detail or {}).get('meta')
    except Exception as e:
        log.warning('banyan_chat_adapter: 读取会话 meta %s 异常: %s', sess_id, e)
        return None


# ── 创建 / 保存(no-op) / 更新 / 删除 ─


async def create_chat(user_id: str, title: str = '') -> Optional[dict]:
    """引擎默认项目下建空会话 → Chat JSON(id=sess_*,WebUI 零行)。

    title 恒空传引擎:引擎 title_source=first_message 首条消息自动出题;
    带 'New Chat' 之类占位会短路引擎的自动标题。失败返回 None(调用方回落
    旧路径,绝不阻断)。"""
    try:
        key = await default_project_key()
        if not key:
            return None
        r = await _engine_call(
            'POST',
            f'/api/projects/{quote(key, safe="")}/sessions',
            json={'title': ''},
        )
        if r.status_code != 200:
            log.warning('banyan_chat_adapter: 建会话失败(%s %s)', r.status_code, r.text[:200])
            return None
        sid = (r.json() or {}).get('id')
        if not sid:
            return None
        now = int(time.time())
        return project_session(
            {'id': sid, 'title': '', 'created_at': now, 'updated_at': now,
             'pinned': False, 'archived': False},
            [],
            user_id=user_id,
        )
    except Exception as e:
        log.warning('banyan_chat_adapter: 建会话异常: %s', e)
        return None


async def mint_engine_chat_id(request: Any = None, model_id: Optional[str] = None) -> Optional[str]:
    """完成流新建对话的 id 铸造:模型指向引擎时先建引擎会话返回 sess_*,
    否则(非引擎模型/无法判定/引擎失败)返回 None——调用方回落 uuid4+本地行。
    D16' 边界:非引擎模型的消息引擎没有行,零存储会丢历史,故必须回落。"""
    if request is not None and model_id:
        try:
            from open_webui.routers.openai import get_openai_connection

            entry = (getattr(request.app.state, 'OPENAI_MODELS', None) or {}).get(model_id) or {}
            idx = entry.get('urlIdx')
            if idx is None:
                return None  # 非openai连接(Ollama等):非引擎,回落本地
            url, _key, _config = await get_openai_connection(idx)
            if not is_banyan_target(url):
                return None
        except Exception as e:
            log.warning('banyan_chat_adapter: 引擎目标判定失败(%s),回落本地', e)
            return None
    created = await create_chat(user_id='')  # 铸造阶段无 user 上下文,仅取 id
    return (created or {}).get('id')


async def save_chat(sess_id: str, data: dict, user_id: str) -> Optional[dict]:
    """保存 no-op(D16' 核心裁决):完成的完成流不持久化,消息唯一落点=引擎行。

    拉引擎现值投影回显(前端内存态已与流一致,回显只为路由签名兼容);
    引擎不可达时回显入参合成最小 Chat JSON,绝不写 WebUI 库。"""
    log.debug('banyan_chat_adapter: save skipped for engine chat %s (D16\' zero dual-write)', sess_id)
    chat = await get_chat(sess_id, user_id)
    if chat is not None:
        return chat
    chat_data = data if isinstance(data, dict) else {}
    now = int(time.time())
    return {
        'id': sess_id,
        'user_id': user_id,
        'title': str(chat_data.get('title') or ''),
        'chat': {**chat_data, 'share_mode': None},
        'updated_at': now,
        'created_at': now,
        'share_id': None,
        'archived': False,
        'pinned': False,
        'meta': {},
        'variables': {},
        'folder_id': None,
        'tasks': None,
        'summary': None,
        'current_message_id': (chat_data.get('history') or {}).get('currentId'),
    }


async def patch_engine_session(sess_id: str, fields: dict) -> bool:
    """引擎 PATCH /api/sessions/{id}(title/pinned/archived/read)。失败只记日志。"""
    if not fields:
        return False
    try:
        r = await _engine_call('PATCH', f'/api/sessions/{quote(sess_id, safe="")}', json=fields)
        if r.status_code != 200:
            log.warning('banyan_chat_adapter: patch %s 失败(%s %s)', sess_id, r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.warning('banyan_chat_adapter: patch %s 异常: %s', sess_id, e)
        return False


async def update_chat(sess_id: str, data: dict, user_id: str) -> Optional[dict]:
    """更新映射:WebUI update 载荷 {title/models/history/params/files} ∩ 引擎
    PATCH 列(title) → 引擎;folders/tags 无引擎对应,忽略。返回投影现值。"""
    fields: dict = {}
    title = data.get('title') if isinstance(data, dict) else None
    if isinstance(title, str) and title.strip():
        fields['title'] = title.strip()
    if isinstance(data, dict):
        if isinstance(data.get('pinned'), bool):
            fields['pinned'] = data['pinned']
        if isinstance(data.get('archived'), bool):
            fields['archived'] = data['archived']
    if fields:
        await patch_engine_session(sess_id, fields)
    return await get_chat(sess_id, user_id)


async def delete_chat(sess_id: str) -> bool:
    """删除=引擎 archived=true(置态留史,不物理删,对齐"分支靠指针不靠删除")。"""
    return await patch_engine_session(sess_id, {'archived': True})


async def toggle_chat_flag(sess_id: str, field: str, user_id: str) -> Optional[dict]:
    """pinned/archived 翻转(WebUI pin/archive 端点是 toggle 语义):读现值→
    取反→PATCH→返回投影。引擎不可达返回 None。"""
    meta = await get_session_meta(sess_id)
    if meta is None:
        return None
    current = bool(meta.get(field))
    if not await patch_engine_session(sess_id, {field: not current}):
        return None
    return await get_chat(sess_id, user_id)


async def mark_chat_read(sess_id: str) -> bool:
    return await patch_engine_session(sess_id, {'read': True})


async def write_back_title(sess_id: str, title: str) -> bool:
    """F13 标题回写半边:任务轮(title 生成)产出的题目写回引擎会话。

    判定(RV-23W E3-P2-4)``title_source != 'custom'`` 即 PATCH——修前"仅引擎
    title 为空才 PATCH"是恒 no-op:引擎首条真实轮先以首条消息截 50 字定题
    (engine.py:_chat_turn,title_source=first_message),任务轮到达时 title 恒
    非空,回写永不发生;改后引擎首条截断题允许被 LLM 标题升级。仅
    title_source=custom(人改名,引擎 PATCH title 会置 custom 短路自动标题)
    永不覆盖。引擎不可得/条件不符返回 False(调用方静默跳过,绝不阻断)。"""
    title = (title or '').strip()
    if not title:
        return False
    meta = await get_session_meta(sess_id)
    if not meta:
        return False
    if meta.get('title_source') == 'custom':
        return False
    return await patch_engine_session(sess_id, {'title': title})


async def bulk_set_archived(archived: bool) -> int:
    """批量置态(bulk 端点的引擎半边):archive/all、unarchive/all、delete-all
    按 D16' 删除=archived=true 的同构语义逐会话 PATCH;返回成功数。
    单机数据量小,逐会话轻 PATCH 可接受(_LIST_MAX 上限防御)。"""
    metas = await list_sessions_raw(archived=not archived, want=_LIST_MAX)
    ok = 0
    for m in metas:
        if await patch_engine_session(str(m.get('id') or ''), {'archived': archived}):
            ok += 1
    return ok


async def bulk_mark_read() -> int:
    """批量已读(RF-16 L1-10,POST /chats/read 的引擎半边):未归档会话逐个
    read=true(接通既有 mark_chat_read——此前已实现未接线);返回成功数。"""
    metas = await list_sessions_raw(archived=False, want=_LIST_MAX)
    ok = 0
    for m in metas:
        if await mark_chat_read(str(m.get('id') or '')):
            ok += 1
    return ok


# ── 列表投影 ─


async def list_sessions_raw(archived: bool = False, want: int = 20,
                            q: str = '') -> list[dict]:
    """引擎会话列表(默认项目;updated_at DESC 键集分页循环拉满 want 条)。
    q:标题 LIKE 下推引擎(M-8① 同款参数,搜索合并用)。"""
    key = await default_project_key()
    if not key:
        return []
    out: list[dict] = []
    before = ''
    while len(out) < want:
        limit = min(100, max(1, want - len(out)))
        path = (f'/api/projects/{quote(key, safe="")}/sessions'
                f'?archived={str(archived).lower()}&limit={limit}')
        if q:
            path += f'&q={quote(q, safe="")}'
        if before:
            path += f'&before={quote(before, safe="")}'
        r = await _engine_call('GET', path)
        if r.status_code != 200:
            log.warning('banyan_chat_adapter: 会话列表不可得(%s %s)', r.status_code, r.text[:200])
            break
        batch = r.json() or []
        out.extend(batch)
        if len(batch) < limit:
            break
        last = batch[-1]
        before = f'{last.get("updated_at", 0)},{last.get("id", "")}'
    return out


async def list_chats(
    *,
    archived: bool = False,
    pinned: Optional[bool] = None,
    page: Optional[int] = None,
    limit: int = 60,
    q: str = '',
) -> list[dict]:
    """引擎会话 → ChatTitleIdResponse 形状列表(updated_at DESC)。

    分页:引擎只有键集分页无 offset——按 limit×page 拉足后切片(单机数据量小,
    注释声明);page=None 时全量拉取(_LIST_MAX 上限)。pinned 过滤在投影侧做
    (引擎列表端点无 pinned 参数);q 为标题 LIKE 下推引擎(搜索投影)。"""
    want = _LIST_MAX if page is None else max(limit, limit * max(1, page))
    metas = await list_sessions_raw(archived=archived, want=want, q=q)
    if pinned is not None:
        metas = [m for m in metas if bool(m.get('pinned')) is pinned]
    if page is not None:
        start = (max(1, page) - 1) * limit
        metas = metas[start : start + limit]
    return [project_session_summary(m) for m in metas]
