<script lang="ts">
	// /waves — 方案列表页(F1/D2 改造:替代手输 id,状态分组一屏全览)。
	// 数据源:GET /banyan/api/plans?status=&limit=(代理桥 → 引擎);
	// 每行 subject + 相对时间 + 任务计数徽章,点击进 /waves/[planId] 下钻;
	// 手输 id 入口保留(折叠)。?mock=1 时走内置样例(不请求引擎)。
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { goto } from '$app/navigation';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';

	import type i18nType from '$lib/i18n';
	import { getBanyanPlans, type BanyanPlanListItem } from '$lib/apis/banyan';
	import { subscribeBanyanEvents, createBanyanRefresher } from '$lib/stores/banyanEvents';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';

	dayjs.extend(relativeTime);

	const i18n = getContext<Writable<i18nType>>('i18n');

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: $i18n.t('Waves') });

	let loaded = false;
	let error: string | null = null;
	let plans: BanyanPlanListItem[] = [];

	// 状态分组(D2):等待批准(含 open 初始态)/运行中/被拦截/已完成/已驳回|其他
	// (rejected|revised|orphaned 终态留史,归"其他"组;行永久可查)。
	const GROUPS: { label: string; statuses: string[]; dot: string }[] = [
		{ label: 'Awaiting approval', statuses: ['open', 'pending_approval'], dot: 'bg-amber-500' },
		{ label: 'Running', statuses: ['running'], dot: 'bg-blue-500' },
		{ label: 'Blocked', statuses: ['blocked'], dot: 'bg-red-500' },
		{ label: 'Finished', statuses: ['finished'], dot: 'bg-green-500' },
		{
			label: 'Rejected / others',
			statuses: ['rejected', 'revised', 'orphaned'],
			dot: 'bg-gray-400'
		}
	];

	const groupOf = (statuses: string[]) => plans.filter((p) => statuses.includes(p.status));
	const relTime = (ms?: number) => (ms ? dayjs(ms).fromNow() : '');

	const isMock = () => new URLSearchParams(window.location.search).has('mock');

	const mockPlans: BanyanPlanListItem[] = [
		{
			id: 'plan-mock-001',
			status: 'pending_approval',
			subject: '排查 RAG 知识管线收口问题并修复',
			created_at: Date.now() - 1000 * 600,
			tasks: { total: 6, done: 0, failed: 0, skipped: 0 }
		},
		{
			id: 'plan-mock-002',
			status: 'running',
			subject: '调度器波次划分重构',
			created_at: Date.now() - 1000 * 3600,
			tasks: { total: 8, done: 3, failed: 1, skipped: 0 }
		},
		{
			id: 'plan-mock-003',
			status: 'finished',
			subject: '信箱状态机超时策略落地',
			created_at: Date.now() - 1000 * 86400,
			tasks: { total: 4, done: 4, failed: 0, skipped: 0 }
		},
		{
			id: 'plan-mock-004',
			status: 'rejected',
			subject: '已被驳回的候选方案',
			created_at: Date.now() - 1000 * 172800,
			tasks: { total: 0, done: 0, failed: 0, skipped: 0 }
		}
	];

	const load = async () => {
		error = null;
		if (isMock()) {
			plans = mockPlans;
			loaded = true;
			return;
		}
		try {
			plans = await getBanyanPlans({ limit: 100 });
		} catch (e) {
			error = `${e}`;
			plans = [];
		}
		loaded = true;
	};

	let planId = '';

	const go = () => {
		if (!planId.trim()) return;
		const mock = isMock() ? '?mock=1' : '';
		goto(`/waves/${encodeURIComponent(planId.trim())}${mock}`);
	};

	const open = (p: BanyanPlanListItem) =>
		goto(`/waves/${encodeURIComponent(p.id)}${isMock() ? '?mock=1' : ''}`);

	onMount(load);

	// F8/D15:K1 事件驱动重取——orchestration.* 帧(方案开启/波次/任务状态/收口)到达
	// 即刷新列表,引擎跑完即见;页面在后台只记待办、回前台补取(防后台风暴),3s 节流。
	onMount(() => {
		const refresher = createBanyanRefresher(load);
		const unsubscribe = subscribeBanyanEvents(['orchestration.'], refresher.trigger);
		return () => {
			unsubscribe();
			refresher.dispose();
		};
	});
</script>

<svelte:head><title>{$i18n.t('Waves')} · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3 space-y-5">
	<div class="max-w-3xl space-y-4">
		{#if error}
			<div
				class="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400"
			>
				{$i18n.t('Engine unreachable via /banyan/api — start the engine or append ?mock=1 to preview with built-in sample data.')}
				<br />
				{error}
			</div>
		{/if}

		<!-- 状态分组方案列表(D2):等待批准/运行中/被拦截/已完成/已驳回|其他 -->
		{#each GROUPS as group (group.label)}
			{@const rows = groupOf(group.statuses)}
			{#if rows.length}
				<div class="space-y-2">
					<div class="flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
						<span class="size-1.5 rounded-full {group.dot}" />
						{$i18n.t(group.label)}
						<span class="font-normal text-gray-400">{rows.length}</span>
					</div>
					{#each rows as p (p.id)}
						<button
							type="button"
							class="w-full text-left rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 hover:bg-gray-100 dark:hover:bg-gray-850 transition"
							on:click={() => open(p)}
						>
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<div class="text-sm font-medium text-black dark:text-white truncate">
										{p.subject || p.id}
									</div>
									<div class="text-[11px] text-gray-400 dark:text-gray-500 truncate">
										{p.id} · {relTime(p.created_at)}
									</div>
								</div>
								<div class="shrink-0 flex items-center gap-1.5">
									{#if p.tasks.failed > 0}
										<span
											class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-600 dark:text-red-400"
										>
											{p.tasks.failed} {$i18n.t('failed')}
										</span>
									{/if}
									{#if p.tasks.skipped > 0}
										<span
											class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-500/10 text-gray-500 dark:text-gray-400"
										>
											{p.tasks.skipped} {$i18n.t('skipped')}
										</span>
									{/if}
									<span
										class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-black/[0.05] dark:bg-white/[0.08] text-gray-600 dark:text-gray-300"
									>
										{p.tasks.done}/{p.tasks.total} {$i18n.t('tasks')}
									</span>
								</div>
							</div>
						</button>
					{/each}
				</div>
			{/if}
		{/each}

		{#if loaded && plans.length === 0 && !error}
			<div class="text-xs text-gray-400 dark:text-gray-500">
				{$i18n.t('No plans yet — ask the butler in chat to draft one.')}
			</div>
		{/if}

		<!-- 手输 id 入口(折叠保留) -->
		<details class="max-w-md">
			<summary class="cursor-pointer text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 select-none">
				{$i18n.t('Open by plan id')}
			</summary>
			<form
				class="mt-2 flex items-center gap-2"
				on:submit={(e) => {
					e.preventDefault();
					go();
				}}
			>
				<input
					class="flex-1 text-xs rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850 outline-none"
					placeholder="plan-mock-001"
					bind:value={planId}
				/>
				<button
					type="submit"
					class="px-3 py-2 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 transition"
				>
					{$i18n.t('Open')}
				</button>
			</form>
		</details>
	</div>
</div>
