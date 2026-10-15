<script lang="ts">
	// /registry — 断言登记簿表（钩点③，统一设计 §6.1 / §8 G3；§4.3 回归元环）
	// 数据源：GET /banyan/api/registry（代理桥 → 引擎）。
	// RFF P1 增补：知识卡区块（GET /banyan/api/knowledge/cards，渲染卡名/权重/状态）
	// ——此前 /cards 页接的是审卡队列（engine /api/cards），知识卡真端点无页面消费。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import {
		getBanyanRegistry,
		getBanyanKnowledgeCards,
		type BanyanRegistryEntry,
		type BanyanKnowledgeCard
	} from '$lib/apis/banyan';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const banyanLayout: any = getContext('banyanLayout') ?? {};

	let loaded = false;
	let items: BanyanRegistryEntry[] = [];
	let kbCards: BanyanKnowledgeCard[] = [];
	let error: string | null = null;
	let kbError: string | null = null;
	let query = '';

	banyanLayout.setHeader?.({ itemName: $i18n.t('Registry') });

	const mockItems: BanyanRegistryEntry[] = [
		{
			id: 'asr-001',
			assertion: '波次收口后 K1 水位 == git 影子库 HEAD',
			scope: 'plan-mock-001',
			status: 'green',
			last_checked_at: Date.now() - 1000 * 300,
			last_result: '水位一致 (seq=4821)',
			hits: 12,
			created_at: Date.now() - 1000 * 86400 * 3
		},
		{
			id: 'asr-002',
			assertion: 'merge queue 无跨写 worktree（worktree 无共写）',
			scope: 'global',
			status: 'green',
			last_checked_at: Date.now() - 1000 * 900,
			last_result: '0 冲突',
			hits: 31,
			created_at: Date.now() - 1000 * 86400 * 9
		},
		{
			id: 'asr-003',
			assertion: 'Pi 会话→K1 镜像无缺帧（水位校验）',
			scope: 'chat-mock-77',
			status: 'red',
			last_checked_at: Date.now() - 1000 * 60,
			last_result: 'seq 4702..4707 缺失，待人工分流',
			hits: 4,
			created_at: Date.now() - 1000 * 86400
		},
		{
			id: 'asr-004',
			assertion: '回归零发现零打扰（四分流不误报）',
			scope: 'global',
			status: 'quarantined',
			last_checked_at: Date.now() - 1000 * 86400,
			last_result: '疑似噪音，隔离观察',
			hits: 2,
			created_at: Date.now() - 1000 * 86400 * 14
		}
	];

	const mockKnowledgeCards: BanyanKnowledgeCard[] = [
		{
			id: 'k-001',
			name: '调度器波次划分经验',
			kind: 'experience',
			scope: 'orchestration.wave',
			weight: 3.2,
			status: 'active',
			used: 12,
			wrong: 0,
			updated: Date.now() - 1000 * 3600 * 5
		},
		{
			id: 'k-002',
			name: 'worktree 共写风险',
			kind: 'experience',
			scope: 'isolation.merge_queue',
			weight: 1.8,
			status: 'corrected',
			used: 7,
			wrong: 2,
			updated: Date.now() - 1000 * 86400
		},
		{
			id: 'k-003',
			name: '旧轮询间隔结论(已证伪)',
			kind: 'experience',
			scope: 'orchestration.scheduler',
			weight: 0.2,
			status: 'superseded',
			used: 31,
			wrong: 9,
			updated: Date.now() - 1000 * 86400 * 40
		}
	];

	const load = async () => {
		error = null;
		kbError = null;
		const mock = new URLSearchParams(window.location.search).has('mock');
		if (mock) {
			items = mockItems;
			kbCards = mockKnowledgeCards;
			loaded = true;
			return;
		}
		// 登记簿与知识卡两路独立取数:一路失败不拖垮另一路
		const [reg, kb] = await Promise.allSettled([
			getBanyanRegistry(),
			getBanyanKnowledgeCards()
		]);
		if (reg.status === 'fulfilled') {
			items = reg.value;
		} else {
			error = `${reg.reason}`;
			toast.error(`${$i18n.t('Failed to load registry')}: ${reg.reason}`);
		}
		if (kb.status === 'fulfilled') {
			kbCards = kb.value.cards;
		} else {
			kbError = `${kb.reason}`;
		}
		loaded = true;
	};

	$: filtered = items.filter(
		(item) =>
			!query ||
			item.assertion.toLowerCase().includes(query.toLowerCase()) ||
			(item.scope ?? '').toLowerCase().includes(query.toLowerCase())
	);

	const statusClass = (status: BanyanRegistryEntry['status']): string => {
		switch (status) {
			case 'green':
				return 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20';
			case 'red':
				return 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20';
			case 'quarantined':
				return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
			default:
				return 'bg-gray-500/10 text-gray-500 dark:text-gray-400 border-gray-500/20';
		}
	};

	$: kbFiltered = kbCards.filter(
		(card) => !query || card.name.toLowerCase().includes(query.toLowerCase())
	);

	// 知识卡状态:active=生效 / corrected=已修正 / superseded=已替代 / dead=退役
	const KB_STATUS_LABEL: Record<string, string> = {
		active: 'Active',
		corrected: 'Corrected',
		superseded: 'Superseded',
		dead: 'Retired'
	};
	const kbStatusClass = (status: string): string => {
		switch (status) {
			case 'active':
				return 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20';
			case 'corrected':
				return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
			case 'superseded':
			case 'dead':
				return 'bg-gray-500/10 text-gray-500 dark:text-gray-400 border-gray-500/20';
			default:
				return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20';
		}
	};

	onMount(load);
</script>

<svelte:head><title>{$i18n.t('Registry')} · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3">
	<div class="flex items-center justify-between gap-2 flex-wrap mb-3">
		<div class="text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Assertion registry: no assertion, no ledger entry')}
		</div>
		<input
			class="w-64 text-xs rounded-lg px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850 outline-none"
			placeholder={$i18n.t('Search assertions')}
			bind:value={query}
		/>
	</div>

	{#if error}
		<div class="mb-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400">
			{$i18n.t('Engine unreachable via /banyan/api — start the engine or append ?mock=1 to preview with built-in sample data.')}
			<br />
			{error}
		</div>
	{/if}

	<div class="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-850">
		<table class="w-full text-xs min-w-[720px]">
			<thead class="bg-gray-50 dark:bg-gray-900/60 text-gray-500 dark:text-gray-400">
				<tr>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Status')}</th>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Assertion')}</th>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Scope')}</th>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Last Result')}</th>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Hits')}</th>
					<th class="text-left font-medium px-3 py-2">{$i18n.t('Last Checked')}</th>
				</tr>
			</thead>
			<tbody>
				{#each filtered as item (item.id)}
					<tr class="border-t border-gray-100 dark:border-gray-850 hover:bg-gray-50 dark:hover:bg-gray-900/40">
						<td class="px-3 py-2">
							<Tooltip content={item.status}>
								<span class="px-2 py-0.5 rounded-full border uppercase {statusClass(item.status)}">
									{item.status}
								</span>
							</Tooltip>
						</td>
						<td class="px-3 py-2 text-gray-700 dark:text-gray-200">
							{item.assertion}
							<div class="text-[10px] text-gray-400">{item.id}</div>
						</td>
						<td class="px-3 py-2 text-gray-500 dark:text-gray-400">{item.scope ?? '-'}</td>
						<td class="px-3 py-2 text-gray-500 dark:text-gray-400">{item.last_result ?? '-'}</td>
						<td class="px-3 py-2 text-gray-500 dark:text-gray-400 tabular-nums">{item.hits ?? 0}</td>
						<td class="px-3 py-2 text-gray-500 dark:text-gray-400">
							{item.last_checked_at ? new Date(item.last_checked_at).toLocaleString() : '-'}
						</td>
					</tr>
				{:else}
					<tr>
						<td colspan="6" class="px-3 py-8 text-center text-gray-400 dark:text-gray-500">
							{loaded ? $i18n.t('No assertions registered') : $i18n.t('Loading')}…
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<!-- 知识卡区块(RFF P1/F6 补页):引擎 GET /api/knowledge/cards → 卡名/权重/状态 -->
	<section class="mt-8">
		<h2 class="text-sm font-medium text-black dark:text-white mb-2">
			{$i18n.t('Knowledge cards')}
			<span class="text-gray-400">({kbFiltered.length})</span>
		</h2>
		{#if kbError}
			<div class="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-600 dark:text-amber-400">
				{$i18n.t('Knowledge cards unavailable')}
				<br />
				{kbError}
			</div>
		{/if}
		<div class="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-850">
			<table class="w-full text-xs min-w-[640px]">
				<thead class="bg-gray-50 dark:bg-gray-900/60 text-gray-500 dark:text-gray-400">
					<tr>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Card')}</th>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Weight')}</th>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Status')}</th>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Scope')}</th>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Used / Wrong')}</th>
						<th class="text-left font-medium px-3 py-2">{$i18n.t('Updated')}</th>
					</tr>
				</thead>
				<tbody>
					{#each kbFiltered as card (card.id)}
						<tr class="border-t border-gray-100 dark:border-gray-850 hover:bg-gray-50 dark:hover:bg-gray-900/40">
							<td class="px-3 py-2 text-gray-700 dark:text-gray-200">
								{card.name}
								<div class="text-[10px] text-gray-400">{card.kind ?? ''} · {card.id}</div>
							</td>
							<td class="px-3 py-2 text-gray-500 dark:text-gray-400 tabular-nums">
								{card.weight !== undefined ? card.weight.toFixed(2) : '-'}
							</td>
							<td class="px-3 py-2">
								<Tooltip content={card.status}>
									<span class="px-2 py-0.5 rounded-full border uppercase {kbStatusClass(card.status)}">
										{$i18n.t(KB_STATUS_LABEL[card.status] ?? card.status)}
									</span>
								</Tooltip>
							</td>
							<td class="px-3 py-2 text-gray-500 dark:text-gray-400">{card.scope ?? '-'}</td>
							<td class="px-3 py-2 text-gray-500 dark:text-gray-400 tabular-nums">
								{card.used ?? 0} / {card.wrong ?? 0}
							</td>
							<td class="px-3 py-2 text-gray-500 dark:text-gray-400">
								{card.updated ? new Date(card.updated).toLocaleString() : '-'}
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="6" class="px-3 py-8 text-center text-gray-400 dark:text-gray-500">
								{kbError ? $i18n.t('Knowledge cards unavailable') : loaded ? $i18n.t('No knowledge cards yet') : $i18n.t('Loading')}…
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
</div>
