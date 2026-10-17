"""banyan 附件桥单测(RF-12;D18/D19/D20 中间件半边)。

同仓"最小测试"模式(test_banyan_conv.py / test_banyan_bridge_path.py):
importlib 直载 ``open_webui/utils/banyan_attach.py``(模块顶部零三方依赖),
覆盖:
- is_banyan_model 判定(banyan- 前缀 / meta.kind==tier / 非 banyan 对照);
- strip_multimodal_segments 多模态 base64 段剥离(image 段不进 payload);
- 附件行拼接(engine_path 三级取值链 + 按裁决格式逐文件一行,无在案不发空头);
- apply_banyan_engine_payload 单点携带(剥离+追加+计数,容错不抛);
- 上传转发降级(引擎不可达 → None,不抛——files.py 侧原行为照常);
- 源码钉线:middleware.py 三处接线 + files.py engine_bridge 只挂主上传端点。

运行:cd backend && python3 -m pytest tests/test_banyan_attach.py -q
"""

import asyncio
import importlib.util
import pathlib
import sys
import types

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / 'open_webui'
    / 'utils'
    / 'banyan_attach.py'
)


def _load_banyan_attach() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        'banyan_attach_under_test', _MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ba = _load_banyan_attach()

# ── is_banyan_model:前缀 / meta.kind / 对照 ──


def test_is_banyan_model_by_id_prefix():
    assert ba.is_banyan_model({'id': 'banyan-duty'})
    assert ba.is_banyan_model({'id': 'banyan-fast', 'info': {'meta': {}}})
    assert ba.is_banyan_model(None, 'banyan-duty')
    assert ba.is_banyan_model({'id': 'gpt-4o'}, 'banyan-fast')   # body id 优先判


def test_is_banyan_model_by_meta_kind_tier():
    # 引擎 /v1/models 条目原样透传:meta.kind=tier 即档位
    assert ba.is_banyan_model({'id': 'whatever', 'info': {'meta': {'kind': 'tier'}}})
    assert not ba.is_banyan_model({'id': 'gpt-4o', 'info': {'meta': {'kind': 'openai'}}})
    assert not ba.is_banyan_model({'id': 'gpt-4o'})
    assert not ba.is_banyan_model(None)
    assert not ba.is_banyan_model(None, 'gpt-4o')


# ── strip_multimodal_segments:多模态剥离(D18 防 token 爆炸)──

B64 = 'data:image/png;base64,iVBORw0KGgoAAAANSU' + 'A' * 200


def test_strip_multimodal_folds_single_text():
    msgs = [{'role': 'user', 'content': [
        {'type': 'text', 'text': '看这张图'},
        {'type': 'image_url', 'image_url': {'url': B64}},
    ]}]
    n = ba.strip_multimodal_segments(msgs)
    assert n == 1
    assert msgs[0]['content'] == '看这张图'          # 单文本段折回字符串
    assert B64 not in str(msgs)                      # base64 不在 payload


def test_strip_multimodal_keeps_multi_text_and_untouches_other_roles():
    msgs = [
        {'role': 'system', 'content': [
            {'type': 'text', 'text': 'sys'},
            {'type': 'image_url', 'image_url': {'url': B64}},   # system 不动
        ]},
        {'role': 'user', 'content': [
            {'type': 'text', 'text': 'a'},
            {'type': 'text', 'text': 'b'},
            {'type': 'image_url', 'image_url': {'url': B64}},
        ]},
        {'role': 'assistant', 'content': 'ok'},
        {'role': 'user', 'content': '纯文本'},
    ]
    n = ba.strip_multimodal_segments(msgs)
    assert n == 1
    assert msgs[0]['content'][1]['type'] == 'image_url'          # system 原样
    assert msgs[1]['content'] == [{'type': 'text', 'text': 'a'},
                                  {'type': 'text', 'text': 'b'}]
    assert msgs[3]['content'] == '纯文本'


def test_strip_multimodal_image_only_message_empties_text():
    msgs = [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': B64}}]}]
    assert ba.strip_multimodal_segments(msgs) == 1
    assert msgs[0]['content'] == ''


# ── 附件行拼接 + 单点携带(engine_path 三级取值链)──


def _file_item(engine_path, kind='file'):
    """前端 payload 形态:fileItem 挂整条 file 记录(item.file.meta.engine_path)。"""
    return {'type': kind, 'id': 'f1', 'name': '报表.pdf', 'url': 'f1',
            'file': {'id': 'f1', 'meta': {'engine_path': engine_path}}}


def test_engine_attachment_lines_format_and_chain():
    files = [
        _file_item('.banyan-uploads/260613-abc1-报表.pdf'),
        {'type': 'file', 'name': 'meta级.txt', 'meta': {'engine_path': '.banyan-uploads/x.txt'}},
        {'type': 'file', 'name': 'item级.txt', 'engine_path': '.banyan-uploads/y.txt'},
        {'type': 'collection', 'name': 'fork知识库', 'collection_names': ['c1']},  # 无 engine_path → 跳过
    ]
    block = ba.engine_attachment_lines(files)
    assert block.startswith('\n\n[附件已存引擎工作区]\n')
    lines = block.strip().split('\n')
    assert lines[0] == '[附件已存引擎工作区]'
    assert lines[1] == '- 报表.pdf @ .banyan-uploads/260613-abc1-报表.pdf'
    assert lines[2] == '- meta级.txt @ .banyan-uploads/x.txt'
    assert lines[3] == '- item级.txt @ .banyan-uploads/y.txt'
    assert len(lines) == 4                            # 无在案附件不进块
    assert ba.engine_attachment_lines([]) == ''
    assert ba.engine_attachment_lines(None) == ''


def test_engine_attachment_lines_flags_unsynced_uploads():
    """C1-5 红绿:file 项有 name 但 engine_path 缺失(上传时引擎不可达的降级件)
    不再静默跳过——生成模型与人都可见的未同步行;collection 非上传件仍跳过。"""
    files = [
        {'type': 'file', 'id': 'f2', 'name': '丢件.pdf'},   # 无任何 engine_path 链
        {'type': 'collection', 'name': 'fork知识库', 'collection_names': ['c1']},
    ]
    block = ba.engine_attachment_lines(files)
    assert '[附件未同步引擎: 丢件.pdf(上传时引擎不可达)]' in block
    assert 'fork知识库' not in block  # collection 不是上传件,不误报
    assert block.startswith('\n\n[附件已存引擎工作区]\n')


def test_engine_attachment_lines_mixed_synced_and_missed():
    files = [
        _file_item('.banyan-uploads/260613-abc1-报表.pdf'),
        {'type': 'file', 'id': 'f2', 'name': '降级.txt', 'meta': {}},  # meta 空无 engine_path
    ]
    block = ba.engine_attachment_lines(files)
    assert '- 报表.pdf @ .banyan-uploads/260613-abc1-报表.pdf' in block
    assert '- [附件未同步引擎: 降级.txt(上传时引擎不可达)]' in block
    # 全员未同步同样可见(不因空 synced 列表丢整块)
    only_missed = ba.engine_attachment_lines([{'type': 'file', 'id': 'f3', 'name': 'a.png'}])
    assert '附件未同步引擎: a.png' in only_missed


def test_files_router_engine_cap_413_pinned():
    """C1-5 源码钉线:files.py 上传桥对引擎帽(20MB)预检 413 明示,不制造
    必丢的降级件(files.py 全量 import 链重,以源码线钉;真机联测归部署阶段)。"""
    assert 'ENGINE_ATTACHMENT_MAX_BYTES' in _FILES
    assert 'HTTP_413_REQUEST_ENTITY_TOO_LARGE' in _FILES


def test_apply_banyan_engine_payload_appends_to_last_user_message():
    form_data = {'messages': [
        {'role': 'user', 'content': [
            {'type': 'text', 'text': '第一条(历史)'},
            {'type': 'image_url', 'image_url': {'url': B64}},
        ]},
        {'role': 'assistant', 'content': '好的'},
        {'role': 'user', 'content': '帮我看报表'},
    ]}
    metadata = {'files': [_file_item('.banyan-uploads/260613-abc1-报表.pdf')]}
    out = ba.apply_banyan_engine_payload(form_data, metadata)
    assert out == {'stripped': 1, 'attached': 1}
    # 引擎 _last_user_text 读最后一条 user——块必须落在它尾部
    assert form_data['messages'][2]['content'] == (
        '帮我看报表\n\n[附件已存引擎工作区]\n- 报表.pdf @ .banyan-uploads/260613-abc1-报表.pdf'
    )
    assert form_data['messages'][0]['content'] == '第一条(历史)'
    # 第二轮:metadata.files 已无在案附件 → 不重复追加
    out2 = ba.apply_banyan_engine_payload(form_data, {'files': []})
    assert out2 == {'stripped': 0, 'attached': 0}


def test_apply_banyan_engine_payload_never_raises():
    assert ba.apply_banyan_engine_payload({}, {}) == {'stripped': 0, 'attached': 0}
    assert ba.apply_banyan_engine_payload({'messages': None}, None)['attached'] == 0
    assert ba.apply_banyan_engine_payload({'messages': [{'role': 'user'}]},
                                          {'files': ['oops', 3]})['attached'] == 0


# ── 上传转发降级(引擎不可达 → None,不抛)──


def _install_engine_conv_stub(monkeypatch, base_url):
    """懒加载链 open_webui.utils.banyan_conv → 注入桩模块(不拉起 WebUI 后端)。"""
    stub_conv = types.ModuleType('open_webui.utils.banyan_conv')
    stub_conv.engine_base_url = lambda: base_url
    stub_conv._engine_headers = lambda: {'Accept': 'application/json'}
    stub_pkg = types.ModuleType('open_webui')
    stub_utils = types.ModuleType('open_webui.utils')
    monkeypatch.setitem(sys.modules, 'open_webui', stub_pkg)
    monkeypatch.setitem(sys.modules, 'open_webui.utils', stub_utils)
    monkeypatch.setitem(sys.modules, 'open_webui.utils.banyan_conv', stub_conv)


def test_forward_attachment_degrades_on_engine_down(monkeypatch):
    _install_engine_conv_stub(monkeypatch, 'http://127.0.0.1:1')   # 连接拒绝
    out = asyncio.run(ba.forward_attachment_to_engine('a.txt', b'hello', 'text/plain'))
    assert out is None, "引擎不可达必须降级返回 None(不阻断上传、不抛)"


def test_forward_attachment_degrades_on_non_200(monkeypatch):
    class _Resp:
        status_code = 413
        text = '{"detail":"attachment too large"}'

        def json(self):
            return {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Resp()

    import httpx as _real_httpx
    _install_engine_conv_stub(monkeypatch, 'http://engine.local')
    stub_httpx = types.ModuleType('httpx')
    stub_httpx.AsyncClient = _Client
    stub_httpx.Timeout = _real_httpx.Timeout
    monkeypatch.setitem(sys.modules, 'httpx', stub_httpx)
    out = asyncio.run(ba.forward_attachment_to_engine('a.txt', b'hello'))
    assert out is None


def test_forward_attachment_returns_path_on_200(monkeypatch):
    class _Resp:
        status_code = 200
        text = ''

        def json(self):
            return {'id': 'att_x', 'path': '.banyan-uploads/260613-abc1-a.txt',
                    'name': 'a.txt', 'size': 5}

    class _Client:
        def __init__(self, *a, **k):
            self.posts = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            self.posts.append((url, k))
            return _Resp()

    import httpx as _real_httpx
    _install_engine_conv_stub(monkeypatch, 'http://engine.local')
    client = _Client()
    stub_httpx = types.ModuleType('httpx')
    stub_httpx.AsyncClient = lambda *a, **k: client
    stub_httpx.Timeout = _real_httpx.Timeout
    monkeypatch.setitem(sys.modules, 'httpx', stub_httpx)
    out = asyncio.run(ba.forward_attachment_to_engine('a.txt', b'hello'))
    assert out == '.banyan-uploads/260613-abc1-a.txt'
    url, kwargs = client.posts[0]
    assert url == 'http://engine.local/api/files'    # 引擎端点带 /api 前缀
    assert 'file' in kwargs['files']


# ── 源码钉线:三处中间件接线 + files.py 转发只挂主上传端点 ──

_MIDDLEWARE = (pathlib.Path(__file__).resolve().parents[1]
               / 'open_webui' / 'utils' / 'middleware.py').read_text(encoding='utf-8')
_FILES = (pathlib.Path(__file__).resolve().parents[1]
          / 'open_webui' / 'routers' / 'files.py').read_text(encoding='utf-8')


def test_middleware_wiring_pinned():
    assert "banyan_model = is_banyan_model(model, form_data.get('model'))" in _MIDDLEWARE
    # D20:features.memory 强制 False(client 供值不可信)
    assert "features['memory'] = False" in _MIDDLEWARE
    # D19:chroma RAG 短路(检索+rag_template 注入同源,一并短路)
    assert 'if file_context_enabled and not banyan_model:' in _MIDDLEWARE
    # D18:会话轮携带单点
    assert 'apply_banyan_engine_payload(form_data, metadata)' in _MIDDLEWARE


def test_files_router_wiring_pinned():
    # 主上传端点挂桥;handler 缺省关(models/images/retrieval 等共用者不转发)
    assert 'engine_bridge=True' in _FILES
    assert 'engine_bridge: bool = False' in _FILES
    assert 'forward_attachment_to_engine' in _FILES
    assert "'engine_path': engine_path" in _FILES
