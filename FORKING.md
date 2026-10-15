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

### 钩点③ — `src/lib/components/layout/Sidebar.svelte`（任务分区五入口）
- `banyanTaskEntries` 常量（registry/cards/audit/waves/tree 五入口）
- `activeBanyanEntryPrefix` 高亮
- `SidebarSection id="sidebar-banyan"` 区块（Channels 区块之后、Folders 之前）
- `showBanyanTasks` 状态。

其余改动全部在 **新文件** 内：
| 目录/文件 | 内容 |
|---|---|
| `src/lib/components/banyan/` | types（schema）/ mock（story 数据）/ 五组件 + BanyanEvents 聚合器 + BanyanPageNav |
| `src/lib/apis/banyan/` | 引擎 API 客户端（统一 `/banyan/api/*`） |
| `src/routes/(app)/(banyan)/` | 五路由 + 共享布局 + waves/tree 入口页 |
| `backend/open_webui/routers/banyan.py` | 代理桥（`/banyan/api/*` → 引擎） |
| `backend/open_webui/main.py` | 仅一行 import + 一行 include_router（钩点③的 backend 侧，登记在案） |
| `backend/open_webui/routers/openai.py` | 仅两处：流式转发包 `banyan_passthrough_wrapper` + 非流式 `strip_banyan_sse_lines`（§2 透传链路，登记在案） |
| `backend/open_webui/utils/banyan_stream.py`、`backend/tests/` | 透传实现（纯标准库）与单测 |

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
面在调用、引擎侧暂无对端）。
路径穿越防护：`/banyan/api/*` 转发前经 `utils/banyan_bridge.safe_bridge_path`
校验，解码后含 `..` 段/反斜杠一律 400 不转发（P2-f-1）。

---

## 4. mock / story 开关

无法真连引擎时：
- 组件级：`<PlanCard mock />` 等五组件均支持 `mock` prop，渲染
  `src/lib/components/banyan/mock.ts` 内置样例。
- 路由级：五路由 URL 加 `?mock=1`，走内置样例数据，不请求引擎；
  引擎不可达时页面顶部展示明确错误条（不静默伪造）。

---

## 5. 上游合并流程（季度节奏）

```bash
git remote add upstream https://github.com/open-webui/open-webui.git   # 首次
git fetch upstream --tags

# 1) 从上游主分支开合并分支
git checkout -b upstream-merge-YYYYQX banyan
git merge --no-ff upstream/main
#    预期冲突面 = §1 钩点清单中的 5 个文件（Chat.svelte / ResponseMessage.svelte /
#    Sidebar.svelte / main.py / openai.py）。逐一手工核对：
#    - Chat.svelte：确认 banyan 分支仍在事件分发链上、loadChat 恢复逻辑仍在；
#    - ResponseMessage.svelte：确认 BanyanEvents 挂载点仍在正文上方；
#    - Sidebar.svelte：确认任务分区仍在；
#    - main.py：确认 banyan router 的 import 与 include_router 仍在；
#    - openai.py：确认 banyan_passthrough_wrapper / strip_banyan_sse_lines 两处仍在。

# 2) 回归验证
npm ci && npm run build          # 前端全绿
python -m compileall backend     # 后端语法
#   手工冒烟：?mock=1 打开 /registry /cards /audit /waves/plan-mock-001 /tree/chat-mock-77

# 3) 合回
git checkout banyan && git merge --no-ff upstream-merge-YYYYQX
git branch -d upstream-merge-YYYYQX
git push origin banyan
```

合并检查单：
- [ ] 三钩点全部存活（grep `banyanEvents` / `BanyanEvents` / `sidebar-banyan` / `banyan.router`）
- [ ] openai.py 透传两处存活（grep `banyan_passthrough_wrapper` / `strip_banyan_sse_lines`），
      `cd backend && python3 -m pytest tests/test_banyan_passthrough.py -q` 全绿
- [ ] `src/lib/components/banyan/`、`src/routes/(app)/(banyan)/`、`src/lib/apis/banyan/` 未被上游删除或重命名冲突
- [ ] `npm run build` 全绿
- [ ] mock story 冒烟通过（五路由 + 组件）
- [ ] 上游若有流式协议/持久化结构变更，重读钩点①相邻代码并补 README 注记

## 6. 回滚

fork 定制全部可剥离：revert 三钩点的 5 个文件改动（含 openai.py 两处）+ 删除
新目录/文件（`src/lib/components/banyan/`、`src/routes/(app)/(banyan)/`、
`src/lib/apis/banyan/`、`banyan.py`、`banyan_stream.py`、`backend/tests/`）即可
回到原生 Open WebUI；chat.db 中残留的 `banyanEvents` 字段会被原生代码忽略。
