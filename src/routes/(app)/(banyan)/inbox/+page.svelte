<script lang="ts">
	// /inbox — 管家信箱（v3 W2，钩点③配套页；V-4/V-5/V-10）
	// 三分类 tab 按 category 过滤（decision=待裁决 / done=完成 / notice=通知），
	// kind→category 机械映射在引擎侧，前端不自解释。
	// 数据源：GET /banyan/api/inbox、POST /banyan/api/inbox/:id/{read,archive,resolve}（代理桥 → 引擎）。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。徽标不在本页（Sidebar 钩点③负责）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import {
		getBanyanInbox,
		resolveBanyanInbox,
		readBanyanInbox,
		archiveBanyanInbox,
		type BanyanInboxItem,
		type BanyanInboxCategory,
		type BanyanInboxUnread
	} from '$lib/apis/banyan';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let items: BanyanInboxItem[] = [];
	let unread: BanyanInboxUnread = { decision: 0, done: 0, notice: 0 };
	let error: string | null = null;
	let activeTab: BanyanInboxCategory = 'decision';
	let actingId: string | null = null;

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: $i18n.t('Inbox') });

	const TABS: { id: BanyanInboxCategory; label: string }[] = [
		{ id: 'decision', label: 'Pending decisions' },
		{ id: 'done', label: 'Completed' },
		{ id: 'notice', label: 'Notices' }
	];

	// 各 tab 拉取的状态集(引擎 status 逗号多值逐个拉取;done/notice 需含已读与已裁决项;
	// F2/D3:decision 并拉 resolved——处置不是消失,是换视图,"已处置"组在本页可查)
	const TAB_STATUSES: Record<BanyanInboxCategory, string[]> = {
		decision: ['open', 'read', 'resolved'],
		done: ['open', 'read', 'resolved'],
		notice: ['open', 'read']
	};

	const isMock = () => new URLSearchParams(window.location.search).has('mock');

	const mockItems: BanyanInboxItem[] = [
		{
			id: 'msg_mock0001',
			kind: 'blocked_escalation',
			category: 'decision',
			title: '依赖缺失：w2.t1 需要 bge 模型文件',
			body: '波次 2 的任务 t1 依赖 RAG 嵌入模型目录 /tmp/banyan-home/models/bge-small-zh-v1.5，当前不存在。监工建议开子任务先行下载（来源 supervisor._discover_dependency 规则覆盖）。',
			push: true,
			status: 'open',
			options: ['开子任务下载', '跳过该任务', '终止方案'],
			plan_id: 'plan-mock-001',
			task_id: 't-201',
			created_at: Date.now() - 1000 * 600
		},
		{
			id: 'msg_mock0002',
			kind: 'delivery_signoff',
			category: 'decision',
			title: '交付签收：知识管线收口',
			body: '方案 plan-mock-001 全部登记簿断言 pass，等待人工签收后归档。',
			push: true,
			status: 'open',
			options: ['签收', '退回'],
			plan_id: 'plan-mock-001',
			created_at: Date.now() - 1000 * 300
		},
		{
			id: 'msg_mock0003',
			kind: 'plan_completed',
			category: 'done',
			title: '方案完成：调度器波次划分重构',
			body: 'w1/w2 全部任务 done，登记簿 6/6 green。',
			push: false,
			status: 'open',
			options: [],
			plan_id: 'plan-mock-001',
			created_at: Date.now() - 1000 * 120
		},
		{
			id: 'msg_mock0004',
			kind: 'notice',
			category: 'notice',
			title: '日历提醒：15:00 引擎例检',
			body: '事件 cal_mock0001 到达提醒时间（提前 10 分钟）。',
			push: false,
			status: 'open',
			options: [],
			created_at: Date.now() - 1000 * 60
		},
		{
			id: 'msg_mock0005',
			kind: 'blocked_escalation',
			category: 'decision',
			title: '攻击门拦截：高危方案（已豁免）',
			body: '攻击面板拦下整契约重跑方案；人已批准豁免重跑，本卡转入已处置可查。',
			push: true,
			status: 'resolved',
			options: [],
			resolution: { decision: 'approve', by: 'human', ts: Date.now() - 1000 * 100 },
			plan_id: 'plan-mock-001',
			created_at: Date.now() - 1000 * 900
		}
	];

	// F2/D3:decision tab 分两组渲染——待处置(open/read,可批准/驳回)在上、
	// 已处置(resolved,只读+resolution 摘要+归档)在下;done/notice tab 不分组。
	$: pendingItems =
		activeTab === 'decision'
			? items.filter((i) => i.status === 'open' || i.status === 'read')
			: items;
	$: resolvedItems =
		activeTab === 'decision' ? items.filter((i) => i.status === 'resolved') : [];

	const load = async () => {
		error = null;
		if (isMock()) {
			items = mockItems.filter((m) => m.category === activeTab);
			unread = { decision: 1, done: 1, notice: 1 };
			loaded = true;
			return;
		}
		try {
			const snapshots = await Promise.all(
				TAB_STATUSES[activeTab].map((status) =>
					getBanyanInbox({ category: activeTab, status, limit: 50 })
				)
			);
			const byId = new Map<string, BanyanInboxItem>();
			for (const snap of snapshots) {
				for (const item of snap.items) byId.set(item.id, item);
			}
			items = [...byId.values()].sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
			// unread 计数与 tab 无关（引擎全量给出），任取一份
			unread = snapshots[0]?.unread ?? { decision: 0, done: 0, notice: 0 };
		} catch (e) {
			error = `${e}`;
			items = [];
			toast.error(`${$i18n.t('Failed to load inbox')}: ${e}`);
		}
		loaded = true;
	};

	const switchTab = async (tab: BanyanInboxCategory) => {
		activeTab = tab;
		await load();
	};

	const refresh = () => load();

	const resolve = async (item: BanyanInboxItem, decision: 'approve' | 'reject') => {
		actingId = item.id;
		try {
			if (!isMock()) {
				await resolveBanyanInbox(item.id, decision);
			} else {
				item.status = 'resolved';
			}
			toast.success(decision === 'approve' ? $i18n.t('Approved') : $i18n.t('Rejected'));
			await refresh(); // 处置后刷新列表（V-5：resolve 按 ref_kind 路由后项离开 open 集）
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			actingId = null;
		}
	};

	const markRead = async (item: BanyanInboxItem) => {
		actingId = item.id;
		try {
			if (!isMock()) {
				await readBanyanInbox(item.id);
			} else {
				item.status = 'read';
			}
			await refresh();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			actingId = null;
		}
	};

	const archive = async (item: BanyanInboxItem) => {
		actingId = item.id;
		try {
			if (!isMock()) {
				await archiveBanyanInbox(item.id);
			} else {
				item.status = 'archived';
			}
			toast.success($i18n.t('Archived'));
			await refresh();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			actingId = null;
		}
	};

	const KIND_LABELS: Record<string, string> = {
		blocked_escalation: 'Blocked escalation',
		principle_conflict: 'Principle conflict',
		delivery_signoff: 'Delivery signoff',
		plan_completed: 'Plan completed',
		notice: 'Notice'
	};

	const fmtTime = (ms?: number) => (ms ? new Date(ms).toLocaleString() : '');

	onMount(load);
</script>

<svelte:head><title>{$i18n.t('Inbox')} · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3 space-y-5">
	{#if error}
		<div
			class="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400"
		>
			{$i18n.t('Engine unreachable via /banyan/api — start the engine or append ?mock=1 to preview with built-in sample data.')}
			<br />
			{error}
		</div>
	{/if}

	<!-- 三分类 tab（category 过滤；徽标=引擎 unread 计数） -->
	<div class="flex items-center gap-1 flex-wrap">
		{#each TABS as tab (tab.id)}
			<button
				type="button"
				class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition {activeTab ===
				tab.id
					? 'bg-black/[0.05] dark:bg-white/[0.08] text-black dark:text-white'
					: 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900'}"
				on:click={() => switchTab(tab.id)}
			>
				{$i18n.t(tab.label)}
				{#if unread[tab.id] > 0}
					<span
						class="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full text-[10px] font-semibold bg-blue-500 text-white"
					>
						{unread[tab.id]}
					</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- F2/D3:decision tab 两组(待处置在上/已处置在下);done/notice 单列表不变 -->
	<div class="space-y-2">
		{#if activeTab === 'decision' && pendingItems.length}
			<div class="text-xs font-semibold text-gray-500 dark:text-gray-400">
				{$i18n.t('Pending')} · {pendingItems.length}
			</div>
		{/if}
		{#each pendingItems as item (item.id)}
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 space-y-2"
			>
				<div class="flex items-start justify-between gap-2">
					<div class="min-w-0">
						<div class="flex items-center gap-2 flex-wrap">
							<span
								class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium {item.category ===
								'decision'
									? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
									: item.category === 'done'
										? 'bg-green-500/10 text-green-600 dark:text-green-400'
										: 'bg-blue-500/10 text-blue-600 dark:text-blue-400'}"
							>
								{$i18n.t(KIND_LABELS[item.kind] ?? item.kind)}
							</span>
							{#if item.status === 'open'}
								<span class="shrink-0 text-[10px] font-semibold text-blue-500">●</span>
							{/if}
							{#if item.escalated}
								<span
									class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/10 text-red-600 dark:text-red-400"
								>
									{$i18n.t('Escalated')}
								</span>
							{/if}
							<div class="text-sm font-medium text-black dark:text-white">{item.title}</div>
						</div>
					</div>
					<span class="shrink-0 text-[11px] text-gray-400">{fmtTime(item.created_at)}</span>
				</div>

				{#if item.body}
					<div class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
						{item.body}
					</div>
				{/if}

				{#if item.options.length}
					<div class="flex items-center gap-1.5 flex-wrap">
						{#each item.options as option (option)}
							<span
								class="px-1.5 py-0.5 rounded border border-gray-200 dark:border-gray-700 text-[11px] text-gray-500 dark:text-gray-400"
							>
								{option}
							</span>
						{/each}
					</div>
				{/if}

				<div class="flex items-center justify-between gap-2 flex-wrap">
					<div class="text-[11px] text-gray-400 dark:text-gray-500 truncate">
						{[item.ref_kind ? `${item.ref_kind}:${item.ref_id}` : '', item.plan_id, item.task_id]
							.filter(Boolean)
							.join(' · ')}
					</div>
						<div class="flex items-center gap-2">
							{#if item.category === 'decision' && (item.status === 'open' || item.status === 'read')}
							<button
								type="button"
								class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
								disabled={actingId === item.id}
								on:click={() => resolve(item, 'approve')}
							>
								<Check className="size-3.5" strokeWidth="2" />
								{$i18n.t('Approve expansion')}
							</button>
							<button
								type="button"
								class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
								disabled={actingId === item.id}
								on:click={() => resolve(item, 'reject')}
							>
								<XMark className="size-3.5" strokeWidth="2" />
								{$i18n.t('Reject')}
							</button>
						{/if}
						{#if item.status === 'open'}
							<button
								type="button"
								class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
								disabled={actingId === item.id}
								on:click={() => markRead(item)}
							>
								{$i18n.t('Mark as read')}
							</button>
						{/if}
						{#if item.status !== 'archived'}
							<button
								type="button"
								class="px-3 py-1.5 text-xs rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
								disabled={actingId === item.id}
								on:click={() => archive(item)}
							>
								{$i18n.t('Archive')}
							</button>
						{/if}
					</div>
				</div>
			</div>
		{:else}
			{#if !(activeTab === 'decision' && resolvedItems.length)}
				<div class="text-xs text-gray-400 dark:text-gray-500">
					{loaded ? $i18n.t('Nothing here') : `${$i18n.t('Loading')}…`}
				</div>
			{/if}
		{/each}

		<!-- 已处置组(F2/D3):resolved 不再消失——只读+resolution 摘要+归档 -->
		{#if activeTab === 'decision' && resolvedItems.length}
			<div class="pt-3 text-xs font-semibold text-gray-500 dark:text-gray-400">
				{$i18n.t('Resolved')} · {resolvedItems.length}
			</div>
			{#each resolvedItems as item (item.id)}
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50/60 dark:bg-gray-900/30 p-3 space-y-2"
				>
					<div class="flex items-start justify-between gap-2">
						<div class="flex items-center gap-2 flex-wrap min-w-0">
							<span
								class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400"
							>
								{$i18n.t(KIND_LABELS[item.kind] ?? item.kind)}
							</span>
							<span
								class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/10 text-green-600 dark:text-green-400"
							>
								{$i18n.t('Resolved')}
							</span>
							<div class="text-sm font-medium text-gray-600 dark:text-gray-300 truncate">
								{item.title}
							</div>
						</div>
						<span class="shrink-0 text-[11px] text-gray-400">{fmtTime(item.created_at)}</span>
					</div>

					{#if item.body}
						<div
							class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed whitespace-pre-wrap"
						>
							{item.body}
						</div>
					{/if}

					{#if item.resolution}
						<div
							class="text-[11px] text-gray-500 dark:text-gray-400 rounded-lg bg-black/[0.03] dark:bg-white/[0.04] px-2 py-1.5"
						>
							{$i18n.t('Decision')}: {item.resolution.decision ?? '—'}{item.resolution.note
								? ` · ${item.resolution.note}`
								: ''}
						</div>
					{/if}

					<div class="flex items-center justify-between gap-2 flex-wrap">
						<div class="text-[11px] text-gray-400 dark:text-gray-500 truncate">
							{[item.ref_kind ? `${item.ref_kind}:${item.ref_id}` : '', item.plan_id, item.task_id]
								.filter(Boolean)
								.join(' · ')}
						</div>
						{#if item.status !== 'archived'}
							<button
								type="button"
								class="px-3 py-1.5 text-xs rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
								disabled={actingId === item.id}
								on:click={() => archive(item)}
							>
								{$i18n.t('Archive')}
							</button>
						{/if}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
