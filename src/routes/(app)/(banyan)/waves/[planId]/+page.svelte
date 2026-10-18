<script lang="ts">
	// /waves/[planId] — WaveBoard 全屏 + 任务检查器（钩点③，统一设计 §6.1 / §8 G3）
	// 数据源：GET /banyan/api/plans/:planId（代理桥 → 引擎）。
	// RF-20b：任务检查器内新增断言登记簿区块（GET /registry?plan_id=X，红测断言
	// fingerprint 带 "red-" 前缀 → 🔴开工红测/🟢交付验收 两组并排）；引擎方案行
	// status=blocked（完成门/攻击门拦截）时页顶黄色提示条，跳信箱/审计。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）；?mock=1&blocked=1 预览拦截条。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import {
		getBanyanPlan,
		getBanyanPlanRegistry,
		type BanyanPlanAssertion,
		type BanyanPlanSnapshot
	} from '$lib/apis/banyan';
	import WaveBoard from '$lib/components/banyan/WaveBoard.svelte';
	import PlanCard from '$lib/components/banyan/PlanCard.svelte';
	import {
		BANYAN_TASK_STATUS_LABEL,
		type BanyanTaskStatus
	} from '$lib/components/banyan/types';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let error: string | null = null;
	let snapshot: BanyanPlanSnapshot | null = null;
	// 任务检查器当前选中
	let selected: { task_id: string; status: BanyanTaskStatus; detail?: string; deps?: string[]; title?: string } | null =
		null;
	// RF-20b：方案断言登记簿（fail-soft——加载失败不打断方案视图）
	let assertions: BanyanPlanAssertion[] = [];
	let assertionsError: string | null = null;

	// 红绿分组轴（冻结契约）：fingerprint "red-" 前缀=开工红测，其余=交付验收
	const isRedAssertion = (a: BanyanPlanAssertion) => a.fingerprint.startsWith('red-');
	$: redAssertions = assertions.filter(isRedAssertion);
	$: greenAssertions = assertions.filter((a) => !isRedAssertion(a));
	// 完成门/攻击门拦截：PLAN_STATUS_MAP 把 blocked 折进 approved，原始态另看 engine_status
	$: gateBlocked = snapshot?.engine_status === 'blocked';

	// 通过/未通过着色（verdict 由 apis 层从 last_result+阶段 detail 归一）
	const VERDICT_LABEL: Record<BanyanPlanAssertion['verdict'], string> = {
		pass: '通过',
		fail: '未通过',
		unknown: '未验证'
	};
	const VERDICT_CLASS: Record<BanyanPlanAssertion['verdict'], string> = {
		pass: 'text-green-600 dark:text-green-400',
		fail: 'text-red-600 dark:text-red-400',
		unknown: 'text-gray-400 dark:text-gray-500'
	};

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	$: banyanLayout.setHeader?.({
		itemName: `方案 · ${$page.params.planId}`
	});

	const mockSnapshot: BanyanPlanSnapshot = {
		plan: {
			type: 'plan',
			plan_id: 'plan-mock-001',
			title: '重构 banyan 调度器为波次模型',
			status: 'approved',
			hypothesis: '波次并发可在不牺牲正确性的前提下提速。',
			waves: [
				{
					index: 1,
					title: '探路',
					tasks: [
						{ task_id: 't-101', title: '梳理现有依赖图', deps: [] },
						{ task_id: 't-102', title: '锁定回归基线', deps: [] }
					]
				},
				{
					index: 2,
					title: '改造',
					depends_on: [1],
					tasks: [
						{ task_id: 't-201', title: '实现波次调度器', deps: ['t-101'] },
						{ task_id: 't-202', title: '迁移存量用例', deps: ['t-101', 't-102'] }
					]
				},
				{
					index: 3,
					title: '收口',
					depends_on: [2],
					tasks: [{ task_id: 't-301', title: '全量回归 + 落账断言', deps: ['t-201', 't-202'] }]
				}
			],
			acceptance: ['167 个存量用例全绿', '波次并发度 ≥ 3'],
			risks: ['依赖图解析错误可能导致空转'],
			rollback: 'revert 调度器切换 commit'
		},
		wave_updates: [
			{
				type: 'wave_update',
				plan_id: 'plan-mock-001',
				wave: 1,
				tasks: [
					{ task_id: 't-101', title: '梳理现有依赖图', status: 'done', detail: '17 节点 23 边' },
					{ task_id: 't-102', title: '锁定回归基线', status: 'done', detail: '基线 commit 9f31c2' }
				]
			},
			{
				type: 'wave_update',
				plan_id: 'plan-mock-001',
				wave: 2,
				tasks: [
					{
						task_id: 't-201',
						title: '实现波次调度器',
						status: 'failed',
						deps: ['t-101'],
						detail: 'merge conflict in scheduler.py'
					},
					{ task_id: 't-202', title: '迁移存量用例', status: 'pending', deps: ['t-101', 't-102'] }
				]
			},
			{
				type: 'wave_update',
				plan_id: 'plan-mock-001',
				wave: 3,
				tasks: [
					{ task_id: 't-301', title: '全量回归 + 落账断言', status: 'blocked', deps: ['t-201', 't-202'] }
				]
			}
		]
	};

	// RF-20b mock：断言登记簿样例（与冻结契约同形——红测行 fingerprint 带 "red-" 前缀、
	// spec 为红测命令、last_result 带 "pre-work red"/"final green" 阶段 detail）
	const mockAssertions: BanyanPlanAssertion[] = [
		{
			id: 'reg-mock-r1',
			fingerprint: 'red-9f31c2b7a4d5e6f7',
			spec: 'pytest tests/test_scheduler.py -k wave_fanout',
			status: 'red',
			last_result: 'pre-work red',
			verdict: 'fail',
			last_checked_at: Date.now() - 1000 * 900,
			task_id: 't-201'
		},
		{
			id: 'reg-mock-r2',
			fingerprint: 'red-3a7d1c9e5b2f4806',
			spec: 'npm run test -- --grep 波次并发',
			status: 'green',
			last_result: 'final green',
			verdict: 'pass',
			last_checked_at: Date.now() - 1000 * 300,
			task_id: 't-202'
		},
		{
			id: 'reg-mock-g1',
			fingerprint: '5c2e8a1d7f3b9046',
			spec: 'pytest tests/ -q（存量回归 167 例）',
			status: 'green',
			last_result: 'pass',
			verdict: 'pass',
			last_checked_at: Date.now() - 1000 * 240,
			task_id: 't-301'
		},
		{
			id: 'reg-mock-g2',
			fingerprint: '8d4f0b2e6a9c1357',
			spec: '波次并发度 ≥ 3（bench/wave.py）',
			status: 'unknown',
			verdict: 'unknown',
			task_id: 't-301'
		}
	];

	const load = async () => {
		error = null;
		assertionsError = null;
		const pid: string = $page.params.planId ?? '';
		const params = new URLSearchParams(window.location.search);
		if (params.has('mock')) {
			snapshot = {
				...mockSnapshot,
				// ?mock=1&blocked=1 预览完成门拦截提示条
				engine_status: params.has('blocked') ? 'blocked' : 'approved'
			};
			assertions = mockAssertions;
			loaded = true;
			return;
		}
		snapshot = await getBanyanPlan(pid).catch((e) => {
			error = `${e}`;
			toast.error(`方案加载失败: ${e}`);
			return null;
		});
		if (!snapshot) {
			loaded = true;
			return;
		}
		// RF-20b：断言登记簿随快照同刷（fail-soft，失败只提示不打断）
		assertions = await getBanyanPlanRegistry(pid).catch((e) => {
			assertionsError = `${e}`;
			return [];
		});
		loaded = true;
	};

	// 简易自动刷新（长任务跨重启靠汇报轮，这里 30s 轮询兜底）
	let autoRefresh: ReturnType<typeof setInterval> | null = null;
	onMount(() => {
		load();
		autoRefresh = setInterval(load, 30000);
		return () => {
			if (autoRefresh) clearInterval(autoRefresh);
		};
	});
</script>

<svelte:head><title>方案 · banyan</title></svelte:head>

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3 space-y-4">
	{#if error}
		<div class="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400">
			经 /banyan/api 无法连通引擎——请先启动引擎，或追加 ?mock=1 用内置样例数据预览。
			<br />
			{error}
		</div>
	{/if}

	<!-- RF-20b：完成门/攻击门拦截提示条（引擎 plan.status=blocked；不解析 reasons，
		机械卡在信箱、细节在 K1——给跳转即可） -->
	{#if gateBlocked}
		<div
			class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-700 dark:text-amber-300 space-y-1.5"
			role="alert"
		>
			<div class="font-semibold text-amber-800 dark:text-amber-200">方案被拦截</div>
			<div>完成门拦截——查信箱卡与 K1（原因：交付物缺失/回归红等）</div>
			<div class="flex items-center gap-2 pt-0.5">
				<a
					href="/inbox"
					class="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 font-medium transition"
				>
					查看信箱卡
				</a>
				<a
					href="/audit"
					class="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 font-medium transition"
				>
					查 K1 审计
				</a>
			</div>
		</div>
	{/if}

	{#if snapshot}
		<PlanCard event={snapshot.plan} />

		<div class="grid gap-4 lg:grid-cols-[1fr_300px] items-start">
			<WaveBoard events={snapshot.wave_updates} plan={snapshot.plan} on:select={(e) => (selected = e.detail)} />

			<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 space-y-2">
				<div class="text-sm font-medium text-black dark:text-white">任务检查器</div>
				{#if selected}
					<div class="space-y-1.5 text-xs">
						<div>
							<span class="text-gray-400">task_id:</span>
							<span class="font-mono text-gray-700 dark:text-gray-200">{selected.task_id}</span>
						</div>
						<div>
							<span class="text-gray-400">标题:</span>
							<span class="text-gray-700 dark:text-gray-200">{selected.title ?? '-'}</span>
						</div>
						<div>
							<span class="text-gray-400">状态:</span>
							<span class="text-gray-700 dark:text-gray-200">
								{$i18n.t(BANYAN_TASK_STATUS_LABEL[selected.status])}
							</span>
						</div>
						{#if selected.deps?.length}
							<div>
								<span class="text-gray-400">依赖:</span>
								<span class="font-mono text-gray-700 dark:text-gray-200">{selected.deps.join(', ')}</span>
							</div>
						{/if}
						{#if selected.detail}
							<div class="rounded-lg bg-black/[0.03] dark:bg-white/[0.05] p-2 text-gray-600 dark:text-gray-300">
								{selected.detail}
							</div>
						{/if}
					</div>
				{:else}
					<div class="text-xs text-gray-400 dark:text-gray-500">
						点击任务格查看详情
					</div>
				{/if}

				<!-- RF-20b：断言登记簿区块（红绿两组并排：fingerprint "red-" 前缀=开工红测） -->
				<div class="pt-2 mt-1 border-t border-gray-100 dark:border-gray-850 space-y-2">
					<div class="flex items-center justify-between">
						<div class="text-sm font-medium text-black dark:text-white">断言登记簿</div>
						{#if assertions.length}
							<span class="text-[10px] text-gray-400">{assertions.length} 条</span>
						{/if}
					</div>
					{#if assertionsError}
						<div class="text-[11px] text-red-500 dark:text-red-400">
							断言登记簿加载失败：{assertionsError}
						</div>
					{:else if !assertions.length}
						<div class="text-xs text-gray-400 dark:text-gray-500">暂无断言登记</div>
					{:else}
						{#each [
							{ icon: '🔴', label: '开工红测', rows: redAssertions },
							{ icon: '🟢', label: '交付验收', rows: greenAssertions }
						] as group (group.label)}
							<div class="space-y-1.5">
								<div
									class="flex items-center gap-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400"
								>
									{group.icon}
									{$i18n.t(group.label)}
									<span class="font-normal text-gray-400">{group.rows.length}</span>
								</div>
								{#if group.rows.length}
									{#each group.rows as a (a.id)}
										<div
											class="rounded-lg bg-black/[0.03] dark:bg-white/[0.05] p-2 space-y-0.5"
										>
											<div
												class="font-mono text-[11px] text-gray-700 dark:text-gray-200 break-all"
											>
												{a.spec}
											</div>
											<div class="text-[11px] {VERDICT_CLASS[a.verdict]}">
												{$i18n.t(VERDICT_LABEL[a.verdict])}{a.last_result ? ` · ${a.last_result}` : ''}
											</div>
										</div>
									{/each}
								{:else}
									<div class="text-[11px] text-gray-400 dark:text-gray-500">
										{group.label === '开工红测' ? '暂无红测断言' : '暂无验收断言'}
									</div>
								{/if}
							</div>
						{/each}
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<div class="text-xs text-gray-400 dark:text-gray-500">
			{loaded ? '未找到方案' : '加载中'}…
		</div>
	{/if}
</div>
