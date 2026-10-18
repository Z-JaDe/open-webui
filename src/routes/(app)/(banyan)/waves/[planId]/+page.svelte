<script lang="ts">
	// /waves/[planId] — WaveBoard 全屏 + 任务检查器（钩点③，统一设计 §6.1 / §8 G3）
	// 数据源：GET /banyan/api/plans/:planId（代理桥 → 引擎）。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import { getBanyanPlan, type BanyanPlanSnapshot } from '$lib/apis/banyan';
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

	const load = async () => {
		error = null;
		const mock = new URLSearchParams(window.location.search).has('mock');
		if (mock) {
			snapshot = mockSnapshot;
			loaded = true;
			return;
		}
		snapshot = await getBanyanPlan($page.params.planId).catch((e) => {
			error = `${e}`;
			toast.error(`方案加载失败: ${e}`);
			return null;
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
			</div>
		</div>
	{:else}
		<div class="text-xs text-gray-400 dark:text-gray-500">
			{loaded ? '未找到方案' : '加载中'}…
		</div>
	{/if}
</div>
