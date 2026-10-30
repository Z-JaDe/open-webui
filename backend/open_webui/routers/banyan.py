"""
banyan 代理桥（统一设计 §6.1 / §8 G4）

fork 自家 FastAPI 增加 /banyan/api/* 反向代理，把前端五路由与组件的全部数据
请求转发到 banyan 引擎 API（env BANYAN_ENGINE_URL），并桥接鉴权：

- 引擎地址：env `BANYAN_ENGINE_URL`（默认 http://localhost:8000）。
  该地址作为 base，代理按原路径 1:1 追加：
    /banyan/api/plans/x/resolve  ->  {BANYAN_ENGINE_URL}/plans/x/resolve
  若引擎挂在子路径下，直接把子路径写进 BANYAN_ENGINE_URL 即可
  （例如 http://engine:8000/api/v1）。
- 鉴权桥接（RFF P1 修正：Authorization 必须**替换**而非叠加）：
  - env `BANYAN_TOKEN` 设置时，剥离客户端自带的 Authorization 头（大小写不敏感），
    以静态 `Authorization: Bearer <token>` 转发——此前 dict 大小写敏感两键并存、
    httpx 依序双发，引擎 Starlette 首者胜取到客户端 webui JWT，静态桥对自家
    前端失效、hub 模式整桥 401（FA-v2 §9-3）；
  - 未设置时，透传前端请求自带的 Authorization 头。
- 前端仍走 Open WebUI 自己的登录态（get_verified_user），未登录用户不能借道。

路径规则与引擎端点对应（前端 $lib/apis/banyan）：
  GET  /registry                      断言登记簿
  GET  /cards                         语义卡列表
  POST /cards/resolve                 审卡批准/驳回（body {id, decision}，非子路径）
  GET  /audit                         K1 事件浏览（支持 chat_id/type/limit query）
  GET  /events                        K1 事件流 SSE 透传（D15/F8，专用端点见下）
  GET  /plans/{plan_id}               方案快照（plan + wave_updates）
  POST /plans/{plan_id}/resolve       方案批准/驳回/选B
  GET  /chats/{chat_id}/tree          会话树
  POST /chats/{chat_id}/tree/switch   切换活动分支（引擎对端缺位，404 提示；台账已登记）
  POST /work/{id}/cancel              停止子代理（RF-Z 真实对端；旧 /subagents/{id}/stop 引擎无此路由已弃）
"""

import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from open_webui.utils.auth import get_verified_user
from open_webui.utils.banyan_bridge import safe_bridge_path

log = logging.getLogger(__name__)

router = APIRouter()

BANYAN_ENGINE_URL = os.environ.get("BANYAN_ENGINE_URL", "http://localhost:8000").rstrip("/")
BANYAN_TOKEN = os.environ.get("BANYAN_TOKEN", "")
BANYAN_TIMEOUT = float(os.environ.get("BANYAN_TIMEOUT", "300"))

# ── V4W-1 云端第二上游(只读聚合)──
# BANYAN_CLOUD_URL=云端引擎基址(如 https://login.pyrris.com,杭州引擎;
# 引擎 API 挂子路径时把子路径写进 URL,与 BANYAN_ENGINE_URL 同构);
# BANYAN_V1_TOKEN=云端引擎凭证(Authorization: Bearer,webui 后端直连公网)。
# 两者缺任一 = 聚合分支零行为(单上游直达,现形态)。
BANYAN_CLOUD_URL = os.environ.get("BANYAN_CLOUD_URL", "").rstrip("/")
BANYAN_V1_TOKEN = os.environ.get("BANYAN_V1_TOKEN", "")
BANYAN_CLOUD_TIMEOUT = float(os.environ.get("BANYAN_CLOUD_TIMEOUT", "10"))

# goals/status/nodes 三族 GET 才聚合(写操作与其余路径一律本地);列表族
# path → 响应列表键(goals/cards 的键是 cards)。
_CLOUD_LIST_PATHS = {"goals": "goals", "goals/cards": "cards", "nodes": "nodes"}

# 不向引擎转发的请求头（逐跳/本机头）
FORWARD_HEADERS_BLOCKLIST = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "accept-encoding",
}

# 不向客户端回传的响应头
RESPONSE_HEADERS_BLOCKLIST = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
}


############################
# Health
############################
@router.get("/health")
async def banyan_health(user: Any = Depends(get_verified_user)):
    """代理桥自身健康 + 引擎可达性探测（不透传，供排障）。"""
    engine_ok = False
    detail = ""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BANYAN_ENGINE_URL}/health")
            engine_ok = resp.status_code < 500
            detail = f"engine /health -> {resp.status_code}"
    except Exception as exc:  # noqa: BLE001 — 排障端点，任何失败都折进 detail
        detail = f"{type(exc).__name__}: {exc}"

    return {
        "status": "ok" if engine_ok else "degraded",
        "engine_url": BANYAN_ENGINE_URL,
        "auth_mode": "static_token" if BANYAN_TOKEN else "passthrough",
        "engine": {"reachable": engine_ok, "detail": detail},
    }


############################
# SSE events passthrough(F8-K1/D15:变化通知唯一源=引擎 K1 事件流)
############################
@router.get("/events")
async def banyan_events_proxy(
    request: Request,
    user: Any = Depends(get_verified_user),
):
    """K1 事件流透传:/banyan/api/events → 引擎 GET /api/events。

    引擎帧契约(banyan/human/api.py):hello 帧 {kind:'hello',seq};事件帧
    {seq,kind,ref,payload};15s keepalive 为注释帧(': keepalive\\n\\n')。

    与 catch-all 的差别只为 SSE 调对参数:
    - 鉴权:前端走浏览器原生 EventSource(带不了 Authorization 头),fork 侧依赖
      登录态 token cookie(get_current_user 同源自动携带,auths 落签时 set_cookie);
      上游鉴权与 catch-all 同款——BANYAN_TOKEN 注入,未设则透传客户端头。
    - read 超时=None:SSE 是长连,keepalive 之外允许空闲,不为读空闲误杀;
      客户端断开由 Starlette 取消响应生成器,finally 关上游(断开→上游断开)。
    - keepalive 注释帧原样透传,不做任何缓冲聚合;显式禁反代缓冲(x-accel-buffering)。
    """
    client_authorization = request.headers.get("authorization", "")
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in FORWARD_HEADERS_BLOCKLIST and key.lower() != "authorization"
    }
    if BANYAN_TOKEN:
        headers["Authorization"] = f"Bearer {BANYAN_TOKEN}"
    elif client_authorization:
        headers["Authorization"] = client_authorization  # 未设静态 token:透传原头
    headers.pop("cookie", None)

    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0)
    )
    upstream_request = client.build_request(
        "GET",
        f"{BANYAN_ENGINE_URL}/api/events",
        params=request.query_params,
        headers=headers,
    )
    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.ConnectError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine unreachable at {BANYAN_ENGINE_URL}: {exc}",
        )
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine events request failed: {exc}",
        )

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in RESPONSE_HEADERS_BLOCKLIST
    }
    response_headers["cache-control"] = "no-cache"
    response_headers["x-accel-buffering"] = "no"

    async def stream():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type", "text/event-stream"),
    )


############################
# V4W-1 云端第二上游聚合(goals/status/nodes 三族 GET,只读)
############################
def _json_bytes(payload: Any) -> bytes:
    """聚合响应序列化(ensure_ascii=False:中文 objective 原样)。"""
    import json as _json
    return _json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _cloud_should_aggregate(method: str, safe_path: str) -> bool:
    """聚合判定:GET + env 齐 + path 命中三族(goals* / status / nodes)。
    env 缺任一 = False(catch-all 单上游零行为);写操作永聚合(仍走本地)。"""
    if method != "GET" or not BANYAN_CLOUD_URL or not BANYAN_V1_TOKEN:
        return False
    if safe_path == "status" or safe_path in _CLOUD_LIST_PATHS:
        return True
    # goals/{goal_id}、goals/{goal_id}/convs(单条族:本地 404 云端回退);
    # goals/cards/{id}/resolve 等写路径是 POST,已被 method 门挡住。
    return safe_path.startswith("goals/")


def _cloud_host() -> str:
    return urlparse(BANYAN_CLOUD_URL).hostname or BANYAN_CLOUD_URL


def _raw_response(upstream: Any) -> Response:
    """上游响应原样回传(聚合分支内的非 200/形状漂移兜底,与 catch-all 流式
    语义等价:码/体/类型一致)。"""
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


async def _cloud_fetch(base: str, safe_path: str, request: Request,
                       headers: dict, timeout_s: float):
    """GET 单上游(stream=False 全量读);返回 (response|None, error|None)。
    响应体已读、连接即关;错误摘要不带完整 URL(内网路径不外泄)。"""
    client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))
    try:
        resp = await client.send(
            client.build_request(
                "GET", f"{base}/api/{safe_path}",
                params=request.query_params, headers=headers,
            ),
            stream=False,
        )
        return resp, None
    except (httpx.ConnectError, httpx.HTTPError) as exc:
        return None, f"{type(exc).__name__}: {exc}"[:200]
    finally:
        await client.aclose()


def _merge_list_rows(cloud_resp: Any, list_key: str) -> tuple[list, bool, str]:
    """云端响应 → (云端条目[每条 dict 拷贝+cloud: true], ok, error)。
    只读聚合:云端数据只拷贝不改写、绝不回写云端。"""
    if cloud_resp is None:
        return [], False, "unreachable"
    if cloud_resp.status_code != 200:
        return [], False, f"status {cloud_resp.status_code}"
    try:
        data = cloud_resp.json()
    except ValueError:
        return [], False, "bad json"
    rows = data.get(list_key) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return [], False, "bad shape"
    out = []
    for it in rows:
        if isinstance(it, dict):
            marked = dict(it)
            marked["cloud"] = True
            out.append(marked)
    return out, True, ""


async def _cloud_aggregate(safe_path: str, request: Request,
                           local_headers: dict):
    """三族 GET 聚合主流程:本地为主 + 云端标记(cloud: true)合并展示。

    - 列表族(goals / goals/cards / nodes):并发两路,本地条目前、云端
      条目带 cloud: true;顶层附 cloud 状态 {ok, host, count, error?}。
    - status 族:本地响应原样 + 顶层 cloud 概要 {ok, host, engine?}。
    - 单条族(goals/{id}、goals/{id}/convs):本地先行,200 直回不打云端;
      本地 404 → 云端试,命中则回云端体 + 顶层/条目 cloud: true(转录页
      可看云 goal);云端也 miss → 本地 404 原样。
    云端任何失败(不可达/非 200/坏 JSON)不拖垮本地:cloud.ok=false 诚实标注。
    """
    list_key = _CLOUD_LIST_PATHS.get(safe_path)
    is_status = safe_path == "status"
    host = _cloud_host()
    cloud_headers = {
        k: v for k, v in local_headers.items() if k.lower() != "authorization"
    }
    cloud_headers["Authorization"] = f"Bearer {BANYAN_V1_TOKEN}"

    # 单条族:本地先行(本地命中零外呼云端)
    if list_key is None and not is_status:
        local, lerr = await _cloud_fetch(
            BANYAN_ENGINE_URL, safe_path, request, local_headers, BANYAN_TIMEOUT)
        if lerr:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"banyan engine unreachable at {BANYAN_ENGINE_URL}: {lerr}",
            )
        if local.status_code != 404:
            return _raw_response(local)               # 本地为主:命中/其他码原样
        cloud, _ = await _cloud_fetch(
            BANYAN_CLOUD_URL, safe_path, request, cloud_headers,
            BANYAN_CLOUD_TIMEOUT)
        cloud_rows, ok, _err = (None, False, "")
        if cloud is not None and cloud.status_code == 200:
            try:
                data = cloud.json()
            except ValueError:
                data = None
            if isinstance(data, dict):
                data = dict(data)
                data["cloud"] = True                  # 顶层云标(转录页徽标)
                if isinstance(data.get("goal"), dict):
                    data["goal"] = dict(data["goal"])
                    data["goal"]["cloud"] = True
                return Response(
                    content=_json_bytes(data), media_type="application/json")
        return _raw_response(local)                   # 云端也 miss → 本地 404 原样

    # 列表/status 族:并发两路
    (local, lerr), (cloud, cerr) = await asyncio.gather(
        _cloud_fetch(BANYAN_ENGINE_URL, safe_path, request,
                     local_headers, BANYAN_TIMEOUT),
        _cloud_fetch(BANYAN_CLOUD_URL, safe_path, request,
                     cloud_headers, BANYAN_CLOUD_TIMEOUT),
    )
    if lerr:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine unreachable at {BANYAN_ENGINE_URL}: {lerr}",
        )
    if local.status_code != 200:
        return _raw_response(local)                   # 本地为主:非 200 原样透传
    try:
        local_data = local.json()
    except ValueError:
        return _raw_response(local)                   # 形状漂移:零聚合诚实透传

    if is_status:
        if not isinstance(local_data, dict):
            return _raw_response(local)
        out = dict(local_data)
        cloud_state = {"ok": False, "host": host}
        if cerr:
            cloud_state["error"] = cerr
        elif cloud is not None and cloud.status_code == 200:
            try:
                cd = cloud.json()
            except ValueError:
                cd = None
            if isinstance(cd, dict):
                cloud_state["ok"] = True
                eng = cd.get("engine")
                if isinstance(eng, dict):             # 云端 engine 概要(子集)
                    cloud_state["engine"] = {
                        k: eng[k] for k in ("status", "last_seq", "version")
                        if k in eng}
            else:
                cloud_state["error"] = "bad shape"
        else:
            cloud_state["error"] = f"status {cloud.status_code if cloud else 'unreachable'}"
        out["cloud"] = cloud_state
        return Response(content=_json_bytes(out), media_type="application/json")

    # 列表族
    local_rows = None
    if isinstance(local_data, dict):
        local_rows = local_data.get(list_key)
    elif isinstance(local_data, list):
        local_rows = local_data                       # 裸数组兜底(nodes F-10 旧形状)
    if not isinstance(local_rows, list):
        return _raw_response(local)                   # 键缺位:不猜形状,原样透传
    cloud_rows, ok, err = _merge_list_rows(cloud, list_key)
    out = {
        list_key: list(local_rows) + cloud_rows,      # 本地在前为主
        "cloud": {"ok": ok, "host": host, "count": len(cloud_rows)},
    }
    if not ok:
        out["cloud"]["error"] = err or cerr or "unknown"
    return Response(content=_json_bytes(out), media_type="application/json")


############################
# Catch-all proxy
############################
@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def banyan_proxy(
    path: str,
    request: Request,
    user: Any = Depends(get_verified_user),
):
    """把 /banyan/api/* 请求 1:1 转发到引擎，流式回传（兼容 SSE）。"""
    # P2-f-1:点段/反斜杠路径一律 400,不转发——{path:path} 原样捕获的点段
    # 会被 httpx 按 RFC3986 对目标 URL 做点段消除,`/api/../../v1/models`
    # 逃出 /api 命名空间(设 BANYAN_TOKEN 时静态凭证自动随行直达引擎
    # /v1、/docs、/openapi.json)。原样 ../、%2e%2e、..%2f、双重编码全覆盖。
    safe_path = safe_bridge_path(path)
    if safe_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="banyan bridge: path traversal rejected",
        )
    target_url = f"{BANYAN_ENGINE_URL}/api/{safe_path}"  # 引擎端点带 /api 前缀(E2E 修正)

    # RFF P1:Authorization 替换而非叠加——剥离客户端带来的头(大小写不敏感),
    # 防止 dict 里 "authorization" 与 "Authorization" 两键并存、httpx 双发、
    # 引擎首者胜取到 webui JWT 而整桥 401。
    client_authorization = request.headers.get("authorization", "")
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in FORWARD_HEADERS_BLOCKLIST and key.lower() != "authorization"
    }
    if BANYAN_TOKEN:
        headers["Authorization"] = f"Bearer {BANYAN_TOKEN}"
    elif client_authorization:
        headers["Authorization"] = client_authorization  # 未设静态 token:透传原头
    headers.pop("cookie", None)

    body = await request.body()

    # V4W-1:goals/status/nodes 三族 GET 云聚合(env 缺=判定 False,零行为直达
    # 下方单上游;写操作与其余路径永不聚合,仍走本地)
    if _cloud_should_aggregate(request.method, safe_path):
        return await _cloud_aggregate(safe_path, request, headers)

    # L1-11:client 建在 try 外——下方 ConnectError/HTTPError 分支 raise 前必须
    # aclose(与 /events 同款),否则引擎不可达时每请求漏一个连接池。
    client = httpx.AsyncClient(timeout=httpx.Timeout(BANYAN_TIMEOUT))
    try:
        upstream_request = client.build_request(
            request.method,
            target_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )
        upstream_response = await client.send(upstream_request, stream=True)
    except asyncio.CancelledError:
        # E3-P3-2:客户端断连取消同样会从 await 点冒出——CancelledError 是
        # BaseException,不入下方 HTTPError 分支,不 aclose 即漏一个连接池
        # (对齐 /events 端点与 L1-11 的收口纪律);收口后原样上抛保取消语义。
        await client.aclose()
        raise
    except httpx.ConnectError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine unreachable at {BANYAN_ENGINE_URL}: {exc}",
        )
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine request failed: {exc}",
        )

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in RESPONSE_HEADERS_BLOCKLIST
    }

    async def stream():
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
