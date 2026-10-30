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

	// RF2-D 类级修复(同 goals 页竞态形态):原 onMount(async) 返回 Promise,
	// 其 return 的 cleanup 从未被注册——destroy 早于 interval 建立时泄漏
	// (interval 自限 60 次故有界,但窗口存在)。改 dead 标志 + 真 cleanup。
	onMount(() => {
		let dead = false;
		let fit: ReturnType<typeof setInterval> | undefined;
		void (async () => {
			try {
				const status = await getBanyanStatus();
				home = status.engine.home ?? '';
				agents = status.agents ?? [];
			} catch {
				home = '';
			}
			loaded = true;
			if (dead) return;
			// 高度自适应兜底:同源直读子页内容高度——子页 postMessage 可能早于本页监听器挂载而丢失
			let tries = 0;
			fit = setInterval(() => {
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
		})();
		return () => {
			dead = true;
			clearInterval(fit);
		};
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
						<b>v4(判据全上移)</b>:角色层退役——系统只提供参数化执行单元(调度参数 task / tier / effort / tools),人设与调度习惯全部住进主 Agent 提示词;新增递归审查循环(见下)与知识自沉淀(goal 终态 → 知识 goal → 空间私有 knowledge/)。不退的三件:subagent 独立上下文 / goal 机械验收 / jail+凭证+K1 审计。
					</p>
					<p class="text-gray-500 dark:text-gray-400">
						存储根(BANYAN_HOME):
						<span class="break-all font-mono text-xs text-gray-700 dark:text-gray-300">
							{home || '引擎不可达'}
						</span>
					</p>
					<p class="text-gray-400 dark:text-gray-500 text-xs">
						人只出现在少数触点:批准方案、处置信箱、goal 人审卡(v4 递归审查不收敛升级亦落人卡)。其余全自动。
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
					v4:agents_baseline 由 4+1 角色收敛为执行底座(任务主 Agent 的 instructions 缺省)——subagent 调度不再按角色,按参数
					<code class="text-[10px]">task / tier / effort / tools</code>(工具面默认全量,可选覆盖;readOnly 等是能力不是角色)。每份 md(frontmatter:名称/描述/档位/工具/记忆/输出)提示词正本在
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

			<!-- ═══ 递归审查循环(设计 v4 §3)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-review-loop"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					递归审查循环(设计 v4)——双触发 → 交叉审查 → 指纹/不收敛治理 → 人卡
				</div>
				<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto mb-3">
cron 每日 ─┐                     ┌─ subagent×N 交叉审查(独立上下文,多切面)
git watch ─┼→ goal_start(审查)──┤        ↓
(变更≥N)─┘   对象=主分支全量diff  └─ 汇最佳方案 → goal_start(修复) → 下轮连带
                                        ↓
                          指纹库:fingerprint=hash(文件+区域+问题类)
                          同指纹再现→轮次+1;连续 3 轮未收敛→停自修+人卡
				</div>
				<ul class="space-y-1 text-gray-500 dark:text-gray-400 list-disc pl-4">
					<li>触发:①automation cron(每日)②git watch(引擎 loop 定期 fetch,last_reviewed_sha..origin/main 变更数≥阈值)——零 LLM 触发</li>
					<li>指纹:审查发现落 K1(review.finding 带 fingerprint);轮次=跨 run 聚合;anchor 用符号名/逻辑区块名(行号随修复漂移会断链)</li>
					<li>不收敛治理:同指纹连续 3 轮 → 禁止自修,升级人卡附完整轮次史(铁律 6 同构:禁止第三次打补丁)</li>
					<li>审查 goal 验收内置交叉收敛纪律(交叉印证/指控分离/回退验证);review_report 是唯一汇报正门</li>
				</ul>
			</div>

			<!-- ═══ 知识自沉淀(设计 v4 §2)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-knowledge-settle"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					知识自沉淀(设计 v4)——goal 终态 → 知识 goal → 空间私有域
				</div>
				<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto mb-3">
goal 终态(completed|failed|aborted)─┐
cron ─────────────────────────────┴→ 起 kind=knowledge 的知识 goal
        (知识官底座 instructions)→ 提炼/去重(grep 同主题先更新)/更新/归档
        → 写空间私有 knowledge/(条目三段式;K3 cards/ 为机制挂载点)
        → K1:knowledge.goal_started / knowledge.settled(dedup 正本)
				</div>
				<ul class="space-y-1 text-gray-500 dark:text-gray-400 list-disc pl-4">
					<li>自递归防护三重:知识 goal 终态不再触发 / objective 前缀标记 / kind=knowledge 跳过</li>
					<li>同 goal 只沉淀一次:dedup 正本=K1 knowledge.settled(kv 只是加速缓存,启动从 K1 重建)</li>
					<li>v4 目录清理:knowledge/agents、knowledge/workflow 已删(空目录零消费);正本=空间私有 knowledge/</li>
				</ul>
			</div>

			<!-- ═══ Agent 交互(v4 参数化;旧「角色交互」表述已废)═══ -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs mb-6"
				data-testid="banyan-arch-interactions"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					Agent 交互(Agent 之间永不直接对话,一切经三种黑板:K1 事件流 · 工作区文件 · 人卡/信箱)
				</div>
				<div class="space-y-4">
					<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">对话流(主 Agent 主导)</div>
						<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">
人 ─▶ WebUI ─▶ /conv submit(主 Agent durable 会话+回调工具∪subagent)
  ├─ 工具调用 ─▶ HTTP 回调 ─▶ 引擎 store 直读(信箱/任务/台账/日历)
  ├─ subagent(参数化:task/tier/effort/tools,v4 起 role 退役) ─▶ 常驻子代理 ─▶ 答案自动回流
  └─ 回复 ──▶ pi_event 镜像 ─▶ SSE ─▶ WebUI 流式 ──▶ chat.db(K1 先行)
						</div>
					</div>
<div>
						<div class="font-medium text-gray-700 dark:text-gray-300 mb-1">机制流(goal 内核主导——一切机制的统一形态)</div>
							<div class="font-mono text-[11px] text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 rounded p-2 overflow-x-auto">触发(cron/git watch/K1 订阅/手动)──▶ goal(requestId 幂等)
  ①seed(管理者会话=引擎 md 逐字)──▶ ②plan ──▶ ③execute(轮次+预算+红测前置;
  管理者自行 spawn 参数化子代理,答案 durable 回流;goal_report 收口)
  ──▶ ④card(人卡:等待即挂起,approve 续跑/reject 终止)──▶ ⑤verify(绿测+交付物,
  机器验收:AC/证据/预算/人卡,v4 判据全上移)──▶ ⑥settle(终态落 GoalIndex)
崩溃任意点 ──▶ durable 提交线续跑;预算尽/证据不过 ──▶ failed+卡,绝不静默
settle ──▶ (v4)知识自沉淀:终态事件自动起知识 goal,提炼入空间私有 knowledge/</div>
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
								<td class="py-1 pr-3">知识正本</td>
								<td>空间私有 knowledge/(v4 自沉淀:条目三段式;cards/ 留作 K3 挂载点;knowledge/agents、workflow 已删)</td>
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
