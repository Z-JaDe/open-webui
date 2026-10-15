"""
banyan 代理桥（统一设计 §6.1 / §8 G4）

fork 自家 FastAPI 增加 /banyan/api/* 反向代理，把前端五路由与组件的全部数据
请求转发到 banyan 引擎 API（env BANYAN_ENGINE_URL），并桥接鉴权：

- 引擎地址：env `BANYAN_ENGINE_URL`（默认 http://localhost:8420）。
  该地址作为 base，代理按原路径 1:1 追加：
    /banyan/api/plans/x/resolve  ->  {BANYAN_ENGINE_URL}/plans/x/resolve
  若引擎挂在子路径下，直接把子路径写进 BANYAN_ENGINE_URL 即可
  （例如 http://engine:8420/api/v1）。
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
  POST /cards/{id}/resolve            审卡批准/驳回
  GET  /audit                         K1 事件浏览（支持 chat_id/type/limit query）
  GET  /plans/{plan_id}               方案快照（plan + wave_updates）
  POST /plans/{plan_id}/resolve       方案批准/驳回/选B
  GET  /chats/{chat_id}/tree          会话树
  POST /chats/{chat_id}/tree/switch   切换活动分支
  POST /chats/{chat_id}/tree/rerun    重跑某轮
  POST /subagents/{id}/stop           停止子代理
"""

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

BANYAN_ENGINE_URL = os.environ.get("BANYAN_ENGINE_URL", "http://localhost:8420").rstrip("/")
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
    target_url = f"{BANYAN_ENGINE_URL}/api/{path}"  # 引擎端点带 /api 前缀(E2E 修正)

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

    try:
        client = httpx.AsyncClient(timeout=httpx.Timeout(BANYAN_TIMEOUT))
        upstream_request = client.build_request(
            request.method,
            target_url,
            params=request.query_params,
            headers=headers,
            content=body,
        )
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"banyan engine unreachable at {BANYAN_ENGINE_URL}: {exc}",
        )
    except httpx.HTTPError as exc:
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
