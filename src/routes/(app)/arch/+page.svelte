<script lang="ts">
	// banyan /arch:架构页——全系统唯一的架构参考(代码/存储/交互/模型全景)。
	// 一切内容内嵌,不依赖外部 md;数据源 /api/status + /api/packs(登录即可见)。
	import { getContext, onMount } from 'svelte';
	import type i18nType from '$lib/i18n';

	import BanyanEngineStatus from '$lib/components/admin/BanyanEngineStatus.svelte';
	import PiSessions from '$lib/components/banyan/PiSessions.svelte';
	import PackListCard from '$lib/components/banyan/PackListCard.svelte';
	import { getBanyanStatus, type BanyanEngineStatus as BanyanEngineStatusData } from '$lib/apis/banyan';

	const i18n: typeof i18nType = getContext('i18n');

	let loaded = false;
	let home = '';
	let agents: BanyanEngineStatusData['agents'] = [];

	onMount(async () => {
		try {
			const status = await getBanyanStatus();
			home = status.engine.home ?? '';
			agents = status.agents ?? [];
		} catch {
			home = '';
		}
		loaded = true;
	});

	const memoryLabel = (m?: string) =>
		m === 'persistent' ? '持久(按会话/按方案)' : m === 'fresh' ? '单轮(用完即弃)' : m ?? '-';
	const outputLabel = (o?: string) =>
		o === 'json' ? 'JSON 契约' : o === 'markdown' ? 'Markdown' : o === 'text' ? '自由文本' : o ?? '-';
</script>

<svelte:head>
	<title>架构</title>
</svelte:head>

<div class="flex flex-col h-full min-h-0">
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-3xl mx-auto w-full px-4 py-8">
			<div class="flex items-center gap-2 mb-5">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
				>
					B
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">
					架构
				</h1>
			</div>

			<!-- ═══ 系统总览 ═══ -->
			<div class="mb-6 space-y-4">
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 space-y-2 text-sm"
				>
					<div class="font-medium text-black dark:text-white">系统总览</div>
					<p class="text-gray-500 dark:text-gray-400">
						三个进程:引擎(:8000,编排调度·状态正本·K1 事件流)· sidecar(:8100,pi 执行内核·沙箱工具)· WebUI(:8080,身份认证·界面呈现)。
					</p>
					<p class="text-gray-500 dark:text-gray-400">
						存储根(BANYAN_HOME):
						<span class="break-all font-mono text-xs text-gray-700 dark:text-gray-300">
							{home || '引擎不可达'}
						</span>
					</p>
					<p class="text-gray-400 dark:text-gray-500 text-xs">
						人只出现在两个触点:批准方案、处置信箱。其余全自动。
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs"
					data-testid="banyan-arch-status"
				>
					<div class="text-sm font-medium text-black dark:text-white mb-3">
						引擎状态
					</div>
					<BanyanEngineStatus />
				</div>
			</div>

			<!-- ═══ Agent 全景 ═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-agents"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-1">
					Agent 全景(5 个)
				</div>
				<p class="text-gray-400 dark:text-gray-500 text-xs mb-3">
					每个 Agent 一份 md(frontmatter:名称/描述/档位/工具/记忆/输出),提示词正本在
					<code class="text-[10px]">{home}/agents/</code>。全部跑在 pi 内核 ReAct 上。
				</p>
				{#if loaded && agents.length}
					<div class="overflow-x-auto">
						<table class="w-full text-left">
							<thead>
								<tr class="text-gray-400 dark:text-gray-500">
									<th class="py-1 pr-3 font-medium">名字</th>
									<th class="py-1 pr-3 font-medium">职责</th>
									<th class="py-1 pr-3 font-medium">档位→模型</th>
									<th class="py-1 pr-3 font-medium">工具</th>
									<th class="py-1 pr-3 font-medium">记忆</th>
									<th class="py-1 font-medium">输出</th>
								</tr>
							</thead>
							<tbody>
								{#each agents as agent (agent.name)}
									<tr class="border-t border-gray-100 dark:border-gray-850 align-top">
										<td class="py-1.5 pr-3 text-black dark:text-white whitespace-nowrap">
											{agent.name}
										</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400 max-w-[16rem]">
											{agent.description || '-'}
										</td>
										<td class="py-1.5 pr-3 font-mono text-gray-700 dark:text-gray-300">
											{agent.tier ?? '-'}
										</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">
											{agent.tools?.length ? agent.tools.join(', ') : '-'}
										</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">
											{memoryLabel(agent.memory)}
										</td>
										<td class="py-1.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">
											{outputLabel(agent.output)}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{:else}
					<div class="text-gray-400 dark:text-gray-500">
						{loaded ? '花名册不可得(引擎未返回)' : '加载中…'}
					</div>
				{/if}
			</div>

			<!-- ═══ 角色交互(五场景 choreography)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-interactions"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					角色交互(Agent 之间永不直接对话,一切经三种黑板:K1 事件流 · 工作区文件 · 信箱/审卡)
				</div>
				<div class="space-y-4">
					<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">对话流(秘书主导)</div>
						<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">
人 ─▶ WebUI ─▶ /run(秘书.md + 九件查询工具) ─▶ pi ReAct
  ├─ 工具调用 ─▶ HTTP 回调 ─▶ 引擎 store 直读(信箱/任务/台账/日历)
  ├─ spawn_agent ─▶ /run(探索者/审查者实例) ─▶ 结果回流
  └─ 回复 ──▶ pi_event 镜像 ─▶ SSE ─▶ WebUI 流式 ──▶ chat.db(K1 先行)
						</div>
					</div>
					<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">方案流(任务管理器主导)</div>
						<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">
人/秘书 ─▶ 方案卡 ──▶ 级联准入(规则→单席→镜头→人)──▶ Ticket
  ──▶ 探索(方案卡)──▶ 人批准 ──▶ 攻击门(3×审查者,拦截→信箱→豁免重入)
  ──▶ 波次执行(执行者)──▶ 登记簿断言 ──▶ 完成门四条件
  ──▶ finished + 信箱完成卡 + K2 知识结算
  失败/模糊 ──▶ 任务管理器裁决 ──▶ 信箱卡 ──▶ 人处置 ──▶ 恢复
						</div>
					</div>
				</div>
			</div>

			<!-- ═══ pi 框架架构(完整介绍)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-pi"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-1">
					pi 执行内核(@earendil-works/pi-coding-agent v1.2.0)
				</div>
				<p class="text-gray-400 dark:text-gray-500 mb-3">
					banyan 所有 Agent 的推理与工具执行都跑在 pi 内核上。pi 是一个通用的 coding agent 框架,提供 AgentSession(ReAct 循环)、工具沙箱、会话树、运行中注入、模型路由——banyan 把自己的提示词和工具清单交给 pi,pi 负责让 LLM 真正干活。
				</p>

				<div class="font-medium text-gray-700 dark:text-gray-300 mb-2 mt-3">pi 内核分层</div>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead>
							<tr class="text-gray-400 dark:text-gray-500">
								<th class="py-1 pr-3 font-medium">层</th>
								<th class="py-1 pr-3 font-medium">模块</th>
								<th class="py-1 font-medium">职责</th>
							</tr>
						</thead>
						<tbody>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">会话运行时</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/agent-session.ts</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">AgentSession 类:prompt() 启动 ReAct 循环、abort() 中断、compact() 压缩、cycleModel() 切模型、navigateTree() 分支导航——一个会话的完整生命周期</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">会话管理</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/session-manager.ts</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">多会话注册表:创建/切换/分叉/归档;jsonl 持久化(banyan sidecar 的 sessions/ 目录)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">工具系统</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/extensions/</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">ToolDefinition(type/function/parameters)+ defineTool 注册;内建 read/write/edit/bash/grep/ls;按白名单注入(banyan /run payload.tools)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">模型路由</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/model-registry.ts</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">models.json 物化(provider/model/api_key)→ /run payload.model 直查 → GLM API 调用(OpenAI 兼容流式)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">上下文压缩</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/compaction/</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">estimateTokens → shouldCompact → compact:超长对话自动截断+摘要(尾窗+摘要头),banyan duty 长对话靠此不爆 token</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">分叉与导航</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/agent-session(树导航)</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">navigateTree(编辑重发/分支切换)、fork(从任意节点分出新树);banyan 预留(未启用)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">技能系统</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/skills</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">ParsedSkillBlock:从 md 提取技能块注入 system prompt;banyan 的 K4 技能投影目标</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">扩展系统</td>
								<td class="py-1 pr-3 font-mono text-[10px]">core/extensions/runner</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">ExtensionRunner:自定义工具注册(如 banyan 的 HTTP 回调工具)、before/after 钩子、UI 渲染器</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- ═══ pi × banyan 对接面(引擎怎么调 pi)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-pi-usage"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					banyan 怎么调 pi(HTTP /run 无状态分发)
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead>
							<tr class="text-gray-400 dark:text-gray-500">
								<th class="py-1 pr-3 font-medium">步骤</th>
								<th class="py-1 pr-3 font-medium">谁→谁</th>
								<th class="py-1 font-medium">做什么</th>
							</tr>
						</thead>
						<tbody>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">①</td>
								<td class="py-1 pr-3">引擎 → sidecar</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">POST /run {system_prompt, task_text, model, tools, workspace, task_id, http_tools?, callback_base?, wait?} — 引擎把 Agent md 的提示词与工具清单组装进载荷</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">②</td>
								<td class="py-1 pr-3">sidecar(pi 内核)</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">创建 AgentSession(system_prompt=系统提示, tools=白名单, model=GLM)→ agent.prompt(task_text) 启动 ReAct 循环</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">③</td>
								<td class="py-1 pr-3">pi → GLM</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">Agent 循环内 LLM 调用 GLM API(流式);LLM 请求工具 → pi 执行(如 write_file)→ 结果回注 → LLM 继续 → 最终文本</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">④</td>
								<td class="py-1 pr-3">事件流回传</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">sidecar /sessions/:id/events SSE → 引擎 HttpWorker 逐条镜像 K1(pi_event)+ 水位断档检测(pi_mirror_gap)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">⑤</td>
								<td class="py-1 pr-3">结果回收</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">wait=true → /run 阻塞返回 RunResult{text,usage};wait=false → agent_result(run_id) 轮询 /runs/:run_id 收取;agent_inject 运行中注入消息(steer/followUp)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">⑥</td>
								<td class="py-1 pr-3">工具回调</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">执行者/审查者的 http_tools(kb_glob/kb_read 等)→ pi 循环调用 → POST callback_base/agent-tools/{tool} → 引擎进程内直查 → JSON 回给 pi → LLM 继续</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- ═══ 存储架构 ═══ -->

			<!-- ═══ 存储架构 ═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-storage"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					存储架构(单一事实正本:K1 事件流;单一存储根:<span class="font-mono">{home}</span>)
				</div>
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead>
							<tr class="text-gray-400 dark:text-gray-500">
								<th class="py-1 pr-3 font-medium">对象</th>
								<th class="py-1 pr-3 font-medium">唯一正本</th>
								<th class="py-1 font-medium">生命周期</th>
							</tr>
						</thead>
						<tbody>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">K1 事件流</td>
								<td>events/ jsonl(append+fsync)</td>
								<td>永久(审计可回放)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">会话消息</td>
								<td>chat.db messages(K1 可重建)</td>
								<td>随会话</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">方案/任务</td>
								<td>chat.db orch_*</td>
								<td>终态留史</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">信箱卡</td>
								<td>chat.db msg_items</td>
								<td>已处置留史/notice 7 天过期</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">日历</td>
								<td>chat.db cal_events</td>
								<td>取消=置态</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">自动化</td>
								<td>chat.db aut_items</td>
								<td>删除=物理删</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">断言登记簿</td>
								<td>chat.db orch_regs(红/绿两轨)</td>
								<td>随方案</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">附件</td>
								<td>workspace/.banyan-uploads(K1 file.stored)</td>
								<td>随工作区</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">知识/技能/角色正本</td>
								<td>knowledge 仓(git: cards/records/agents/prompts)</td>
								<td>版本化</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">WebUI 身份/配置</td>
								<td>webui/webui.db(+cache/uploads)</td>
								<td>仅身份与界面偏好(零消息)</td>
							</tr>
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3">sidecar 运行态</td>
								<td>pi-sidecar/(Pi 会话树=执行缓存)</td>
								<td>K1 镜像为正本</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			{#if loaded}
				<!-- RF-37:运行面卡片行(场景包) -->
				<div class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
					<PackListCard />
				</div>
			{/if}

			<!-- F15/D28:sidecar Pi 会话(只读) -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mt-6 text-xs"
				data-testid="banyan-pi-sessions"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					Pi 会话(sidecar,只读)
				</div>
				<PiSessions />
			</div>
		</div>
	</div>
</div>
