# FORKING.md — banyan-webui fork 维护手册

本仓库是 Open WebUI 的 banyan 定制 fork（基线 **0.12.1**，分支 `banyan`）。
上游：`open-webui/open-webui`；本 fork：`Z-JaDe/open-webui`。

定制原则：**加法优先**。所有 banyan 能力收敛到 **三钩点 + 独立新文件目录**
（`src/lib/components/banyan/`、`src/routes/(app)/(banyan)/`、`src/lib/apis/banyan/`、
`backend/open_webui/routers/banyan.py`），对上游文件的侵入改动只允许出现在下述
钩点清单内。这样上游季度合并时冲突面最小、可逐条核对。

---

## 1. 三钩点清单（对上游文件的唯一合法侵入点）

### 钩点① — `src/lib/components/chat/Chat.svelte`（渲染协议入口）
- 流式事件分发段（`if (type === 'status')` 链前）新增 `type === 'banyan'` 分支：
  `message.banyanEvents = [...(message.banyanEvents ?? []), unwrapBanyanEvent(data)]`
- `loadChat()` 中 sanitize 之后：历史载入时从持久字段恢复
  `message.banyanEvents`（兼容旧形状 `message.banyan.events`）。
- 新增 import：`unwrapBanyanEvent`（来自 `$lib/components/banyan/types`）。

### 钩点② — `src/lib/components/chat/Messages/ResponseMessage.svelte`（渲染出口）
- 消息内容块顶端（正文上方）挂载 `BanyanEvents.svelte`：
  `{#if message?.banyanEvents?.length}<BanyanEvents events={message.banyanEvents} {chatId} />{/if}`
- 新增 import：`BanyanEvents from '$lib/components/banyan/BanyanEvents.svelte'`。

### 钩点③ — `src/lib/components/layout/Sidebar.svelte`（任务分区入口）
- `banyanTaskEntries` 常量（registry/cards/audit/waves/tree/arch 六入口；
  v3 W2/W3（V-10）追加 **inbox/cal 两行**）
- v3 W2 信箱徽标（登记在钩点③内）：`getBanyanInbox` import + 60s 轮询
  `unread.decision` 的 onMount/清 timer 块 + inbox 条目徽标渲染
  （任何异常静默置 0，引擎不在是常态）
- `activeBanyanEntryPrefix` 高亮
- `SidebarSection id="sidebar-banyan"` 区块（Channels 区块之后、Folders 之前）
- `showBanyanTasks` 状态。

### hook④ — `src/lib/components/chat/SettingsModal.svelte`（v3 W4，V-10 两处）
- 组件分支 `admin:connections` → `<AdminBanyanEngineStatus />`（只读状态卡；
  tab 行保留不删；`AdminConnections` import 留置未用，回滚即还原）
- `adminSettings` 数组中 `admin:connections` 的 `title/titleKey` 改普通键
  `'Engine'`（同 `admin:apps` 'Apps' 的既有写法）、`searchPrefixes` 置空
  （面板内容已换，旧 connections 搜索前缀作废）

其余改动全部在 **新文件** 内：
| 目录/文件 | 内容 |
|---|---|
| `src/lib/components/banyan/` | types（schema）/ mock（story 数据）/ 五组件 + BanyanEvents 聚合器 + BanyanPageNav（v3 W2/W3 起含 inbox/cal pills） |
| `src/lib/apis/banyan/` | 引擎 API 客户端（统一 `/banyan/api/*`；v3 W2-W4 追加 inbox/calendar/status 九函数） |
| `src/routes/(app)/(banyan)/` | 五路由 + 共享布局 + waves/tree 入口页；v3 W2/W3 追加 `inbox/+page.svelte`（信箱三 tab）与 `cal/+page.svelte`（复用 CalendarView 月视图） |
| `src/lib/components/admin/BanyanEngineStatus.svelte` | v3 W4：引擎聚合状态只读卡（hook④ 的面板本体） |
| `backend/open_webui/routers/banyan.py` | 代理桥（`/banyan/api/*` → 引擎） |
| `backend/open_webui/main.py` | 仅一行 import + 一行 include_router（钩点③的 backend 侧，登记在案） |
| `backend/open_webui/routers/openai.py` | 四处：流式转发包 `banyan_passthrough_wrapper` + 非流式 `strip_banyan_sse_lines`（§2 透传链路）+ conv 头注入 `resolve_conv_header`（§3b）+ 任务轮头注入 `resolve_task_header` → `X-Banyan-Task: 1`（RF-16 C1-3，均在 `generate_chat_completion` 内，登记在案） |
| `backend/open_webui/routers/chats.py` | 两处（§3b quick-win）：`update_chat_by_id` 改名→引擎 title 同步；`delete_chat_by_id` 删除→引擎归档（登记在案） |
| `backend/open_webui/models/chats.py` | 一个方法：`update_chat_meta_by_id`（conv 绑定持久化用，登记在案） |
| `backend/open_webui/utils/banyan_stream.py`、`banyan_conv.py`、`banyan_oauth.py`、`backend/tests/` | 透传/conv 绑定/GitHub OAuth 内置凭据（§3d）实现与单测 |
| `backend/open_webui/config.py` | §3d 一处：`GITHUB_*` 四变量默认值改读 `utils/banyan_oauth`（env 仍可覆盖；登记在案） |
| `src/lib/components/admin/Settings/Authentication.svelte` | §3d：OAuth 配置表单区块整体移除，换说明文字；signup 开关保留（登记在案） |
| `src/lib/i18n/locales/zh-CN/translation.json` | §3d：三条 GitHub OAuth 说明 i18n 键（登记在案） |

---

## 2. 渲染协议（事件 schema）

引擎在 OpenAI 兼容 SSE 正文之外，发送私有事件行：

```
data:{"banyan":{"type":"plan","plan_id":"...","status":"pending", ...}}
```

fork 后端把它作为 socket 事件 `{type:'banyan', data:<BanyanEvent>}` 转发到前端
（钩点①消费）。权威 TypeScript 定义：`src/lib/components/banyan/types.ts`。

### 透传链路（backend，WE-3B）

`backend/open_webui/routers/openai.py` 的 `/chat/completions` 代理流式段把私有行
接入前端事件通道，与 `status` 同机制：

1. **流式**：`generate_chat_completion` 的 SSE 返回包裹
   `banyan_passthrough_wrapper(stream_wrapper(r))`（实现：
   `backend/open_webui/utils/banyan_stream.py`，纯标准库）。上游行
   `data:{"banyan":{...}}` 被逐行即时改写为 Open WebUI 既有事件线格式
   `data:{"event":{"type":"banyan","data":{...}}}`——middleware 流处理循环
   （`utils/middleware.py`）对含 `event` 键的 chunk 走 `event_emitter` 推送，
   前端 socket 即收到 `{type:'banyan', data:<BanyanEvent>}`。逐行即时、
   不缓冲整段；坏 JSON 行、非 banyan 行、`[DONE]` 一律逐字节原样透传，
   绝不进错误路径。
2. **非流式**：不转发编排事件。若正文被 banyan 行污染导致 JSON 解析回退文本，
   用 `strip_banyan_sse_lines` 剥离私有行后按 JSON 返回（忽略而非报错）。
3. 上游直连模式（`request.state.direct`）沿用上游 `event` chunk 的既有语义
   （不经 socket，随 HTTP 流透传给客户端）。

单测：`backend/tests/test_banyan_passthrough.py`
（`cd backend && python3 -m pytest tests/test_banyan_passthrough.py -q`）。

### 事件一览（五组件映射）

| type | 载荷 | 组件 | 归并规则 |
|---|---|---|---|
| `plan` | `{plan_id, title?, status:'pending'\|'approved'\|'rejected'\|'revised', hypothesis?, waves:[{index,title?,depends_on?,tasks:[{task_id,title,deps?}]}], acceptance?, risks?, rollback?, alt_option?, ts?}` | **PlanCard** | 按 `plan_id` upsert |
| `wave_update` | `{plan_id, wave, tasks:[{task_id, title?, status:'pending'\|'running'\|'done'\|'failed'\|'skipped'\|'blocked', deps?, detail?}], ts?}` | **WaveBoard** | 同 `plan_id` 聚合；`task_id` upsert 不刷屏；失败沿 `deps` 传导标红（blocked，渲染层推断） |
| `tool` | `{call_id, name, args_summary?, status:'running'\|'ok'\|'error', output_summary?, started_at?, ended_at?, ts?}` | **ToolTimeline** | 按 `call_id` upsert；默认折叠只显最近 3 行 |
| `subagent` | `{subagent_id, role?, title?, latest_action?, status:'running'\|'done'\|'failed'\|'stopped', session_id?, started_at?, ended_at?, ts?}` | **SubagentCard** | 按 `subagent_id` upsert；`latest_action` 换词动画 |
| `branch` | `{branches:[{id,label,active}], ts?}` | **TreeSwitcher** | 只保留最新一份，挂消息块顶端 |

组件渲染顺序（正文上方）：TreeSwitcher → PlanCard → WaveBoard → ToolTimeline → SubagentCard。

### 持久化
`message.banyanEvents[]` 随 history JSON 存入 chat.db（`updateChatById` 全量保存
history），历史载入时在钩点①恢复。事件正本仍在引擎 K1，chat 内副本仅为渲染缓存。

### 引擎回流约定
- 方案决议：前端按钮 → `POST /banyan/api/plans/:id/resolve`（body
  `{decision:'approved'|'rejected'|'revised', choice?}`）→ 引擎回流 `plan` 事件
  覆盖状态（前端也做乐观本地回填）。
- 分支切换：`TreeSwitcher` → `POST /banyan/api/chats/:chat_id/tree/switch`
  `{node_id}` → 引擎切换活动分支并投影线性消息流。

---

## 3. 代理桥（backend）

`backend/open_webui/routers/banyan.py`，挂载于 `/banyan/api`。

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `BANYAN_ENGINE_URL` | `http://localhost:8420` | 引擎 base URL（可含子路径，代理按原路径 1:1 追加） |
| `BANYAN_TOKEN` | 空 | 静态引擎 token；设置后覆盖透传的 `Authorization`，未设置则透传前端请求头 |
| `BANYAN_TIMEOUT` | `300` | 上游超时（秒） |

- 鉴权：前端仍需 Open WebUI 登录态（`get_verified_user`），未登录不能借道。
- 流式：`StreamingResponse` 透传，SSE 兼容。
- 排障：`GET /banyan/api/health` 返回代理配置与引擎可达性。

引擎端点约定（前端 `$lib/apis/banyan/index.ts` 为权威调用方）：
`/registry`、`/cards`、`/cards/{id}/resolve`、`/audit`、`/plans/{id}`、
`/plans/{id}/resolve`、`/chats/{id}/tree`、`/work/{id}/cancel`
（RF-Z：子代理停止的真实引擎对端；旧 `/subagents/{id}/stop` 引擎无此路由已弃，
`/chats/{id}/tree/switch`、`/chats/{id}/tree/rerun` 仅消息流 TreeSwitcher/story
面在调用、引擎侧暂无对端）。v3（W2-W4，V-4/V-5/V-8/V-10）追加：
`/inbox?category=&status=&limit=`、`/inbox/{id}/read|archive|resolve`、
`/calendar/events?from=&to=`（epoch 秒）、`POST/PATCH/DELETE /calendar/events[/{id}]`
（DELETE=取消语义）、`/status`（引擎+sidecar 聚合健康；sidecar 不可达返回
`{ok:false}` 不 500）。
路径穿越防护：`/banyan/api/*` 转发前经 `utils/banyan_bridge.safe_bridge_path`
校验，解码后含 `..` 段/反斜杠一律 400 不转发（P2-f-1）。

---

## 3b. conv 绑定（P0 会话映射）+ quick-win 对接

实现：`backend/open_webui/utils/banyan_conv.py`（引擎访问复用 §3 同款 env）。

**机制**：WebUI chat ↔ 引擎 session 1:1。chat 首条消息转发前
（`routers/openai.py generate_chat_completion`，`get_headers_and_cookies` 之后）
判定：目标是引擎（scheme+netloc 与 `BANYAN_ENGINE_URL` 相等）且为真实对话轮
（metadata 无 `task` 键、chat_id 已落库）→ 取 `chat.meta.banyan_conv_id`；
没有则 `POST {BANYAN_ENGINE_URL}/api/projects/{默认项目}/sessions` 建会话并回写
meta，随后注入 `X-Banyan-Conv` 头（引擎 `_resolve_conv` 头优先）。映射不可得时
不注入头（降级为引擎默认实例，即修复前行为），**绝不阻断对话**。

注意边界：
- 后台任务轮（title/tags/follow_up/autocomplete/query 生成，metadata 带
  `task`）**不**注入头——否则任务 prompt 会作为正式 turn 落进绑定会话污染
  K1 正本（修复前默认 conv 的标题即被 title 任务 prompt 污染的实证）。
- 引擎 DB 若重置而 WebUI meta 仍存旧 conv id，引擎按"no such session"404
  该轮（显式失败，不静默串话）；清理 chat.meta.banyan_conv_id 即恢复。

**quick-win 对接**（`routers/chats.py`，均容错不阻断 WebUI 侧操作）：
- 对话改名（`update_chat_by_id`，title 实变时）→ `PATCH /api/sessions/{conv}`
  `{title}`（引擎 `title_source=custom`）。
- 对话删除（`delete_chat_by_id`）→ `PATCH /api/sessions/{conv}` `{archived:true}`
  （引擎保留正本，对齐"分支靠指针不靠删除"）。

单测：`backend/tests/test_banyan_conv.py`。

---

## 3b'. chats 路由 = 引擎适配投影（D16' 零双写，完整方案 §4.5/F7）

**架构终局：对话引擎单写单存，WebUI 消息零存储。** §3b 的 meta 绑定机制随之
**退役**（模块保留，仅为非 `sess_` 存量副本的兜底/改名/归档同步服务，勿增新
依赖）；新对话不再有 WebUI 行、无绑定表、无 meta 回写。

实现：`backend/open_webui/utils/banyan_chat_adapter.py`（引擎 HTTP 沿用 §3b
同款 env 直连；模块顶部只依赖 httpx+标准库，importlib 单测同款）。

**chat id 即引擎会话 id（`sess_*`）**，两个铸造点：

- `POST /api/v1/chats/new`（`routers/chats.py create_new_chat`）：先经引擎
  建会话（标题恒空——引擎 `title_source=first_message` 自动出题），返回
  `sess_*` 投影；引擎不可得回落本地行（绝不阻断）。
- 完成流新建对话（`main.py chat_completion`，`is_new_chat` 分支——前端
  sendPrompt 主路径不走 /new，chat id 由后端铸造）：`mint_engine_chat_id`
  按 openai 连接 origin 判定模型指向引擎（`is_banyan_target`）才建引擎会话;
  非引擎模型/引擎不可得回落 uuid4+本地行。持久化块对 `sess_` chat 整体跳过
  （零落库、不建 WebUI 标题任务——标题由引擎首条消息逻辑生成）。

**端点映射**（`routers/chats.py`；非 `sess_` 存量 chat 一律原路径不动）：

| 端点 | 引擎会话行为 |
|---|---|
| GET `/`、`/list`、`/pinned`、`/archived`(+count) | 引擎会话列表投影并入（`merged_chat_list`，updated_at DESC 合并;引擎不可达降级为仅本地） |
| POST `/new` | 引擎建会话 → `sess_*` chat id,WebUI 零行 |
| GET `/{id}` | 会话 meta+行 → Chat JSON（`history.messages` 映射+平铺;行上滚补页到全量,零信息损失） |
| POST `/{id}`（保存/改名） | **保存 no-op**（完成流不持久化,消息唯一落点=引擎行）;载荷带非空 title → 引擎 PATCH title |
| DELETE `/{id}` | 引擎 `PATCH {archived:true}`（置态留史,不物理删） |
| POST `/{id}/pin`、`/{id}/archive` | 读现值→取反→引擎 PATCH（toggle 语义） |
| GET `/{id}/tags`、POST/DELETE `/{id}/tags`、`/{id}/folder`、`/{id}/unread` | no-op（引擎无 tags/folders/标未读,空表/现值回显） |

**行 → 消息投影**（`rows_to_chat_messages`/`row_to_event`）：

| 引擎行 kind | Open WebUI 形状 |
|---|---|
| userInput | `{role:'user',content:data.text}`;`confirmed===false` → `pending:true`（echo 待确认） |
| assistantText | `{role:'assistant',content:model:'banyan-duty'}`;`status=streaming`→`done:false`（进行中）;`error/cancelled`→`error` 键 |
| toolCall | `banyanEvents` += `BanyanToolEvent{type:'tool',call_id:row_id,name,args_summary,status:'ok'|'error',output_summary,ended_at,ts}` |
| ticket | `banyanEvents` += `BanyanSubagentEvent{type:'subagent',subagent_id:work_id:ticket_id,title,latest_action,status:done→done/cancelled→stopped/failed→failed/其余running}`（引擎 v1 编排线同款映射,work_id 保 `/work/{id}/cancel` 可达） |
| marker | `banyanEvents` += `{type:'marker',marker,text,ts}`（前端 BanyanEvents switch 无此分支=渲染中性,数据保留） |

事件 ts 为 epoch ms（前端 types.ts 约定）;事件按行序归入同 turn 最近 assistant
消息（其前无 assistant 行时合成空壳承载）。前端零改——流式期走既有 socket
`{type:'banyan'}` 通道,刷新后由本投影从引擎行重建 `message.banyanEvents`。

**头注入**：`resolve_conv_header`（§3b）对 `sess_` chat 直通返回（chat id 本身
即会话 id,零查询）;旧 meta 路径仅为存量副本兜底。

已知边界（单用户部署可接受,如实列明）：引擎会话无 folders/tags/未读位
（相应端点 no-op;`POST /chats/read` 批量已读经 `bulk_mark_read` 同步引擎
sess_ 会话——RF-16 L1-10）;投影 model 名恒 `banyan-duty`（行不带档位）;跨设备
`chat:{id}` socket 房间（typing/共享事件）以本地行为准,引擎会话不参与（事件
发射器对 sess_ 不回写本地行——RF-16 L1-8）;消息级编辑/compact/fork/clone/
share 对 `sess_` 会话 401（引擎线性树,不做 WebUI 侧分支工程——见完整方案 P2
"会话树多分支"悬置）。

单测：`backend/tests/test_banyan_chat_adapter.py`（行投影形状/save no-op 零
WebUI 库写入断言/引擎桩全端点映射/sess_ 头直通;运行
`cd backend && ../venv/bin/python -m pytest tests/test_banyan_chat_adapter.py -q`）。

---

## 3c. 部署（env-only 开关 + 嵌入模型本地化）

**env-only 开关**（只进进程 env，写 DB 无效；源自审计 11b 清单，见
`docs/goal/功能适配审计.md`）：

```bash
ENABLE_SIGNUP=true                 # FU-3 [用户裁决] signup 重开；DB 行存在时以 DB 为准
ENABLE_OLLAMA_API=false
ENABLE_DIRECT_CONNECTIONS=false
ENABLE_TOOL_SERVERS=false        # 连带 terminals 关闭
ENABLE_TOOLS=false
ENABLE_FUNCTIONS=false
ENABLE_CODE_EXECUTION=false
ENABLE_CODE_INTERPRETER=false
ENABLE_ADMIN_ANALYTICS=false
```

其余（DB `config` 表热生效的开关、i18n、任务后台收敛等）按审计 §11a 的 SQL
清单写库即可，无需重启。当前运行实例启动脚本：`/tmp/run-webui.sh`。

**任务面模型（F3/D5）**：管理设置 `task.model.external` 建议填 `banyan-fast`——
标题/标签/补全等后台任务自动轮烧引擎 fast 档，且走引擎无状态通道
（引擎按 `X-Banyan-Task: 1` 识别：不建会话、不写 chat.db 行、不占 duty LRU，
任务轮不再污染人的会话历史）。

**RAG 嵌入本地化**（审计域3）：
- 选型 `BAAI/bge-small-zh-v1.5`（中文优先，512 维）；DB 键
  `rag.embedding_engine=""`（**空串=本地 sentence-transformers**，不是
  "sentence-transformers" 字面量——写错会导致 boot 时
  `Unknown embedding engine` 起不来）、
  `rag.embedding_model="/tmp/webui-data/models/bge-small-zh-v1.5"`。
- 模型文件预下载为**普通目录**（非 HF cache）：hf-mirror 对 python TLS 栈
  （requests/httpx）返回 308 跳回 huggingface.co（不可达），对 curl 正常——
  是镜像站的客户端指纹分流；故用 curl 批量下载到 DATA_DIR（当前源用
  ModelScope `https://modelscope.cn/api/v1/models/BAAI/bge-small-zh-v1.5/repo?FilePath=<f>`，
  hf-mirror `resolve/main` 亦可但常 429 限流）。文件清单：
  `config.json modules.json sentence_bert_config.json config_sentence_transformers.json
  special_tokens_map.json tokenizer_config.json vocab.txt tokenizer.json
  1_Pooling/config.json model.safetensors`。
- venv 兼容性：torch 按 NumPy 1.x 编译，需 `numpy<2` + `scipy<1.14`（2.x 会
  `Numpy is not available` / `np.long` 报错）。


---

## 3d. GitHub OAuth 内置化（FU-3，用户裁决）

**裁决**：GitHub OAuth 需要，但凭据用户自持申请、**不作为运行时配置存在**——
不进设置页、不靠 env 手配；signup 重开。

**实现**（对上游的侵入仅两处，登记进 §1 表）：
- `backend/open_webui/utils/banyan_oauth.py`（新文件）：内置凭据常量
  `BANYAN_GITHUB_CLIENT_ID / _CLIENT_SECRET / _REDIRECT_URI / _SCOPE`，
  初值留空占位。**这是唯一填写处**。该模块刻意零 import（config.py 会引它，
  引依赖即循环导入）。
- `backend/open_webui/config.py`：`GITHUB_*` 四变量默认值从 `banyan_oauth`
  读（env 仍可覆盖）。其余 provider（google/microsoft/oidc）保持 env 原样、
  默认不启用。
- `src/lib/components/admin/Settings/Authentication.svelte`：OAuth 配置表单
  区块整体移除，替换为说明文字（zh-CN 三条 i18n 键，加在
  `zh-CN/translation.json`）；signup 开关保留。

**用户申请步骤**（GitHub OAuth App）：
1. GitHub → Settings → Developer settings → OAuth Apps → New OAuth App；
2. Homepage URL：`https://<部署域名>/`；Authorization callback URL：
   `https://<部署域名>/oauth/github/login/callback`
   （后端路由 `GET /oauth/{provider}/login/callback`；`BANYAN_GITHUB_REDIRECT_URI`
   留空时按请求自动推导该地址，二者一致即可。反代/内外网域名不一致才需显式
   填 REDIRECT_URI，且必须与 GitHub 登记值完全一致）；
3. 创建后复制 Client ID，"Generate a new client secret" 复制 Secret（只显示
   一次），填入 `banyan_oauth.py` 两个常量，重启后端。登录页自动出现 GitHub
   按钮（`$config.oauth.providers` 驱动，前端零改动）。

**行为**：凭据未填 → provider 不装配、登录页无 GitHub 按钮、启动无报错（已验证）。
填好后启动会出现上游的 logout 警告（`OAuth providers configured (GitHub) but
OPENID_PROVIDER_URL not set`）——GitHub 无 OIDC end-session 端点，本地会话登出
不受影响，可忽略。

**逃生门**（测试用）：env `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` /
`GITHUB_CLIENT_REDIRECT_URI` / `GITHUB_CLIENT_SCOPE` 优先于内置常量（已验证
env 覆盖生效）。

**signup 重开**：DB `config` 表 `ui.enable_signup=true`（运行库已写入；注意
上游行为——首个注册用户成为 admin 时会自动把该键写回 false，此后不再触发）；
启动脚本 env `ENABLE_SIGNUP=true`（新库种子/缺省回退，DB 行存在时以 DB 为准）。

---

## 3e. 存储单根（D26，完整方案.md §12.5/F10）

**纪律**：一个 `BANYAN_HOME` 收纳三进程全部状态，杜绝"sidecar 落 `~/.banyan`
死目录、WebUI 落 `backend/data`"的活分裂。fork 侧的义务只有一条——**必须由
启动脚本显式给 `DATA_DIR`**（fork 后端从 `open_webui.env.DATA_DIR` 定位
`webui.db/vector_db/uploads/cache`，缺省回落到仓库内 `backend/data`，属分裂根）。

**env 约定**（`scripts/start-all.sh` 已统一注入，手工起进程时须自带）：

| 进程 | env | 值 | 缺省回落(=分裂根,禁止) |
|---|---|---|---|
| 引擎 | `BANYAN_HOME` | `$HOME_DIR` | `~/.banyan` |
| sidecar | `BANYAN_SIDECAR_HOME` | `$HOME_DIR/pi-sidecar`（stateDir；agentDir/sessionsDir 在其下） | `~/.banyan/pi-sidecar` |
| 引擎(K4 投影) | `BANYAN_SIDECAR_HOME` | 同值——引擎 `_pi_skills_dir` 的 env 优先级高于 `~/.banyan` 回落,技能投影落进 sidecar 真实 stateDir | `~/.banyan/pi-sidecar` |
| WebUI | `DATA_DIR` | `$HOME_DIR/webui`（start-all 已先 `mkdir -p`） | `<fork>/backend/data` |

**存量迁移**（停机一次性，幂等，支持 `--dry-run`）：

```bash
scripts/stop-all.sh                 # 三进程(engine:8000/sidecar:8100/webui:8080)必须先停
scripts/migrate-to-home.sh /tmp/banyan-final --dry-run   # 先看清单
scripts/migrate-to-home.sh /tmp/banyan-final             # 实际迁移
```

脚本动作：①校验三进程已停；②`~/.banyan/pi-sidecar/{agent,sessions}` →
`$HOME_DIR/pi-sidecar/`；③`<webui>/backend/data/{webui.db*,vector_db,uploads,cache}`
→ `$HOME_DIR/webui/`；④旧 `~/.banyan` 其余（config.toml/events/state/knowledge/
workspace）归档到 `~/.banyan-archive-<date>/`——**`remote.json` 保留原位**
（桌面壳活读）；归档后打印 API key 轮换提示（旧家配置已双份落盘明文密钥）。
已迁过的条目自动跳过，重复执行无副作用。

**弃用开关同步登记（D25/D21 过渡封堵，仅改缺省值不删代码）**：
`backend/open_webui/config.py` 中 `ENABLE_CALENDAR`、`ENABLE_AUTOMATIONS`
的 env 缺省已改 `False`（连带 `DEFAULT_CONFIG` 的 `calendar.enable` /
`automations.enable` 种子值；统一调度器 `scheduler_worker_loop` 据此停摆
本地日历提醒扫描与 automations 执行——正本归引擎 cal_events 与引擎定时任务）。
env 显式 `ENABLE_CALENDAR=true` 仍可临时复活（排障用，口径为弃用）。
注意：`seed_defaults` 只对 DB 中**不存在**的键下种，存量库已写 true 的行需在
管理设置或 SQL 置 false 才热生效。

---

## 4. mock / story 开关

无法真连引擎时：
- 组件级：`<PlanCard mock />` 等五组件均支持 `mock` prop，渲染
  `src/lib/components/banyan/mock.ts` 内置样例。
- 路由级：各 (banyan) 路由 URL 加 `?mock=1`（v3 起含 inbox/cal），走内置样例数据，
  不请求引擎；引擎不可达时页面顶部展示明确错误条（不静默伪造）。

---

## 5. 上游合并流程（季度节奏）

```bash
git remote add upstream https://github.com/open-webui/open-webui.git   # 首次
git fetch upstream --tags

# 1) 从上游主分支开合并分支
git checkout -b upstream-merge-YYYYQX banyan
git merge --no-ff upstream/main
#    预期冲突面 = §1 钩点清单中的 11 个文件（Chat.svelte / ResponseMessage.svelte /
#    Sidebar.svelte / main.py / openai.py / chats.py / models/chats.py /
#    config.py / Authentication.svelte / zh-CN translation.json /
#    utils/banyan_*.py）。逐一手工核对：
#    - Chat.svelte：确认 banyan 分支仍在事件分发链上、loadChat 恢复逻辑仍在；
#    - ResponseMessage.svelte：确认 BanyanEvents 挂载点仍在正文上方；
#    - Sidebar.svelte：确认任务分区仍在；
#    - main.py：确认 banyan router 的 import 与 include_router 仍在；
#    - openai.py：确认 banyan_passthrough_wrapper / strip_banyan_sse_lines /
#      resolve_conv_header（X-Banyan-Conv 注入）三处仍在；
#    - chats.py：确认 update_chat_by_id 的改名同步与 delete_chat_by_id 的
#      归档钩子（conv_id_for_chat / patch_engine_session）仍在；
#    - models/chats.py：确认 update_chat_meta_by_id 仍在。
#    - config.py：确认 GITHUB_* 四变量默认值仍读 banyan_oauth（§3d）；
#    - Authentication.svelte：确认 OAuth 表单仍被说明文字取代、signup 开关仍在；
#    - zh-CN translation.json：确认三条 GitHub OAuth 说明键仍在。

# 2) 回归验证
npm ci && npm run build          # 前端全绿
python3 -m compileall backend     # 后端语法
#   手工冒烟：?mock=1 打开 /registry /cards /audit /waves/plan-mock-001 /tree/chat-mock-77

# 3) 合回
git checkout banyan && git merge --no-ff upstream-merge-YYYYQX
git branch -d upstream-merge-YYYYQX
git push origin banyan
```

合并检查单：
- [ ] 三钩点全部存活（grep `banyanEvents` / `BanyanEvents` / `sidebar-banyan` / `banyan.router`）
- [ ] openai.py 透传两处 + conv 注入存活（grep `banyan_passthrough_wrapper` /
      `strip_banyan_sse_lines` / `resolve_conv_header`），chats.py 两钩子 +
      `update_chat_meta_by_id` 存活（grep `conv_id_for_chat`），
      `cd backend && python3 -m pytest tests/test_banyan_passthrough.py tests/test_banyan_conv.py -q` 全绿
- [ ] `src/lib/components/banyan/`、`src/routes/(app)/(banyan)/`、`src/lib/apis/banyan/` 未被上游删除或重命名冲突
- [ ] `npm run build` 全绿
- [ ] mock story 冒烟通过（五路由 + 组件）
- [ ] 上游若有流式协议/持久化结构变更，重读钩点①相邻代码并补 README 注记

## 6. 回滚

fork 定制全部可剥离：revert 三钩点的 7 个文件改动（含 openai.py 三处、chats.py
两处、models/chats.py 一处）+ 删除新目录/文件（`src/lib/components/banyan/`、
`src/routes/(app)/(banyan)/`、`src/lib/apis/banyan/`、`banyan.py`、
`banyan_stream.py`、`banyan_conv.py`、`backend/tests/`）即可回到原生 Open WebUI；
chat.db 中残留的 `banyanEvents` / `meta.banyan_conv_id` 字段会被原生代码忽略
（后者仅引擎侧会话归档语义随之失效）。
