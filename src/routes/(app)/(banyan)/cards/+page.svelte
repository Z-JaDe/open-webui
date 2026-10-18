<script lang="ts">
	// /cards — 语义卡审核：批准/驳回（钩点③，统一设计 §6.1 / §8 G3；K3 知识层）
	// 数据源：GET /banyan/api/cards、POST /banyan/api/cards/:id/resolve（代理桥 → 引擎）。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import { getBanyanCards, resolveBanyanCard, type BanyanCard } from '$lib/apis/banyan';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let items: BanyanCard[] = [];
	let error: string | null = null;
	let resolvingId: string | null = null;

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: '审卡' });

	const mockItems: BanyanCard[] = [
		{
			id: 'card-001',
			title: '调度器波次划分经验',
			content: '当任务依赖图呈分层结构时，按最长路径分层做波次划分，收口次数最少。',
			scope: 'orchestration.wave',
			weight: 3.2,
			status: 'pending',
			source: 'plan-mock-001 收口归因',
			created_at: Date.now() - 1000 * 3600 * 5
		},
		{
			id: 'card-002',
			title: 'worktree 共写风险',
			content: '同一文件被两个波次的任务同时改动时，merge queue 必须拒绝后者并触发依赖单据重排。',
			scope: 'isolation.merge_queue',
			weight: 1.8,
			status: 'pending',
			source: 'chat-mock-77 收口归因',
			created_at: Date.now() - 1000 * 3600 * 26
		},
		{
			id: 'card-003',
			title: '过时结论（待驳回）',
			content: '旧 scheduler 的轮询间隔 5s 最优——已被事件驱动调度取代。',
			scope: 'orchestration.scheduler',
			weight: 0.4,
			status: 'pending',
			source: 'K3 攻击发现',
			created_at: Date.now() - 1000 * 86400 * 40
		}
	];

	const load = async () => {
		error = null;
		const mock = new URLSearchParams(window.location.search).has('mock');
		if (mock) {
			items = mockItems;
			loaded = true;
			return;
		}
		items = await getBanyanCards().catch((e) => {
			error = `${e}`;
			toast.error(`审卡队列加载失败: ${e}`);
			return [];
		});
		loaded = true;
	};

	const resolve = async (card: BanyanCard, decision: 'approved' | 'rejected') => {
		resolvingId = card.id;
		try {
			if (!new URLSearchParams(window.location.search).has('mock')) {
				await resolveBanyanCard(card.id, decision);
			}
			card.status = decision;
			items = [...items]; // 触发 pending/settled 重算
			toast.success(decision === 'approved' ? '卡片已批准' : '卡片已驳回');
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			resolvingId = null;
		}
	};

	$: pending = items.filter((card) => card.status === 'pending');
	$: settled = items.filter((card) => card.status !== 'pending');

	onMount(load);
</script>

<svelte:head><title>审卡 · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3 space-y-6">
	{#if error}
		<div class="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400">
			经 /banyan/api 无法连通引擎——请先启动引擎，或追加 ?mock=1 用内置样例数据预览。
			<br />
			{error}
		</div>
	{/if}

	<section>
		<h2 class="text-sm font-medium text-black dark:text-white mb-2">
			待审
			<span class="text-gray-400">({pending.length})</span>
		</h2>
		<div class="grid gap-2 md:grid-cols-2">
			{#each pending as card (card.id)}
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 space-y-2">
					<div class="flex items-start justify-between gap-2">
						<div class="text-sm font-medium text-black dark:text-white">{card.title}</div>
						<span class="shrink-0 text-[11px] text-gray-400">w{card.weight?.toFixed(1) ?? '-'}</span>
					</div>
					<div class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">{card.content}</div>
					<div class="text-[11px] text-gray-400 dark:text-gray-500">
						{card.scope ?? '-'} · {card.source ?? '-'} ·
						{card.created_at ? new Date(card.created_at).toLocaleDateString() : ''}
					</div>
					<div class="flex items-center gap-2">
						<button
							type="button"
							class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
							disabled={resolvingId === card.id}
							on:click={() => resolve(card, 'approved')}
						>
							<Check className="size-3.5" strokeWidth="2" />
							批准
						</button>
						<button
							type="button"
							class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
							disabled={resolvingId === card.id}
							on:click={() => resolve(card, 'rejected')}
						>
							<XMark className="size-3.5" strokeWidth="2" />
							驳回
						</button>
					</div>
				</div>
			{:else}
				<div class="text-xs text-gray-400 dark:text-gray-500">
					{loaded ? '暂无待审卡片' : '加载中'}…
				</div>
			{/each}
		</div>
	</section>

	{#if settled.length}
		<section>
			<h2 class="text-sm font-medium text-black dark:text-white mb-2">已裁定</h2>
			<div class="space-y-1">
				{#each settled as card (card.id)}
					<div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
						<span class={card.status === 'approved' ? 'text-green-600 dark:text-green-400' : 'text-red-500'}>
							{card.status === 'approved' ? '✓' : '✕'}
						</span>
						<span class="text-gray-700 dark:text-gray-200">{card.title}</span>
						<span class="truncate">{card.scope ?? ''}</span>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</div>
