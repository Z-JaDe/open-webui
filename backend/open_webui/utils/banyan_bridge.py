"""banyan 代理桥路径守卫(P2-f-1;纯标准库模块——与 banyan_stream 同款
importlib 直载测试模式,不经 open_webui 包 __init__ 拉起完整后端依赖树)。

背景(FA-final §9-1):桥 catch-all `{path:path}` 原样捕获点段路径,
`target_url = f"{ENGINE}/api/{path}"` 拼好后 httpx 按 RFC3986 对目标 URL 做
点段消除——`/banyan/api/../../v1/models` 与编码变体(`%2e%2e`、`..%2f`)规范化
成 `{ENGINE}/v1/models`,逃出 `/api` 命名空间。桥的"1:1 追加转发"契约被破坏:
设 BANYAN_TOKEN 时静态凭证自动随行直达引擎 `/v1`、`/docs`、`/openapi.json`。
转发前在此拦截:解码后含 `..` 段或反斜杠的路径一律拒绝(调用方回 400,
不转发)。
"""

from __future__ import annotations

from urllib.parse import unquote

#: 解码轮数:捕获层(Starlette)已 URL 解码一次;这里再解两遍防御双重/三重
#: 编码(%252e%252e → %2e%2e → ..)。点段消除前拦截,不依赖 httpx 的规范化行为。
_DECODE_ROUNDS = 2


def safe_bridge_path(path: str) -> str | None:
    """规范化桥转发路径;逃逸形态返回 None。

    判据(解码后):
    - 任一路径段为 ``..`` → 逃逸(../、%2e%2e、..%2f、双重编码全覆盖);
    - 含反斜杠 → 拒绝(部分服务器把 ``\\`` 当段分隔符,不赌对端语义)。
    合法路径返回解码后的规范化输入(转发用同一形态,所见即所验)。
    """
    decoded = path
    for _ in range(_DECODE_ROUNDS):
        decoded = unquote(decoded)
    if "\\" in decoded:
        return None
    if any(seg == ".." for seg in decoded.split("/")):
        return None
    return decoded
