"""banyan conv 绑定（P0 修复，FU-2 执行项 1 / 审计域10 头号项）。

**D16' 退役说明（完整方案 §4.5/F7，勿增新依赖）：** chat id 即引擎会话 id
（``sess_*``）后，本模块的"建会话+meta 绑定回写"机制退役——新对话的引擎会话
由 ``utils/banyan_chat_adapter.py``（chats 路由适配投影）创建，``sess_*`` 直接
作为 chat id，``resolve_conv_header`` 对 sess_ chat 直通返回（不再查绑定表）。
本模块保留仅为两类存量场景：
- 非 sess_ 存量 chat（旧副本）的绑定解析/删除归档/改名同步，只读到自然淘汰；
- ``resolve_conv_header`` 的旧路径兜底（meta.banyan_conv_id）。
新代码一律走 banyan_chat_adapter；不要在本模块加新功能。

背景：引擎 v1 会话映射为 ``X-Banyan-Conv 头 > model id 编码 > banyan-duty=默认实例``
（``banyan/human/v1_api.py:_resolve_conv``）。fork 透传层此前不注入任何 conv 头，
所有 WebUI 对话汇入引擎同一个默认 conv——树页/审计页按 conv 组织的假定失真，
K1 正本"每个 WebUI chat 一个引擎会话"的预期不成立。

本模块修复该断裂，实现 **WebUI chat ↔ 引擎 session 1:1 绑定**：

- chat 首条消息转发前，若无绑定则经引擎 API（``POST /api/projects/{key}/sessions``）
  在引擎默认项目下建一个会话，把返回的 ``sess_*`` id 回写进
  ``chat.meta.banyan_conv_id``（WebUI 库），随后在 openai 转发请求注入
  ``X-Banyan-Conv`` 头；同对话后续轮次直接复用 meta 里的绑定。
- 只有**真实对话轮**参与映射：后台任务（title/tags/follow_up/autocomplete/query
  等，metadata 带 ``task`` 键）不注入头——否则任务 prompt 会作为正式 turn 落进
  绑定会话污染 K1 正本（修复前默认 conv 的标题就是被 title 任务 prompt 污染的
  实证）。临时/本地/频道对话（未落库 chat id）同样不映射，落引擎默认实例。
- **绝不阻断对话**：映射不可得（引擎不可达、chat 行缺失、meta 回写失败等）时
  返回 None，调用方不注入头，行为降级回修复前（引擎默认实例）并记日志。

quick-win 复用（审计域10）：``conv_id_for_chat`` 供对话删除→引擎归档、改名→
引擎 title 同步取绑定；``patch_engine_session`` 封装引擎
``PATCH /api/sessions/{conv_id}``（title/archived）。

引擎访问沿用代理桥同款 env（``BANYAN_ENGINE_URL`` / ``BANYAN_TOKEN``，见
routers/banyan.py §3），不经 /banyan/api 桥（那是前端通道），后端直连。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional
from urllib.parse import quote, urlparse

import httpx

from open_webui.utils.chat_id import is_saved_chat_id

log = logging.getLogger(__name__)

#: 注入的请求头（引擎 v1_api 按小写读取 x-banyan-conv）
CONV_HEADER = 'X-Banyan-Conv'
#: chat.meta 里的绑定键名
META_KEY = 'banyan_conv_id'
#: 引擎 API 调用超时（秒）——建会话/补丁都属轻量短调用
_API_TIMEOUT = 10.0
#: 每 chat 建会话锁（防止同 chat 并发首条消息双建引擎会话）
_chat_locks: dict[str, asyncio.Lock] = {}


def engine_base_url() -> str:
    """引擎 base URL（与代理桥同源 env；尾斜杠归一）。"""
    return os.environ.get('BANYAN_ENGINE_URL', 'http://localhost:8420').rstrip('/')


def _engine_headers() -> dict[str, str]:
    headers = {'Accept': 'application/json'}
    token = os.environ.get('BANYAN_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def is_banyan_target(url: str) -> bool:
    """判断一个 openai 连接 URL 是否指向 banyan 引擎（scheme+netloc 相等）。

    openai 连接配的是引擎 /v1（如 ``http://127.0.0.1:8000/v1``），引擎 env 是
    根地址（``http://127.0.0.1:8000``）——按 origin 比较容忍路径差异；host 写法
    不同（localhost vs 127.0.0.1）不视为同一目标，此时不注入头（降级为引擎默认
    实例，即修复前行为）。
    """
    try:
        engine = urlparse(engine_base_url())
        target = urlparse(url or '')
        return bool(target.netloc) and (engine.scheme, engine.netloc) == (
            target.scheme,
            target.netloc,
        )
    except Exception:
        return False


def _chat_lock(chat_id: str) -> asyncio.Lock:
    lock = _chat_locks.get(chat_id)
    if lock is None:
        lock = _chat_locks.setdefault(chat_id, asyncio.Lock())
    return lock


async def _engine_call(method: str, path: str, **kwargs) -> httpx.Response:
    url = f'{engine_base_url()}{path}'
    timeout = httpx.Timeout(_API_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.request(method, url, headers=_engine_headers(), **kwargs)


async def _default_project_key() -> Optional[str]:
    """引擎默认项目 key（sort_order 最小者；引擎 _default_conv 用 realpath(workspace)
    作默认项目 key，每次默认轮都会 upsert，列表首项即它）。"""
    r = await _engine_call('GET', '/api/projects')
    if r.status_code != 200:
        log.warning('banyan_conv: 引擎项目列表不可得(%s %s)', r.status_code, r.text[:200])
        return None
    projects = r.json()
    if not isinstance(projects, list) or not projects:
        log.warning('banyan_conv: 引擎无项目，无法建会话')
        return None
    return min(projects, key=lambda p: p.get('sort_order', 0)).get('key')


async def _create_engine_session() -> Optional[str]:
    """在引擎默认项目下建空会话，返回 sess_* id；失败返回 None（不抛）。"""
    try:
        key = await _default_project_key()
        if not key:
            return None
        r = await _engine_call(
            'POST',
            f'/api/projects/{quote(key, safe="")}/sessions',
            json={'title': ''},
        )
        if r.status_code != 200:
            log.warning('banyan_conv: 建引擎会话失败(%s %s)', r.status_code, r.text[:200])
            return None
        sid = r.json().get('id')
        return str(sid) if sid else None
    except Exception as e:  # 引擎不可达等——降级，不阻断对话
        log.warning('banyan_conv: 建引擎会话异常: %s', e)
        return None


async def _persist_conv_binding(chat_id: str, conv_id: str) -> bool:
    from open_webui.models.chats import Chats

    meta = await Chats.update_chat_meta_by_id(chat_id, {META_KEY: conv_id})
    if meta is None:
        log.warning('banyan_conv: conv 绑定回写失败(chat %s -> %s)', chat_id, conv_id)
        return False
    return True


async def resolve_conv_for_chat(chat_id: str) -> Optional[str]:
    """取/建 chat 的引擎会话绑定：meta 有则直用；无则建引擎会话并回写 meta。

    返回 None 表示映射不可得（调用方降级为不注入头）。chat 行缺失（理论上首条
    消息前 initChatHandler 已落库）同样返回 None。
    """
    from open_webui.models.chats import Chats

    chat = await Chats.get_chat_by_id(chat_id)
    if chat is None:
        log.debug('banyan_conv: chat %s 不存在，跳过映射', chat_id)
        return None
    bound = (chat.meta or {}).get(META_KEY)
    if bound:
        return str(bound)

    async with _chat_lock(chat_id):
        # double-check：等锁期间并发请求可能已建好并回写
        chat = await Chats.get_chat_by_id(chat_id)
        bound = (chat.meta or {}).get(META_KEY) if chat else None
        if bound:
            return str(bound)
        conv_id = await _create_engine_session()
        if conv_id is None:
            return None
        if chat is None or not await _persist_conv_binding(chat_id, conv_id):
            # 回写失败也返回 conv_id：本进程内该 chat 的本轮已建，宁可用上
            # （进程重启后 meta 仍缺失会再建一个——单主人场景可接受，记日志可查）
            log.warning('banyan_conv: chat %s 绑定 %s 未持久化', chat_id, conv_id)
        log.info('banyan_conv: chat %s 绑定引擎会话 %s', chat_id, conv_id)
        return conv_id


async def conv_id_for_chat(chat_id: str) -> Optional[str]:
    """只读取绑定（不建会话）——quick-win（删除→归档/改名→title）用。"""
    from open_webui.models.chats import Chats

    chat = await Chats.get_chat_by_id(chat_id)
    if chat is None:
        return None
    bound = (chat.meta or {}).get(META_KEY)
    return str(bound) if bound else None


async def patch_engine_session(conv_id: str, *, title: Optional[str] = None,
                               archived: Optional[bool] = None) -> bool:
    """引擎 PATCH /api/sessions/{conv_id}（title / archived）。失败只记日志。"""
    fields: dict = {}
    if title is not None:
        fields['title'] = title
    if archived is not None:
        fields['archived'] = archived
    if not fields:
        return False
    try:
        r = await _engine_call('PATCH', f'/api/sessions/{quote(conv_id, safe="")}',
                               json=fields)
        if r.status_code != 200:
            log.warning('banyan_conv: patch 引擎会话 %s 失败(%s %s)',
                        conv_id, r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        log.warning('banyan_conv: patch 引擎会话 %s 异常: %s', conv_id, e)
        return False


async def resolve_conv_header(metadata: Optional[dict], url: str) -> Optional[str]:
    """openai.py 转发前钩点：判定应否注入 X-Banyan-Conv，返回 conv id 或 None。

    判定链（任一不满足即 None，调用方不注入头）：
    1. 转发目标是引擎（origin 相等）；
    2. metadata 带已落库 chat_id（临时/本地/频道对话不映射）；
    3. **D16' 快路径：chat_id 以 sess_ 开头 → 本身即引擎会话 id，直通返回**
       （不查绑定表、不建会话——绑定机制已退役）；
    4. 非 sess_ 存量 chat：旧路径 meta 绑定兜底（首条消息建会话+回写，只服务
       存量副本到自然淘汰）。
    """
    if not is_banyan_target(url):
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get('task'):
        return None
    chat_id = metadata.get('chat_id')
    if not is_saved_chat_id(chat_id):
        return None
    # D16'：chat id 即引擎会话 id——零查询直通（适配器见 banyan_chat_adapter.py）
    if isinstance(chat_id, str) and chat_id.startswith('sess_'):
        return chat_id
    try:
        return await resolve_conv_for_chat(str(chat_id))
    except Exception as e:  # 绝不让映射问题炸掉对话
        log.warning('banyan_conv: 解析 chat %s 绑定异常: %s', chat_id, e)
        return None
