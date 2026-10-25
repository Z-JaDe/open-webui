"""banyan 引擎桥·模型判定与附件携带(RF-12;D18/D19/D20 的中间件半边)。

完整方案.md §12.5 裁决在本仓的落点:
- **D18 附件归引擎**:附件唯一正本=引擎工作区。fork 主上传端点(routers/files.py
  POST /api/v1/files/)把对话附件**同步转发**引擎 ``POST /api/files``(失败降级:
  本地缓存行照常+警告日志,绝不阻断上传);返回的 ``engine_path`` 记入 file.meta。
  对话轮在 middleware.process_chat_payload 把在案附件以文本行追加进最后一条 user
  消息(引擎 ``v1_api._last_user_text`` 只读文本),同时**剥离多模态 base64 段**
  (image 段不进 payload,防 token/带宽爆炸——引擎本就只取 text 段)。
- **D19 知识单一链**:fork chroma RAG 对 banyan 模型整体短路(fork 库文档绕过
  入审/攻击门/K2 直达 prompt 是纪律后门);短路点=middleware 的
  chat_completion_files_handler 门控,本模块只供判定。
- **D20 记忆归引擎**:banyan 模型强制 ``features.memory=False``(第二人格记忆层
  封禁;middleware 在 features pop 后置 False)。

banyan 模型判定:body model id 以 ``banyan-`` 前缀,或 model 条目
``info.meta.kind == "tier"``(引擎 /v1/models 档位条目的标记)。

结构红线:全部判定与 payload 变换内聚本模块,middleware 只留三处一行接线;
模块级 import 仅标准库(与 banyan_bridge.py 同款 importlib 直载测试模式),
httpx/open_webui 依赖在函数内懒加载。前端 src/ 零改。
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

#: 引擎模型 id 前缀(v3:model=工作空间,banyan-<空间id>;旧档位条目已退役)
BANYAN_MODEL_PREFIX = 'banyan-'
#: 附件行块头(追加在最后一条 user 文本尾部;引擎 _last_user_text 整串入会话行)
ATTACHMENT_NOTE_HEADER = '\n\n[附件已存引擎工作区]'
#: 引擎附件大小帽(与引擎 api UPLOAD_MAX_BYTES=20MB 同口径)。files.py 上传桥
#: 以此预检 413 明示(C1-5):超帽转发引擎必 413,静默降级=造一个引擎工人永远
#: 读不到的附件假象,不如上传时明示拒绝。
ENGINE_ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024
#: 上传转发超时(秒)——20MB 本机回环上限;失败即降级,不重试不阻断
UPLOAD_FORWARD_TIMEOUT = 30.0


# ── banyan 模型判定(D18/D19/D20 三处共用)──


def is_banyan_model(model: dict | None, body_model: str = '') -> bool:
    """判定本次补全是否指向 banyan 引擎档位。

    判据(任一命中即真):
    - body model id(form_data['model'])或 model 条目 id 以 ``banyan-`` 前缀;
    - model 条目 ``info.meta.kind == "tier"``(引擎 /v1/models 的档位标记,
      经 fork models 注册表原样透传)。
    """
    mid = str(body_model or '').strip()
    if not mid and isinstance(model, dict):
        mid = str(model.get('id') or '').strip()
    if mid.startswith(BANYAN_MODEL_PREFIX):
        return True
    try:
        meta = ((model or {}).get('info') or {}).get('meta') or {}
    except Exception:
        return False
    return isinstance(meta, dict) and meta.get('kind') in ('tier', 'space')


# ── D18:多模态剥离 + 附件行携带 ──


def strip_multimodal_segments(messages: list) -> int:
    """就地剥掉 user 消息 content 列表里的非文本段(image_url 等含 base64 段)。

    引擎 ``_last_user_text`` 只取 text 段——图片段进了 payload 也到不了模型,
    纯属带宽/泄露面;这里让 image 段不进 payload。单文本段折回纯字符串,
    与引擎返回形态一致。返回剥离的段数。"""
    stripped = 0
    for m in messages or []:
        if not isinstance(m, dict) or m.get('role') != 'user':
            continue
        content = m.get('content')
        if not isinstance(content, list):
            continue
        texts = [p.get('text', '') for p in content
                 if isinstance(p, dict) and p.get('type') == 'text']
        stripped += len(content) - len(texts)
        if len(texts) == 1:
            m['content'] = texts[0]
        elif texts:
            m['content'] = [{'type': 'text', 'text': t} for t in texts]
        else:
            m['content'] = ''
    return stripped


def engine_path_of_file(item: dict) -> str | None:
    """附件条目的 engine_path 取值链(files.py 上传桥写库 meta;前端 fileItem
    把整条 file 记录挂在 item.file,故三级链:item → item.meta → item.file.meta)。
    """
    if not isinstance(item, dict):
        return None
    for source in (item, item.get('meta'), (item.get('file') or {}).get('meta')
                   if isinstance(item.get('file'), dict) else None):
        if isinstance(source, dict):
            v = source.get('engine_path')
            if isinstance(v, str) and v:
                return v
    return None


def engine_attachment_lines(files) -> str:
    """files 元数据 → 附件行块;无任何附件行返回 ''(不发空头)。

    形态(D18 契约,每文件一行,引擎工人按 workspace 相对路径直读):
    \\n\\n[附件已存引擎工作区]\\n- <name> @ .banyan-uploads/<path>

    C1-5 降级可见:file 型条目有 name 但 engine_path 缺失(上传时引擎不可达的
    降级件)生成 ``[附件未同步引擎: <name>(上传时引擎不可达)]`` 行——模型与人
    都可见,不再静默丢附件;collection 等非上传件仍跳过(知识库不是引擎工作
    区文件,不误报)。
    """
    lines: list[str] = []
    for f in files or []:
        if not isinstance(f, dict):
            continue
        path = engine_path_of_file(f)
        if not path:
            name = str(f.get('name') or f.get('filename') or '')
            if name and f.get('type') != 'collection':
                lines.append(f'- [附件未同步引擎: {name}(上传时引擎不可达)]')
            continue
        name = str(f.get('name') or f.get('filename') or path.rsplit('/', 1)[-1])
        lines.append(f'- {name} @ {path}')
    if not lines:
        return ''
    return ATTACHMENT_NOTE_HEADER + '\n' + '\n'.join(lines)


def _last_user_message(messages: list) -> dict | None:
    for m in reversed(messages or []):
        if isinstance(m, dict) and m.get('role') == 'user':
            return m
    return None


def _message_text(m: dict) -> str:
    c = m.get('content')
    if isinstance(c, list):
        return ''.join(p.get('text', '') for p in c
                       if isinstance(p, dict) and p.get('type') == 'text')
    return str(c or '')


def apply_banyan_engine_payload(form_data: dict, metadata: dict) -> dict:
    """会话轮引擎携带单点(D18,middleware 唯一接线):
    ① 剥 user 消息多模态段;② 在案附件(engine_path)以文本行追加到最后一条
    user 消息文本尾部。返回 {stripped, attached} 供日志。绝不抛。"""
    out = {'stripped': 0, 'attached': 0}
    try:
        messages = form_data.get('messages') or []
        out['stripped'] = strip_multimodal_segments(messages)
        block = engine_attachment_lines((metadata or {}).get('files'))
        if block:
            msg = _last_user_message(messages)
            if msg is not None:
                msg['content'] = _message_text(msg) + block
                out['attached'] = block.count('\n- ')
    except Exception as e:                       # 携带失败不炸对话,降级裸文本
        log.warning('banyan_attach: 附件携带失败(降级): %s', e)
    return out


# ── D18:上传转发引擎(fork files.py 主上传端点专用)──


async def forward_attachment_to_engine(filename: str, contents: bytes,
                                       content_type: str | None = None) -> str | None:
    """multipart 转发引擎 ``POST /api/files``,返回 engine_path(workspace 相对)。

    失败(引擎不可达/413 超帽/鉴权/任何异常)→ None:调用方保持原行为(本地
    缓存行照常落库)+ 警告日志,不阻断上传——附件桥是尽力而为的登记,不是闸门。
    """
    try:
        import httpx

        from open_webui.utils.banyan_conv import _engine_headers, engine_base_url
        async with httpx.AsyncClient(timeout=httpx.Timeout(UPLOAD_FORWARD_TIMEOUT)) as client:
            r = await client.post(
                f'{engine_base_url()}/api/files',
                headers=_engine_headers(),
                files={'file': (filename or 'file', contents,
                                content_type or 'application/octet-stream')},
            )
        if r.status_code != 200:
            log.warning('banyan_attach: 引擎登记附件失败(%s %s)——降级本地缓存',
                        r.status_code, r.text[:200])
            return None
        path = (r.json() or {}).get('path')
        return str(path) if path else None
    except Exception as e:
        log.warning('banyan_attach: 引擎登记附件异常: %s——降级本地缓存', e)
        return None
