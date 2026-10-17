"""banyan chats 适配投影单测(完整方案 §4.5 D16' 零双写,F7)。

与 test_banyan_conv.py 同款"最小测试"原则:importlib 直载
``open_webui/utils/banyan_chat_adapter.py``(模块顶部只依赖 httpx 与标准库,
WebUI 库 import 全部函数内 lazy),引擎 API 以假 ``_engine_call`` 桩掉,
并向 sys.modules 注入 WebUI 库桩模块(写方法被调即断言失败)以证明
**零 WebUI 库写入**。

覆盖:
- 行 → 消息投影:userInput/assistantText/toolCall/ticket/marker → 消息 +
  banyanEvents[](形状对齐前端 types.ts:BanyanToolEvent/BanyanSubagentEvent);
- project_session:Chat JSON 形状(history 映射 + 平铺 + currentId);
- create_chat:建引擎会话返回 sess_* chat id;
- save_chat no-op:绝不写 WebUI 库(写桩即炸),打引擎现值回显;
- update/delete/pin/archive:引擎 PATCH 映射(title/pinned/archived/read);
- list_chats:引擎键集分页 → ChatTitleId 形状 + page 切片 + pinned 过滤;
- resolve_conv_header(banyan_conv)sess_ 快路径:直通返回、零绑定查询。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_chat_adapter.py -q
"""

import importlib.util
import json
import pathlib
import sys
import types

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'utils' / 'banyan_chat_adapter.py'
)
_CONV_PATH = pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'utils' / 'banyan_conv.py'


def _load_module(path: pathlib.Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = types.ModuleType(name) if spec is None else importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(coro):
    import asyncio
    return asyncio.run(coro)


ba = _load_module(_MODULE_PATH, 'banyan_chat_adapter_under_test')
bc = _load_module(_CONV_PATH, 'banyan_conv_under_test')

ENGINE = 'http://127.0.0.1:8000'


# ── 桩具 ──


class _Resp:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text or json.dumps(payload or {})

    def json(self):
        return self._payload


def _install_engine(monkeypatch, module, routes):
    """按 (method, path 前缀) 匹配的引擎桩;记录全部调用供断言。
    最长前缀优先('/api/projects/%2Fw/sessions' 不得被 '/api/projects' 吞掉);
    callable 路由支持同步/异步 (path, kwargs) → _Resp。"""
    calls: list[tuple[str, str, dict | None]] = []

    async def _engine_call(method, path, **kwargs):
        clean = path.split('?')[0]
        calls.append((method, clean, kwargs.get('json')))
        matches = [r for r in routes if r[0] == method and clean.startswith(r[1])]
        if matches:
            resp = max(matches, key=lambda r: len(r[1]))[2]
            if callable(resp):
                out = resp(path, kwargs)
                if hasattr(out, '__await__'):
                    out = await out
                return out
            return resp
        return _Resp(404, {'detail': 'no route'})

    monkeypatch.setattr(module, '_engine_call', _engine_call)
    return calls


def _install_webui_db_guard(monkeypatch):
    """向 sys.modules 注入 open_webui.models.chats 桩:任何写方法被调即炸。
    适配器在任何路径 import 它都意味着触碰 WebUI 库——测试据此断言零写入。"""
    guard = types.ModuleType('open_webui.models.chats')

    class _Boom:
        def __getattr__(self, name):
            def _fail(*a, **k):
                raise AssertionError(f'WebUI 库写入被调: Chats.{name}')

            return _fail

    guard.Chats = _Boom()
    top = types.ModuleType('open_webui')
    models = types.ModuleType('open_webui.models')
    monkeypatch.setitem(sys.modules, 'open_webui', top)
    monkeypatch.setitem(sys.modules, 'open_webui.models', models)
    monkeypatch.setitem(sys.modules, 'open_webui.models.chats', guard)


# ── 行 → 事件(形状对齐前端 types.ts)──


def test_toolcall_row_to_tool_event():
    ev = ba.row_to_event({
        'row_id': 'row_a1', 'kind': 'toolCall', 'ts': 1728800000.5, 'status': None,
        'data': {'tool': 'query_inbox', 'args': {'limit': 5}, 'output': '3 cards'},
    })
    assert ev['type'] == 'tool' and ev['call_id'] == 'row_a1' and ev['name'] == 'query_inbox'
    assert ev['status'] == 'ok' and ev['output_summary'] == '3 cards'
    assert json.loads(ev['args_summary']) == {'limit': 5}
    assert ev['ended_at'] == 1728800000500 and ev['ts'] == 1728800000500  # epoch ms


def test_toolcall_row_error_status():
    ev = ba.row_to_event({'row_id': 'r', 'kind': 'toolCall', 'ts': 1.0, 'status': 'error', 'data': {}})
    assert ev['status'] == 'error'


def test_ticket_row_to_subagent_event():
    ev = ba.row_to_event({
        'row_id': 'row_b2', 'kind': 'ticket', 'ts': 1728800001.0, 'status': None,
        'data': {'ticket_id': 'tk_9', 'kind': 'requirement', 'title': '排查X',
                 'state': 'running', 'latest_action': '已开单'},
    })
    # 引擎 v1 编排线同款映射:ticket→subagent;work_id=ticket_id 保 /work/cancel 可达
    assert ev['type'] == 'subagent' and ev['subagent_id'] == 'tk_9' and ev['work_id'] == 'tk_9'
    assert ev['title'] == '排查X' and ev['latest_action'] == '已开单' and ev['status'] == 'running'
    assert ev['ts'] == 1728800001000


def test_ticket_state_mapping():
    for state, want in (('done', 'done'), ('cancelled', 'stopped'), ('failed', 'failed'), ('waiting_human', 'running')):
        ev = ba.row_to_event({'row_id': 'r', 'kind': 'ticket', 'ts': 1.0, 'status': None,
                              'data': {'ticket_id': 't', 'state': state}})
        assert ev['status'] == want, state


def test_marker_row_passthrough_and_unknown_kind():
    ev = ba.row_to_event({'row_id': 'r', 'kind': 'marker', 'ts': 1.0, 'status': None,
                          'data': {'marker': 'compact', 'text': '上下文已压缩'}})
    assert ev == {'type': 'marker', 'marker': 'compact', 'text': '上下文已压缩', 'ts': 1000}
    assert ba.row_to_event({'row_id': 'r', 'kind': 'future', 'ts': 1.0, 'status': None, 'data': {}}) is None


# ── 行 → 消息投影 ─


def _turn_rows():
    return [
        {'row_id': 'row_u1', 'turn_id': 't1', 'seq': 1, 'kind': 'userInput', 'ts': 100.0,
         'status': None, 'data': {'text': '帮我排查X'}},
        {'row_id': 'row_a1', 'turn_id': 't1', 'seq': 2, 'kind': 'assistantText', 'ts': 101.0,
         'status': None, 'data': {'text': '方案如下'}},
        {'row_id': 'row_t1', 'turn_id': 't1', 'seq': 3, 'kind': 'toolCall', 'ts': 102.0,
         'status': None, 'data': {'tool': 'query_inbox', 'args': {}, 'output': 'ok'}},
        {'row_id': 'row_k1', 'turn_id': 't1', 'seq': 4, 'kind': 'ticket', 'ts': 103.0,
         'status': None, 'data': {'ticket_id': 'tk_1', 'title': '修复X', 'state': 'running',
                                  'latest_action': '已开单'}},
        {'row_id': 'row_m1', 'turn_id': 't1', 'seq': 5, 'kind': 'marker', 'ts': 104.0,
         'status': None, 'data': {'marker': 'notice', 'text': '见待审卡'}},
    ]


def test_rows_to_chat_messages_shape():
    messages = ba.rows_to_chat_messages(_turn_rows())
    assert [m['id'] for m in messages] == ['row_u1', 'row_a1']
    user, assistant = messages
    assert user['role'] == 'user' and user['content'] == '帮我排查X' and user['parentId'] is None
    assert assistant['role'] == 'assistant' and assistant['content'] == '方案如下'
    assert assistant['parentId'] == 'row_u1' and assistant['done'] is True
    # childrenIds 链自建(线性树):loadChat 直接消费 history 映射,不走
    # convertMessagesToHistory——父节点 childrenIds 需投影侧补齐
    assert user['childrenIds'] == ['row_a1'] and assistant['childrenIds'] == []
    # 三个非文本行按行序归入同 turn assistant 消息的 banyanEvents[](零信息损失)
    events = assistant['banyanEvents']
    assert [e['type'] for e in events] == ['tool', 'subagent', 'marker']


def test_rows_streaming_and_pending_and_error():
    rows = [
        {'row_id': 'row_u1', 'turn_id': 't1', 'seq': 1, 'kind': 'userInput', 'ts': 100.0,
         'status': None, 'data': {'text': '危险操作', 'confirmed': False}},  # echo 待确认
        {'row_id': 'row_a1', 'turn_id': 't1', 'seq': 2, 'kind': 'assistantText', 'ts': 101.0,
         'status': 'streaming', 'data': {'text': '正在…'}},
        {'row_id': 'row_u2', 'turn_id': 't2', 'seq': 3, 'kind': 'userInput', 'ts': 200.0,
         'status': None, 'data': {'text': '确认'}},
        {'row_id': 'row_a2', 'turn_id': 't2', 'seq': 4, 'kind': 'assistantText', 'ts': 201.0,
         'status': 'error', 'data': {'text': '(对话失败:boom)'}},
    ]
    messages = ba.rows_to_chat_messages(rows)
    assert messages[0]['pending'] is True
    assert messages[1]['done'] is False  # streaming 行 → 进行中
    assert messages[2]['parentId'] == 'row_a1'
    assert messages[3]['done'] is True and messages[3]['error'] == {'content': '(对话失败:boom)'}


def test_events_before_any_assistant_text_are_kept():
    rows = [
        {'row_id': 'row_t0', 'turn_id': 't1', 'seq': 1, 'kind': 'toolCall', 'ts': 100.0,
         'status': None, 'data': {'tool': 'x', 'args': None, 'output': ''}},
        {'row_id': 'row_a1', 'turn_id': 't1', 'seq': 2, 'kind': 'assistantText', 'ts': 101.0,
         'status': None, 'data': {'text': 'hi'}},
    ]
    messages = ba.rows_to_chat_messages(rows)
    assert len(messages) == 2  # 空壳承载 + 正文
    assert messages[0]['banyanEvents'][0]['type'] == 'tool'
    assert messages[1]['content'] == 'hi'


# ── 会话投影 ─


def test_project_session_chat_json_shape():
    chat = ba.project_session(
        {'id': 'sess_abc', 'title': '排查X', 'created_at': 1728800000.0,
         'updated_at': 1728800100.0, 'pinned': True, 'archived': False},
        _turn_rows(),
        user_id='u1',
    )
    assert chat['id'] == 'sess_abc' and chat['user_id'] == 'u1'
    assert chat['title'] == '排查X' and chat['pinned'] is True and chat['archived'] is False
    assert chat['updated_at'] == 1728800100 and chat['created_at'] == 1728800000
    history = chat['chat']['history']
    assert history['currentId'] == 'row_a1' and set(history['messages']) == {'row_u1', 'row_a1'}
    # 首条 parentId=null + 父 childrenIds 链(前端 createMessagesList 沿 parentId
    # 上溯构造请求 messages——链断则发送消息恒空)
    assert history['messages']['row_u1']['parentId'] is None
    assert history['messages']['row_u1']['childrenIds'] == ['row_a1']
    assert [m['id'] for m in chat['chat']['messages']] == ['row_u1', 'row_a1']
    assert chat['current_message_id'] == 'row_a1'
    assert chat['chat']['files'] == [] and chat['meta'] == {} and chat['folder_id'] is None


# ── create / get / save no-op / update / delete ─


def test_create_chat_returns_engine_session_id(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [
        ('GET', '/api/projects', _Resp(200, [{'key': '/w', 'sort_order': 0}])),
        ('POST', '/api/projects/%2Fw/sessions', _Resp(200, {'id': 'sess_new1'})),
    ])
    chat = _run(ba.create_chat('u1'))
    assert chat['id'] == 'sess_new1' and chat['title'] == '' and chat['chat']['messages'] == []
    assert ('POST', '/api/projects/%2Fw/sessions', {'title': ''}) in calls  # 标题恒空:引擎自动出题


def test_create_chat_downgrades_on_engine_failure(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    _install_engine(monkeypatch, ba, [('GET', '/api/projects', _Resp(500, {}, text='boom'))])
    assert _run(ba.create_chat('u1')) is None


def test_get_chat_projects_full_history_with_row_backfill(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    tail = [_turn_rows()[4]]
    older = _turn_rows()[:4]

    def rows_endpoint(path, kwargs):
        before = int((kwargs.get('params') or {}).get('before_seq', 0))
        return _Resp(200, {'rows': [r for r in older if r['seq'] < before]})

    _install_engine(monkeypatch, ba, [
        ('GET', f'/api/sessions/sess_abc/rows', rows_endpoint),
        ('GET', '/api/sessions/sess_abc', _Resp(
            200, {'meta': {'id': 'sess_abc', 'title': 'T', 'created_at': 1.0, 'updated_at': 2.0,
                           'pinned': False, 'archived': False},
                  'rows': tail, 'total': 5, 'last_seq': 5})),
    ])
    chat = _run(ba.get_chat('sess_abc', 'u1'))
    assert chat is not None and chat['title'] == 'T'
    # 尾窗 1 行 + 上滚补页 4 行 = 全量;3 个编排行归并为 row_a1 的 banyanEvents
    # (行是超集,零信息损失:5 行 → 2 消息 + 3 事件)
    assert len(chat['chat']['history']['messages']) == 2
    assert [e['type'] for e in chat['chat']['history']['messages']['row_a1']['banyanEvents']] == [
        'tool', 'subagent', 'marker']


def test_save_chat_is_noop_and_never_touches_webui_db(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    _install_webui_db_guard(monkeypatch)
    _install_engine(monkeypatch, ba, [
        ('GET', '/api/sessions/sess_abc', _Resp(
            200, {'meta': {'id': 'sess_abc', 'title': '引擎正本', 'created_at': 1.0,
                           'updated_at': 2.0, 'pinned': False, 'archived': False},
                  'rows': _turn_rows(), 'total': 5, 'last_seq': 5})),
    ])
    incoming = {'title': 'New Chat', 'models': ['banyan-duty'], 'history': {'messages': {}, 'currentId': 'x'}}
    chat = _run(ba.save_chat('sess_abc', incoming, 'u1'))
    # 回显的是引擎现值,不是入参——完成的完成流不持久化,消息唯一落点=引擎行
    assert chat['title'] == '引擎正本'
    assert len(chat['chat']['history']['messages']) == 2


def test_save_chat_echo_fallback_when_engine_down(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)

    async def _dead(method, path, **kwargs):
        raise ConnectionError('engine down')

    monkeypatch.setattr(ba, '_engine_call', _dead)
    chat = _run(ba.save_chat('sess_abc', {'title': '本地暂态'}, 'u1'))
    assert chat['id'] == 'sess_abc' and chat['title'] == '本地暂态'  # 回显入参,绝不写库


def test_update_chat_patches_engine_title(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [
        ('PATCH', '/api/sessions/sess_abc', _Resp(200, {'ok': True})),
        ('GET', '/api/sessions/sess_abc', _Resp(
            200, {'meta': {'id': 'sess_abc', 'title': '新名', 'created_at': 1.0, 'updated_at': 2.0,
                           'pinned': False, 'archived': False}, 'rows': [], 'total': 0, 'last_seq': 0})),
    ])
    chat = _run(ba.update_chat('sess_abc', {'title': '新名', 'history': {}}, 'u1'))
    assert chat['title'] == '新名'
    assert ('PATCH', '/api/sessions/sess_abc', {'title': '新名'}) in calls


def test_delete_chat_archives_not_deletes(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [('PATCH', '/api/sessions/sess_abc', _Resp(200, {'ok': True}))])
    assert _run(ba.delete_chat('sess_abc')) is True
    assert calls[0] == ('PATCH', '/api/sessions/sess_abc', {'archived': True})  # 置态留史


def test_toggle_flags_read_current_then_flip(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    state = {'pinned': False}
    patches = []

    async def patch(path, kwargs):
        patches.append(kwargs['json'])
        state['pinned'] = kwargs['json']['pinned']
        return _Resp(200, {'ok': True})

    meta = {'id': 'sess_abc', 'title': 'T', 'created_at': 1.0, 'updated_at': 2.0,
            'pinned': False, 'archived': False}

    def get_session(path, kwargs):
        return _Resp(200, {'meta': {**meta, 'pinned': state['pinned']}, 'rows': [], 'total': 0, 'last_seq': 0})

    _install_engine(monkeypatch, ba, [
        ('PATCH', '/api/sessions/sess_abc', patch),
        ('GET', '/api/sessions/sess_abc', get_session),
    ])
    chat = _run(ba.toggle_chat_flag('sess_abc', 'pinned', 'u1'))
    assert patches == [{'pinned': True}] and chat['pinned'] is True


def test_mark_chat_read(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [('PATCH', '/api/sessions/sess_abc', _Resp(200, {'ok': True}))])
    assert _run(ba.mark_chat_read('sess_abc')) is True
    assert calls[0][2] == {'read': True}


# ── 列表投影 ─


def test_list_chats_projects_and_filters_pinned(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    _install_engine(monkeypatch, ba, [
        ('GET', '/api/projects', _Resp(200, [{'key': '/w', 'sort_order': 0}])),
        ('GET', '/api/projects/%2Fw/sessions', _Resp(200, [
            {'id': 'sess_a', 'title': 'A', 'created_at': 1.0, 'updated_at': 30.0,
             'pinned': False, 'archived': False},
            {'id': 'sess_b', 'title': 'B', 'created_at': 2.0, 'updated_at': 20.0,
             'pinned': True, 'archived': False},
            {'id': 'sess_c', 'title': 'C', 'created_at': 3.0, 'updated_at': 10.0,
             'pinned': False, 'archived': False},
        ])),
    ])
    items = _run(ba.list_chats())
    assert [i['id'] for i in items] == ['sess_a', 'sess_b', 'sess_c']  # 引擎序(updated_at DESC)
    assert items[0]['updated_at'] == 30 and items[0]['title'] == 'A'
    pinned_only = _run(ba.list_chats(pinned=True))
    assert [i['id'] for i in pinned_only] == ['sess_b']


def test_list_chats_pages_via_keyset_fetch_and_slice(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)

    def sessions(path, kwargs):
        before = path.split('before=')[1] if 'before=' in path else ''
        limit = int(path.split('limit=')[1].split('&')[0]) if 'limit=' in path else 20
        all_sorted = [
            {'id': f'sess_{i:02d}', 'title': str(i), 'created_at': float(i),
             'updated_at': float(i), 'pinned': False, 'archived': False}
            for i in range(9, -1, -1)
        ]
        if before:
            cutoff = float(before.split(',')[0])  # 引擎键集即 (updated_at,id),ts 是浮点秒
            all_sorted = [m for m in all_sorted if m['updated_at'] < cutoff]
        return _Resp(200, all_sorted[:limit])

    _install_engine(monkeypatch, ba, [
        ('GET', '/api/projects', _Resp(200, [{'key': '/w', 'sort_order': 0}])),
        ('GET', '/api/projects/%2Fw/sessions', sessions),
    ])
    page2 = _run(ba.list_chats(page=2, limit=4))
    assert [i['id'] for i in page2] == ['sess_05', 'sess_04', 'sess_03', 'sess_02']


def test_list_chats_pushes_q_title_search_down(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    seen: list[str] = []

    async def sessions(path, kwargs):
        seen.append(path)
        return _Resp(200, [{'id': 'sess_q1', 'title': '排查X', 'created_at': 1.0,
                            'updated_at': 5.0, 'pinned': False, 'archived': False}])

    _install_engine(monkeypatch, ba, [
        ('GET', '/api/projects', _Resp(200, [{'key': '/w', 'sort_order': 0}])),
        ('GET', '/api/projects/%2Fw/sessions', sessions),
    ])
    items = _run(ba.list_chats(q='排查', limit=20))
    assert [i['id'] for i in items] == ['sess_q1']
    assert any('q=%E6%8E%92%E6%9F%A5' in p for p in seen)  # q 经 URL 编码下推引擎


# ── F13 标题回写(sess_ 任务轮 → 引擎 PATCH title,保守裁决)──


def _title_meta(**kw):
    meta = {'id': 'sess_abc', 'title': '', 'title_source': 'first_message',
            'created_at': 1.0, 'updated_at': 2.0, 'pinned': False, 'archived': False}
    meta.update(kw)
    return meta


def test_write_back_title_patches_when_engine_title_empty(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [
        ('GET', '/api/sessions/sess_abc', _Resp(200, {'meta': _title_meta(), 'rows': [], 'total': 0})),
        ('PATCH', '/api/sessions/sess_abc', _Resp(200, {'ok': True})),
    ])
    assert _run(ba.write_back_title('sess_abc', '  排查X并修复 ')) is True
    assert ('PATCH', '/api/sessions/sess_abc', {'title': '排查X并修复'}) in calls  # 去首尾空白


def test_write_back_title_never_overwrites_existing_title(monkeypatch):
    """引擎首条消息 50 字截断已先行定题 → 任务轮题目不覆盖(F13 保守裁决)。"""
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [
        ('GET', '/api/sessions/sess_abc',
         _Resp(200, {'meta': _title_meta(title='帮我排查X并修复'), 'rows': [], 'total': 0})),
        ('PATCH', '/api/sessions/sess_abc', _Resp(200, {'ok': True})),
    ])
    assert _run(ba.write_back_title('sess_abc', '任务轮题目')) is False
    assert all(m != 'PATCH' for m, _p, _j in calls)  # 零 PATCH


def test_write_back_title_never_overwrites_custom_source(monkeypatch):
    """title_source=custom(人改名)→ 永不覆盖,即使 title 恰为空。"""
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [
        ('GET', '/api/sessions/sess_abc',
         _Resp(200, {'meta': _title_meta(title='', title_source='custom'), 'rows': [], 'total': 0})),
    ])
    assert _run(ba.write_back_title('sess_abc', '任务轮题目')) is False
    assert all(m != 'PATCH' for m, _p, _j in calls)


def test_write_back_title_skips_empty_and_engine_down(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    calls = _install_engine(monkeypatch, ba, [])
    assert _run(ba.write_back_title('sess_abc', '   ')) is False  # 空题不发起任何调用
    assert calls == []

    async def _dead(method, path, **kwargs):
        raise ConnectionError('engine down')

    monkeypatch.setattr(ba, '_engine_call', _dead)
    assert _run(ba.write_back_title('sess_abc', '排查X')) is False  # 引擎不可达降级 False


# ── 批量置态(archive/all、unarchive/all、delete-all 的引擎半边)──


def test_bulk_set_archived_patches_matching_side(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    patches: list[dict | None] = []

    async def patch(path, kwargs):
        patches.append(kwargs.get('json'))
        return _Resp(200, {'ok': True})

    _install_engine(monkeypatch, ba, [
        ('GET', '/api/projects', _Resp(200, [{'key': '/w', 'sort_order': 0}])),
        ('GET', '/api/projects/%2Fw/sessions', _Resp(200, [
            {'id': 'sess_1', 'title': 'a', 'created_at': 1.0, 'updated_at': 3.0,
             'pinned': False, 'archived': False},
            {'id': 'sess_2', 'title': 'b', 'created_at': 2.0, 'updated_at': 2.0,
             'pinned': False, 'archived': False},
        ])),
        ('PATCH', '/api/sessions/sess_', patch),
    ])
    assert _run(ba.bulk_set_archived(True)) == 2  # 归档动作拉未归档侧,逐个置 archived=true
    assert patches == [{'archived': True}, {'archived': True}]


# ── resolve_conv_header(banyan_conv)sess_ 快路径 ─


def test_resolve_conv_header_passthrough_for_engine_chat(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    hit = []

    async def _must_not_call(chat_id):
        hit.append(chat_id)
        return 'bound_conv'

    monkeypatch.setattr(bc, 'resolve_conv_for_chat', _must_not_call)
    conv = _run(bc.resolve_conv_header({'chat_id': 'sess_direct1'}, ENGINE + '/v1'))
    assert conv == 'sess_direct1'  # chat id 即引擎会话 id,零查询直通
    assert hit == []               # 绑定表查询已跳过


def test_resolve_conv_header_legacy_binding_path_intact(monkeypatch):
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)

    async def _legacy(chat_id):
        return 'bound_legacy'

    monkeypatch.setattr(bc, 'resolve_conv_for_chat', _legacy)
    assert _run(bc.resolve_conv_header({'chat_id': 'legacy_uuid'}, ENGINE + '/v1')) == 'bound_legacy'
    # 后台任务轮照旧不注入(D5 无状态通道)
    assert _run(bc.resolve_conv_header({'chat_id': 'sess_x', 'task': 'title'}, ENGINE + '/v1')) is None


# ── C1-3:X-Banyan-Task 注头判定(RF-16 红绿)──


def test_task_header_requires_engine_target_and_task_metadata(monkeypatch):
    """判定形态复用 RF-11 铸造点(is_banyan_target origin 相等):目标为引擎且
    metadata 带 task(title/tags/补全等自动轮)→ 注 X-Banyan-Task: 1。"""
    monkeypatch.setenv('BANYAN_ENGINE_URL', ENGINE)
    assert bc.resolve_task_header({'task': True, 'chat_id': 'sess_x'}, ENGINE + '/v1') is True
    assert bc.resolve_task_header({'task': 'title'}, ENGINE + '/v1') is True
    # 真实对话轮(无 metadata.task)不注——引擎按有头与否分流无状态通道
    assert bc.resolve_task_header({'chat_id': 'sess_x'}, ENGINE + '/v1') is False
    assert bc.resolve_task_header(None, ENGINE + '/v1') is False
    # 目标非引擎(同引擎 origin 判定形态):任务轮头不外泄给第三方连接
    assert bc.resolve_task_header({'task': True}, 'https://api.openai.com/v1') is False


def test_openai_py_wires_task_header_source_pin():
    """源码钉线(C1-3):openai.py generate_chat_completion 转发处按
    resolve_task_header(metadata.task + 引擎目标)注 X-Banyan-Task(真机联测
    归部署阶段;openai.py 全量 import 链太重,单测以源码线+判定函数双钉)。"""
    src = (pathlib.Path(__file__).resolve().parents[1] / 'open_webui' / 'routers' / 'openai.py').read_text()
    assert 'X-Banyan-Task' in src, 'openai.py 未注 X-Banyan-Task(C1-3 红态)'
    assert 'resolve_task_header' in src, '注头未复用 banyan_conv.resolve_task_header 判定'
