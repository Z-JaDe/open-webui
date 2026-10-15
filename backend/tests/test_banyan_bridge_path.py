"""代理桥路径守卫单测（P2-f-1：点段路径穿越逃逸 /api 命名空间）。

本仓库尚无后端测试基建，按既有"最小测试"模式（test_banyan_passthrough.py）：
importlib 直载 ``open_webui/utils/banyan_bridge.py``（纯标准库模块，不经
open_webui 包 __init__，避免拉起完整后端依赖树），穷举 FA-final §9-1 的
穿越变体（../、%2e%2e、..%2f、双重编码、反斜杠）与合法路径对照；
另以源码断言钉住 banyan.py 的接线（400 不转发）。

运行：cd backend && python3 -m pytest tests/test_banyan_bridge_path.py -q
"""

import importlib.util
import pathlib
import types

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / 'open_webui'
    / 'utils'
    / 'banyan_bridge.py'
)


def _load_banyan_bridge() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        'banyan_bridge_under_test', _MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load_banyan_bridge()

# FA-final §9-1 复现的全部变体(按到达守卫时的形态:Starlette 捕获层已 URL
# 解码一次——变体含其后仍残留的编码形态)
TRAVERSAL_VARIANTS = [
    '../../v1/models',          # 原样点段(--path-as-is 直达)
    '../..%2Fv1/models',        # 段内部分编码
    '%2e%2e/%2e%2e/v1/models',  # 全编码点段(若捕获层未解码)
    '%252e%252e/v1/models',     # 双重编码(守卫两轮解码后现形)
    '..%252Fv1',                # 段内双重编码(三轮合计解码后现形)
    '..',                       # 纯点段
    'plans/../../openapi.json', # 合法前缀夹带逃逸尾段
    'plans/x\\..\\..\\v1',      # 反斜杠形态
    'plans\\..\\..\\v1',        # 纯反斜杠分隔
]

LEGIT_PATHS = [
    'registry',
    'cards',
    'cards/card-1/resolve',
    'plans/plan_abc123',
    'plans/plan_abc123/resolve',
    'audit?type=plan&limit=50',  # query 不入 path 参数,原样含 ? 也不受影响
    'chats/sess_def456/tree',
    './registry',                # 同段点不构成逃逸(留在命名空间内)
]


def test_traversal_variants_all_rejected():
    """穿越变体全部返回 None(调用方回 400,不转发)。"""
    for p in TRAVERSAL_VARIANTS:
        assert bridge.safe_bridge_path(p) is None, f'{p!r} 必须判为逃逸'


def test_legit_paths_pass_through():
    """合法路径原样放行(1:1 追加转发契约不受伤)。"""
    for p in LEGIT_PATHS:
        assert bridge.safe_bridge_path(p) == p, f'{p!r} 必须放行'


def test_double_decoding_reveals_dot_segments():
    """双重编码 %252e%252e:守卫两轮解码后出现 `..` 段 → 拒。"""
    assert bridge.safe_bridge_path('%252e%252e/secret') is None
    # 单层编码在同层已现形
    assert bridge.safe_bridge_path('%2e%2e/secret') is None


def test_multi_round_encoding_caught_with_capture_layer():
    """端到端账:捕获层(Starlette)解码一轮 + 守卫两轮 = 原始 URL 三重编码仍在网。
    原始 `..%2525%32F` 形态经捕获层后即下式(守卫输入形态)。"""
    assert bridge.safe_bridge_path('..%252Fsecret') is None


def test_router_wiring_rejects_before_forward():
    """banyan.py 确实接线:守卫 None → 400(detail JSON),target_url 用净化后路径。"""
    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'open_webui'
        / 'routers'
        / 'banyan.py'
    ).read_text(encoding='utf-8')

    assert 'from open_webui.utils.banyan_bridge import safe_bridge_path' in source
    assert 'safe_path = safe_bridge_path(path)' in source
    assert 'HTTP_400_BAD_REQUEST' in source, '逃逸形态回 400,不转发'
    assert 'target_url = f"{BANYAN_ENGINE_URL}/api/{safe_path}"' in source, \
        '转发用的是守卫净化后的路径'
