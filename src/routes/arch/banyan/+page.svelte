<script lang="ts">
	// /arch/banyan(v3 重画):goal 内核架构——pi-durable 之上的薄编排。
	// 事实出处:banyan/pi-goal 源码(goal.ts 六相/subagent.ts 常驻子代理/docs.ts 提交文档)
	// + 方案-v3-薄banyan-on-pi-durable.md;只讲新架构本身,不做新旧对比。
	import { onMount } from 'svelte';

	onMount(() => {
		const post = () => {
			if (window.parent !== window) {
				const inner = document.querySelector('.max-w-full');
				const height = inner
					? Math.ceil(inner.getBoundingClientRect().height) + 2
					: document.documentElement.scrollHeight;
				window.parent.postMessage(
					{ type: 'banyan-arch-banyan-height', height },
					window.location.origin
				);
			}
		};
		post();
		const ro = new ResizeObserver(post);
		ro.observe(document.body);
		window.addEventListener('resize', post);
		return () => {
			ro.disconnect();
			window.removeEventListener('resize', post);
		};
	});
</script>

<svelte:head>
	<title>banyan goal 内核架构</title>
</svelte:head>

<div class="h-screen overflow-y-auto">
	<div class="max-w-full mx-auto w-full px-4 py-6">
		<div class="flex items-baseline justify-between mb-4">
			<h1 class="text-lg font-semibold text-gray-900 dark:text-white">
				banyan v3:goal 内核与统一机制(pi-durable)
			</h1>
			<span class="text-[11px] text-gray-400 dark:text-gray-500">
				pi-goal :8101 · durable SQLite 执行正本 · 直接切换已执行(触发器/波次迁移待接)
			</span>
		</div>

		<!-- ═══ 图一:goal 六相状态机 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图一 · goal 任务六相——一条 durable 提交线,崩溃即续跑
			</div>
			<svg viewBox="0 0 1080 330" class="w-full h-auto" role="img" aria-label="goal 六相状态机">
				<defs>
					<marker id="g3-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
						<path d="M0,0 L10,5 L0,10 z" class="fill-gray-400 dark:fill-gray-600" />
					</marker>
				</defs>
				<g font-size="10.5" text-anchor="middle">
					<rect x="14" y="40" width="150" height="76" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="89" y="64" font-weight="600" class="fill-gray-800 dark:fill-gray-100">① seed</text>
					<text x="89" y="82" class="fill-gray-500 dark:fill-gray-400">建管理者会话(引擎 md 逐字)</text>
					<text x="89" y="98" class="fill-gray-500 dark:fill-gray-400">GoalIndex 落账 · configure</text>

					<rect x="192" y="40" width="150" height="76" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="267" y="64" font-weight="600" class="fill-gray-800 dark:fill-gray-100">② plan</text>
					<text x="267" y="82" class="fill-gray-500 dark:fill-gray-400">submit(objective) 等答案</text>
					<text x="267" y="98" class="fill-gray-500 dark:fill-gray-400">requestId 幂等(崩溃不重发)</text>

					<rect x="370" y="40" width="190" height="76" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="465" y="64" font-weight="600" class="fill-gray-900 dark:fill-gray-100">③ execute(轮次循环)</text>
					<text x="465" y="82" class="fill-gray-500 dark:fill-gray-400">每轮一 submit;goal_report 收口</text>
					<text x="465" y="98" class="fill-gray-500 dark:fill-gray-400">预算=轮数帽+墙钟 · 红测前置</text>

					<rect x="588" y="40" width="160" height="76" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="668" y="64" font-weight="600" class="fill-gray-900 dark:fill-gray-100">④ card(人卡)</text>
					<text x="668" y="82" class="fill-gray-500 dark:fill-gray-400">CardIndex 开卡;相内 watchDoc</text>
					<text x="668" y="98" class="fill-gray-500 dark:fill-gray-400">HTTP resolve → approve/reject</text>

					<rect x="776" y="40" width="140" height="76" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="846" y="64" font-weight="600" class="fill-gray-800 dark:fill-gray-100">⑤ verify</text>
					<text x="846" y="82" class="fill-gray-500 dark:fill-gray-400">绿测 exit 0 · 交付物实存</text>
					<text x="846" y="98" class="fill-gray-500 dark:fill-gray-400">只验存在与形状,不判内容</text>

					<rect x="944" y="40" width="122" height="76" rx="8" class="fill-green-50 dark:fill-gray-900 stroke-green-400/50 dark:stroke-gray-700" />
					<text x="1005" y="64" font-weight="600" class="fill-gray-900 dark:fill-gray-100">⑥ settle</text>
					<text x="1005" y="82" class="fill-gray-500 dark:fill-gray-400">终态落 GoalIndex</text>
					<text x="1005" y="98" class="fill-gray-500 dark:fill-gray-400">summary/verified 随结果</text>
				</g>
				<line x1="164" y1="78" x2="190" y2="78" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="342" y1="78" x2="368" y2="78" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="560" y1="78" x2="586" y2="78" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="748" y1="78" x2="774" y2="78" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="916" y1="78" x2="942" y2="78" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />

				<!-- 终止语义 -->
				<g font-size="10" text-anchor="middle">
					<rect x="370" y="170" width="378" height="64" rx="8" class="fill-transparent stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
					<text x="559" y="192" font-weight="600" class="fill-gray-600 dark:fill-gray-400">终止路径(全部落 GoalIndex,绝不静默)</text>
					<text x="559" y="210" class="fill-gray-500 dark:fill-gray-400">预算尽=failed · 人卡 reject=aborted · 红测未红=failed(no-op 自证)</text>
					<text x="559" y="226" class="fill-gray-500 dark:fill-gray-400">abort(HTTP)=aborted · verify 不过=failed+原因</text>
				</g>
				<line x1="465" y1="116" x2="465" y2="168" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="668" y1="116" x2="668" y2="168" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="14" y="300" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">机制件:ReportDoc(goal_report 写/goal 读——注意力锚)· PlanDoc(plan_update 写/每轮回放)· Subagents(常驻子代理注册表,答案经 reporter 回流)——全部是与条目同事务提交的 durable 文档,压缩不丢。</text>
			</svg>
		</div>

		<!-- ═══ 图二:统一机制链 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图二 · 统一机制——一切审查/准入/裁决都是「触发 → goal → (异常→再触发) → 任务」
			</div>
			<svg viewBox="0 0 1080 300" class="w-full h-auto" role="img" aria-label="统一机制链">
				<g font-size="10.5" text-anchor="middle">
					<!-- 触发层 -->
					<rect x="14" y="24" width="200" height="88" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="114" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">触发层(引擎持有 · P2 接线中)</text>
					<text x="114" y="68" class="fill-gray-500 dark:fill-gray-400">现入口=手动 HTTP /goals;cron/git watch 待接</text>
					<text x="114" y="84" class="fill-gray-500 dark:fill-gray-400">K1 事件订阅 · 手动</text>
					<text x="114" y="100" class="fill-gray-500 dark:fill-gray-400">requestId 幂等 → 重启不重发</text>

					<!-- goal 内核 -->
					<rect x="272" y="24" width="240" height="88" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="392" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">goal 内核(pi-goal :8101)</text>
					<text x="392" y="68" class="fill-gray-500 dark:fill-gray-400">pi-durable Harness · SQLite 执行正本</text>
					<text x="392" y="84" class="fill-gray-500 dark:fill-gray-400">六相任务 · 常驻 subagent · 人卡</text>
					<text x="392" y="100" class="fill-gray-500 dark:fill-gray-400">HTTP:/goals /cards /usage /health</text>

					<!-- 管理者+子代理 -->
					<rect x="570" y="24" width="240" height="88" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="690" y="48" font-weight="600" class="fill-gray-800 dark:fill-gray-100">管理者会话 + 常驻子代理</text>
					<text x="690" y="68" class="fill-gray-500 dark:fill-gray-400">instructions=引擎 md(逐字)· GLM</text>
					<text x="690" y="84" class="fill-gray-500 dark:fill-gray-400">subagent spawn/send/stop · 答案回流</text>
					<text x="690" y="100" class="fill-gray-500 dark:fill-gray-400">CodingTools 沙箱(工作区 cwd)</text>

					<!-- 人的触点 -->
					<rect x="868" y="24" width="198" height="88" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" />
					<text x="967" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">人(信箱/卡)</text>
					<text x="967" y="68" class="fill-gray-500 dark:fill-gray-400">GET /cards → 引擎镜像 → 信箱卡</text>
					<text x="967" y="84" class="fill-gray-500 dark:fill-gray-400">POST /cards/:id/resolve</text>
					<text x="967" y="100" class="fill-gray-500 dark:fill-gray-400">approve=续跑 · reject=aborted</text>
				</g>
				<line x1="214" y1="68" x2="270" y2="68" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="512" y1="68" x2="568" y2="68" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="810" y1="68" x2="866" y2="68" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="967" y1="112" x2="967" y2="140" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<line x1="967" y1="140" x2="392" y2="140" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" />
				<line x1="392" y1="140" x2="392" y2="112" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="680" y="134" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">处置回流(watchDoc 唤醒等待中的 goal)</text>

				<g font-size="10.5" text-anchor="middle">
					<rect x="14" y="180" width="486" height="88" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="257" y="204" font-weight="600" class="fill-gray-800 dark:fill-gray-100">场景一:每日交叉审查(cron 02:00)</text>
					<text x="257" y="224" class="fill-gray-500 dark:fill-gray-400">goal(3×审查者并行 + 汇总)→ 异常报告(目标形态:P2 接线后全自动)</text>
					<text x="257" y="240" class="fill-gray-500 dark:fill-gray-400">→ 人卡或自动触发深审 goal → 结论提交执行 goal</text>
					<text x="257" y="258" class="fill-gray-500 dark:fill-gray-400">全程同一套原语,无专属代码路径</text>

					<rect x="540" y="180" width="526" height="88" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="803" y="204" font-weight="600" class="fill-gray-800 dark:fill-gray-100">场景二:代码变更审查(git watch)</text>
					<text x="803" y="224" class="fill-gray-500 dark:fill-gray-400">变更(去抖+最小间隔)→ 同一条链</text>
					<text x="803" y="240" class="fill-gray-500 dark:fill-gray-400">审查 goal → 异常 → 深审 → 执行</text>
					<text x="803" y="258" class="fill-gray-500 dark:fill-gray-400">机制交互统一:触发器只做一件事——create_goal(requestId)</text>
				</g>
			</svg>
		</div>

		<!-- ═══ 图三:全景分层架构 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图三 · 全景分层架构——谁负责什么、怎么接线、正本归谁
			</div>
			<svg viewBox="0 0 1080 430" class="w-full h-auto" role="img" aria-label="全景分层架构">
				<g font-size="10.5" text-anchor="middle">
					<!-- WebUI -->
					<rect x="14" y="24" width="200" height="150" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="114" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">WebUI(:8080)</text>
					<text x="114" y="70" class="fill-gray-500 dark:fill-gray-400">身份认证(账号体系)</text>
					<text x="114" y="86" class="fill-gray-500 dark:fill-gray-400">界面呈现(对话/信箱/日历</text>
					<text x="114" y="102" class="fill-gray-500 dark:fill-gray-400">·工作空间/架构页)</text>
					<text x="114" y="122" class="fill-gray-500 dark:fill-gray-400">/banyan/api 代理(登录门槛</text>
					<text x="114" y="138" class="fill-gray-500 dark:fill-gray-400">+Bearer 注入)</text>
					<text x="114" y="160" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">正本:webui.db(仅身份与偏好,零消息)</text>

					<!-- 引擎 -->
					<rect x="272" y="24" width="240" height="150" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="392" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">引擎(:8000,门卫+记账)</text>
					<text x="392" y="70" class="fill-gray-500 dark:fill-gray-400">触发器(P2 待接:手动 HTTP 已通)</text>
					<text x="392" y="86" class="fill-gray-500 dark:fill-gray-400">·K1 事件订阅 · 手动</text>
					<text x="392" y="106" class="fill-gray-500 dark:fill-gray-400">K1 事件账(事实与审计正本)</text>
					<text x="392" y="122" class="fill-gray-500 dark:fill-gray-400">store 工具回调(信箱/日历</text>
					<text x="392" y="138" class="fill-gray-500 dark:fill-gray-400">/台账/知识直读)·人卡处置面</text>
					<text x="392" y="160" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">正本:K1 events/ jsonl(唯一写者)</text>

					<!-- pi-goal -->
					<rect x="570" y="24" width="240" height="150" rx="8" class="fill-green-50 dark:fill-gray-900 stroke-green-400/60 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="690" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">pi-goal(:8101,goal 内核)</text>
					<text x="690" y="70" class="fill-gray-500 dark:fill-gray-400">pi-durable Harness(提交线)</text>
					<text x="690" y="86" class="fill-gray-500 dark:fill-gray-400">goal 六相任务 · 常驻 subagent</text>
					<text x="690" y="102" class="fill-gray-500 dark:fill-gray-400">预算(轮数/墙钟) · 证据校验</text>
					<text x="690" y="122" class="fill-gray-500 dark:fill-gray-400">人卡(watchDoc 等待)</text>
					<text x="690" y="138" class="fill-gray-500 dark:fill-gray-400">HTTP:/goals · /cards · /usage</text>
					<text x="690" y="160" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">正本:session.sqlite(执行态,durable)</text>

					<!-- pi-sidecar + GLM -->
					<rect x="868" y="24" width="198" height="150" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="967" y="48" font-weight="600" class="fill-gray-800 dark:fill-gray-100">pi-sidecar(:8100)</text>
					<text x="967" y="70" class="fill-gray-500 dark:fill-gray-400">pi 执行内核(无角色 /run)</text>
					<text x="967" y="86" class="fill-gray-500 dark:fill-gray-400">对话面(秘书 ReAct·沙箱)</text>
					<text x="967" y="106" class="fill-gray-500 dark:fill-gray-400">会话树 · 事件流(镜像 K1)</text>
					<text x="967" y="130" font-weight="600" class="fill-gray-800 dark:fill-gray-100">GLM(zai-coding-cn)</text>
					<text x="967" y="148" class="fill-gray-500 dark:fill-gray-400">glm-5.3 / glm-5.3-flash</text>
					<text x="967" y="164" class="fill-gray-500 dark:fill-gray-400">流式 · token 计量(cost 价目未配)</text>
				</g>
				<!-- 接线箭头 -->
				<line x1="214" y1="90" x2="270" y2="90" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="242" y="82" text-anchor="middle" font-size="9" class="fill-gray-400 dark:fill-gray-500">SSE/代理</text>
				<line x1="512" y1="90" x2="568" y2="90" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="540" y="82" text-anchor="middle" font-size="9" class="fill-gray-400 dark:fill-gray-500">BANYAN_GOAL_URL</text>
				<line x1="392" y1="174" x2="392" y2="206" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="400" y="196" font-size="9" class="fill-gray-400 dark:fill-gray-500">对话面 /v1/chat/completions</text>
				<line x1="810" y1="174" x2="810" y2="206" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" />
				<line x1="810" y1="206" x2="967" y2="206" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#g3-ar)" />
				<text x="890" y="200" text-anchor="middle" font-size="9" class="fill-gray-400 dark:fill-gray-500">管理者/子代理 → GLM 流式</text>

				<!-- 正本归属条 -->
				<rect x="14" y="240" width="1052" height="46" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
				<text x="540" y="258" text-anchor="middle" font-size="10.5" font-weight="600" class="fill-gray-700 dark:fill-gray-300">正本纪律:K1 事件账=事实与审计正本(引擎)· session.sqlite=执行态正本(pi-goal,断点续跑)· 知识仓(git)=知识正本 · webui.db=身份偏好</text>
				<text x="540" y="276" text-anchor="middle" font-size="10" class="fill-gray-500 dark:fill-gray-400">职责铁律:内核不拥有事实与知识正本;角色定义权 100% 在引擎 agents/*.md(逐字下发);前端不执行工具</text>

				<!-- 七原语 -->
				<text x="540" y="322" text-anchor="middle" font-size="11" font-weight="600" class="fill-gray-700 dark:fill-gray-300">全系统只有七个原语——一切机制都是它们的组合:</text>
				<g font-size="10" text-anchor="middle">
					{#each primitives as prim, i}
						<rect x="{14 + i * 152}" y="338" width="140" height="72" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-200 dark:stroke-gray-800" />
						<text x="{84 + i * 152}" y="360" font-weight="600" class="fill-gray-800 dark:fill-gray-100">{prim.n}</text>
						<text x="{84 + i * 152}" y="378" class="fill-gray-500 dark:fill-gray-400">{prim.a}</text>
						<text x="{84 + i * 152}" y="394" class="fill-gray-500 dark:fill-gray-400">{prim.b}</text>
					{/each}
				</g>
			</svg>
		</div>

		<!-- ═══ 四机械保证 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
			<div class="text-sm font-medium text-black dark:text-white mb-2">四条机械保证(v3 落点)</div>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
				{#each guarantees as g}
					<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
						<div class="font-semibold text-gray-800 dark:text-gray-200">{g.n}</div>
						<div class="text-gray-500 dark:text-gray-400 mt-1">{g.d}</div>
					</div>
				{/each}
			</div>
			<p class="text-[10.5px] text-gray-400 dark:text-gray-500 mt-2">
				正本纪律(v3 修订):执行态正本归 pi-goal durable 存储(断点续跑的前提);K1 仍是全系统事实与审计正本(引擎镜像);知识正本不动。
			</p>
		</div>
	</div>
</div>

<script context="module">
	const primitives = [
		{ n: 'goal', a: '六相 durable 任务', b: '一切工作的载体' },
		{ n: 'trigger', a: 'cron/git watch/K1 订阅', b: '唯一发起方式' },
		{ n: 'agent', a: '管理者+常驻子代理', b: '提示词正本在引擎' },
		{ n: 'task', a: 'durable 状态机', b: '子任务/锚/reporter' },
		{ n: 'card', a: '人卡(等待即挂起)', b: '人的唯一触点' },
		{ n: 'evidence', a: '红绿/交付物', b: '机械可验证据' },
		{ n: 'ledger', a: 'K1 事件账', b: '事实与审计正本' }
	];

	const guarantees = [
		{ n: '防自证', d: '红测前置必须红 + verify 只认机械证据(文件/exit code),不认 Agent 自述——pi-goal execute/verify 相' },
		{ n: '人的触点', d: 'card 相= durable 等待;approve/reject 经 HTTP/引擎信箱;goal 在等待期零代码运行' },
		{ n: '失败诚实', d: '一切过单一原子提交线先存储后展示;崩溃 resume();requestId 幂等;终止路径全落 GoalIndex' },
		{ n: '无界开销', d: '预算=轮数帽+墙钟(execute 相间检查);预算尽=failed 或人卡,绝不静默' }
	];
</script>
