"""chats 路由 sess_ 消息级端点 404 分流接线测试(RV-23W E3-P2-5)。

引擎会话(sess_*)的消息级操作(消息编辑/删除、消息事件、compact、fork、clone)
无 WebUI 侧对端:修前落 `Chats.get_chat_by_id` 零行 → 401 裸错;修后
`_reject_engine_chat_operation` 早 404,中文 detail 透传前端提示。

chats.py 依赖面极重(config/models/socket 全链),无法像其余 banyan 单测那样
importlib 桩载——本文件直接导入**真包** `open_webui.routers.chats`(venv 内依赖
齐全)。因其余 banyan 单测已向 sys.modules 注入非包 `open_webui` 桩(遮蔽真包
子模块解析),导入前先摘桩、导毕按现场恢复(各桩型单测持模块对象直引,不受扰动)。

运行:cd backend && ../venv/bin/python -m pytest tests/test_banyan_sess_message_guards.py -q
"""

import asyncio
import os
import sys

os.environ.setdefault('WEBUI_SECRET_KEY', 'test-secret-only-for-import')

#: 摘除其余单测注入的 open_webui.* 桩,让真包按文件系统正常解析
_STUBBED = {
    name: mod
    for name, mod in sys.modules.items()
    if name == 'open_webui' or name.startswith('open_webui.')
}
for _name in _STUBBED:
    sys.modules.pop(_name, None)

import fastapi  # noqa: E402
import open_webui.routers.chats as chats_router  # noqa: E402  真包全链导入

sys.modules.update(_STUBBED)  # 恢复桩现场

_ENGINE_CHAT_ID = 'sess_abc123def456'

#: 6 个被守卫的 handler 及其最小关键字实参(守卫先于一切 I/O,守卫抛 404 即返回)
_GUARDED = [
    (chats_router.compact_chat_by_id, {}),
    (chats_router.update_chat_message_by_id, {'message_id': 'row1', 'form_data': chats_router.MessageForm(content='x')}),
    (chats_router.delete_chat_message_by_id, {'message_id': 'row1'}),
    (chats_router.send_chat_message_event_by_id, {'message_id': 'row1', 'form_data': chats_router.EventForm(type='input', data={})}),
    (chats_router.fork_chat_by_id, {}),
    (chats_router.clone_chat_by_id, {'form_data': None}),
]


def test_engine_chat_message_level_ops_rejected_404_with_detail():
    """sess_* 会话的消息级操作一律早 404,中文说明随 detail 透传(前端可见)。"""
    for handler, kwargs in _GUARDED:
        try:
            asyncio.run(handler(request=None, id=_ENGINE_CHAT_ID, **kwargs))
            raise AssertionError(f'expected 404 from {handler.__name__}')
        except fastapi.HTTPException as e:
            assert e.status_code == 404, handler.__name__
            assert '引擎会话不支持该操作' in e.detail, handler.__name__


def test_guard_passes_non_engine_ids_through():
    """非 sess_ 存量 id 不拦(原路径零改——真 404/401 由下游既有逻辑裁决)。"""
    assert chats_router._reject_engine_chat_operation('legacy-local-id') is None
    assert chats_router._reject_engine_chat_operation('sess') is None  # 'sess' 非 'sess_' 前缀,不误伤
