<script lang="ts">
	// banyan /arch:架构页——全系统唯一的架构参考(代码/存储/交互/模型全景)。
	// 一切内容内嵌,不依赖外部 md;数据源 /api/status + /api/packs(登录即可见)。
	import { getContext, onMount } from 'svelte';
	import type i18nType from '$lib/i18n';
	import { showSidebar } from '$lib/stores';

	import BanyanEngineStatus from '$lib/components/admin/BanyanEngineStatus.svelte';
	import PiSessions from '$lib/components/banyan/PiSessions.svelte';
	import PackListCard from '$lib/components/banyan/PackListCard.svelte';
	import { getBanyanStatus, type BanyanEngineStatus as BanyanEngineStatusData } from '$lib/apis/banyan';

	const i18n: typeof i18nType = getContext('i18n');

	let loaded = false;
	let home = '';
	let agents: BanyanEngineStatusData['agents'] = [];

	// /arch/pi 嵌入:子页上报内容高度,iframe 自适应(全局 html 锁了 overflow,不能靠内页滚动兜底观感)
	let piHeight = 1200;
	const onPiMessage = (e: MessageEvent) => {
		const d = e.data;
		if (d && d.type === 'banyan-arch-pi-height' && typeof d.height === 'number') {
			piHeight = Math.min(Math.max(Math.round(d.height), 400), 4000);
		}
	};

	onMount(async () => {
		try {
			const status = await getBanyanStatus();
			home = status.engine.home ?? '';
			agents = status.agents ?? [];
		} catch {
			home = '';
		}
		loaded = true;
		// 高度自适应兜底:同源直读子页内容高度——子页 postMessage 可能早于本页监听器挂载而丢失
		let tries = 0;
		const fit = setInterval(() => {
			tries++;
			const f = document.querySelector('iframe[src="/arch/pi"]');
			if (!f) {
				if (tries > 60) clearInterval(fit);
				return;
			}
			try {
				const inner = f.contentDocument && f.contentDocument.querySelector('.max-w-full');
				if (inner) {
					const h = Math.ceil(inner.getBoundingClientRect().height) + 2;
					if (h > 400) piHeight = Math.min(h, 4000);
					clearInterval(fit);
				} else if (tries > 60) {
					clearInterval(fit);
				}
			} catch {
				if (tries > 60) clearInterval(fit);
			}
		}, 500);
		return () => clearInterval(fit);
	});

	const memoryLabel = (m?: string) =>
		m === 'persistent' ? '持久(按会话/按方案)' : m === 'fresh' ? '单轮(用完即弃)' : m ?? '-';
	const outputLabel = (o?: string) =>
		o === 'json' ? 'JSON 契约' : o === 'markdown' ? 'Markdown' : o === 'text' ? '自由文本' : o ?? '-';
</script>

<svelte:head>
	<title>架构</title>
</svelte:head>

<svelte:window on:message={onPiMessage} />

<div
	class="flex flex-col h-full min-h-0 w-full max-w-full transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-full mx-auto w-full px-4 py-8">
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
						四个进程:引擎(:8000,触发器·K1 事实正本·store 工具回调)· pi-sidecar(:8100,pi 执行内核·沙箱工具)· <b>pi-goal(:8101,goal 内核·durable 执行正本,v3 新)</b>· WebUI(:8080,身份认证·界面呈现)。
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
					Agent 全景({agents.length} 预设)
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
					角色交互(Agent 之间永不直接对话,一切经三种黑板:K1 事件流 · 工作区文件 · 人卡/信箱)
				</div>
				<div class="space-y-4">
					<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">对话流(秘书主导)</div>
						<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">
人 ─▶ WebUI ─▶ /conv submit(秘书.md durable 会话+回调工具∪subagent)
  ├─ 工具调用 ─▶ HTTP 回调 ─▶ 引擎 store 直读(信箱/任务/台账/日历)
  ├─ subagent(role=探索者/审查者) ─▶ 常驻子代理 ─▶ 答案自动回流
  └─ 回复 ──▶ pi_event 镜像 ─▶ SSE ─▶ WebUI 流式 ──▶ chat.db(K1 先行)
						</div>
					</div>
<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">机制流(goal 内核主导——一切机制的统一形态)</div>
						<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">触发(cron/git watch/K1 订阅/手动)──▶ goal(requestId 幂等)
  ①seed(管理者会话=引擎 md 逐字)──▶ ②plan ──▶ ③execute(轮次+预算+红测前置;
  管理者自行 spawn 常驻子代理,答案 durable 回流;goal_report 收口)
  ──▶ ④card(人卡:等待即挂起,approve 续跑/reject 终止)──▶ ⑤verify(绿测+交付物,
  机器+审查者+变异门三裁判)──▶ ⑥settle(终态落 GoalIndex;完成卡/K2 结算=P2 待接线)
崩溃任意点 ──▶ durable 提交线续跑;预算尽/证据不过 ──▶ failed+卡,绝不静默</div>
					</div>
				</div>
			</div>

			<!-- ═══ 架构子页入口 ═══ -->
			<div class="mb-6">
				<div class="text-sm font-medium text-black dark:text-white mb-2">架构子页(点开看全图)</div>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<a
						href="/arch/pi"
						target="_blank"
						rel="noreferrer"
						class="group rounded-xl border border-gray-100 dark:border-gray-850 p-4 hover:border-gray-300 dark:hover:border-gray-700 transition"
					>
						<div class="flex items-center justify-between">
							<div class="text-sm font-medium text-black dark:text-white">pi 执行内核</div>
							<span class="text-xs text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300">/arch/pi ↗</span>
						</div>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
							内核八项能力 · 与 banyan 引擎对接 · subagent 调度映射 · /run 生命周期 · 全触点总览——本页下方同款图板
						</p>
					</a>
					<a
						href="/arch/banyan"
						target="_blank"
						rel="noreferrer"
						class="group rounded-xl border border-gray-100 dark:border-gray-850 p-4 hover:border-gray-300 dark:hover:border-gray-700 transition"
					>
						<div class="flex items-center justify-between">
							<div class="text-sm font-medium text-black dark:text-white">banyan goal 内核与统一机制(v3)</div>
							<span class="text-xs text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300">/arch/banyan ↗</span>
						</div>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
							goal 六相状态机 · 统一机制链(触发→goal→人卡→结算)· v2→v3 迁移对照 · 四机械保证——全图示
						</p>
					</a>
					<a
						href="/arch/webui"
						target="_blank"
						rel="noreferrer"
						class="group rounded-xl border border-gray-100 dark:border-gray-850 p-4 hover:border-gray-300 dark:hover:border-gray-700 transition md:col-span-2"
					>
						<div class="flex items-center justify-between">
							<div class="text-sm font-medium text-black dark:text-white">WebUI × 引擎对接</div>
							<span class="text-xs text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300">/arch/webui ↗</span>
						</div>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1.5">
							一条消息的完整旅行(八步时序)· /banyan/api 代理面与鉴权链 · 零双写存储 · 组件触点——全图示
						</p>
					</a>
				</div>
			</div>

			<!-- ═══ pi 执行内核(图示子页嵌入:/arch/pi)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mb-6"
				data-testid="banyan-arch-pi"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					pi 执行内核——内核分层 · 引擎对接 · /run 生命周期(全图示)
				</div>
				<iframe
					src="/arch/pi"
					title="pi 架构与对接图"
					style="height: {piHeight}px"
					class="w-full rounded-lg border border-gray-100 dark:border-gray-850"
				/>
			</div>


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
