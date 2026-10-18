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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from open_webui.utils.auth import get_verified_user
from open_webui.utils.banyan_bridge import safe_bridge_path

log = logging.getLogger(__name__)

router = APIRouter()

BANYAN_ENGINE_URL = os.environ.get("BANYAN_ENGINE_URL", "http://localhost:8000").rstrip("/")
BANYAN_TOKEN = os.environ.get("BANYAN_TOKEN", "")
BANYAN_TIMEOUT = float(os.environ.get("BANYAN_TIMEOUT", "300"))

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
