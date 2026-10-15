<script lang="ts">
	// /tree/[chatId] — 会话树视图：节点=轮（user→assistant），只读投影
	// （钩点③，统一设计 §6.1 / §8 G3；§6.3 会话树）
	// 数据源：GET /banyan/api/chats/:chatId/tree
	// （RF-Z 死按钮摘除：switch/rerun 引擎无对端端点，实测落 404——诚实 UI
	// 原则，摘按钮保留只读树；分支切换经消息流 TreeSwitcher 恢复对端后再上。）
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import { getBanyanTree, type BanyanTreeSnapshot } from '$lib/apis/banyan';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let error: string | null = null;
	let snapshot: BanyanTreeSnapshot | null = null;

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	$: banyanLayout.setHeader?.({
		itemName: `${$i18n.t('Tree')} · ${$page.params.chatId}`
	});

	const mockSnapshot: BanyanTreeSnapshot = {
		chat_id: 'chat-mock-77',
		active_path: ['r1', 'r2a', 'r3a'],
		nodes: [
			{ id: 'r1', round: 1, label: '轮 1 · 梳理调度器现状', parent_id: null, children: ['r2a', 'r2b'], active: true, status: 'done', summary: '产出依赖图与基线报告' },
			{ id: 'r2a', round: 2, label: '轮 2 · 波次模型方案', parent_id: 'r1', children: ['r3a'], active: true, status: 'done', summary: '方案获批，波次执行中' },
			{ id: 'r2b', round: 2, label: '轮 2 · 保守并行方案', parent_id: 'r1', children: [], active: false, status: 'abandoned', summary: '已驳回' },
			{ id: 'r3a', round: 3, label: '轮 3 · 波次收口与断言', parent_id: 'r2a', children: [], active: true, status: 'running', summary: 'W2 收口失败待分流' }
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
		snapshot = await getBanyanTree($page.params.chatId).catch((e) => {
			error = `${e}`;
			toast.error(`${$i18n.t('Failed to load tree')}: ${e}`);
			return null;
		});
		loaded = true;
	};

	$: nodes = snapshot?.nodes ?? [];
	$: nodesById = Object.fromEntries(nodes.map((node) => [node.id, node]));
	$: roots = nodes.filter((node) => !node.parent_id || !nodesById[node.parent_id]);

	// 父链深度（防御环：上限 64）
	const nodeDepth = (node: (typeof nodes)[number]): number => {
		let depth = 0;
		let cursor = node;
		const guard = new Set<string>();
		while (cursor?.parent_id && nodesById[cursor.parent_id] && !guard.has(cursor.id) && depth < 64) {
			guard.add(cursor.id);
			cursor = nodesById[cursor.parent_id];
			depth += 1;
		}
		return depth;
	};

	const statusClass = (status?: string): string => {
		switch (status) {
			case 'done':
				return 'border-green-500/40 bg-green-500/5';
			case 'running':
				return 'border-blue-500/40 bg-blue-500/5';
			case 'failed':
				return 'border-red-500/40 bg-red-500/5';
			case 'abandoned':
				return 'border-dashed border-gray-300 dark:border-gray-700 opacity-60';
			default:
				return 'border-gray-200 dark:border-gray-700';
		}
	};

	onMount(load);
</script>

<svelte:head><title>{$i18n.t('Tree')} · banyan</title></svelte:head>

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3">
	{#if error}
		<div class="mb-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400">
			{$i18n.t('Engine unreachable via /banyan/api — start the engine or append ?mock=1 to preview with built-in sample data.')}
			<br />
			{error}
		</div>
	{/if}

	{#if roots.length}
		<!-- 平铺渲染：按父链深度缩进 -->
		<div class="space-y-1.5">
			{#each nodes as node (node.id)}
				{@const depth = nodeDepth(node)}
				<div class="flex items-center gap-2" style="margin-left: {depth * 24}px">
					<div class="flex-1 min-w-0 rounded-xl border p-2.5 {statusClass(node.status)} {node.active ? 'ring-1 ring-black/10 dark:ring-white/20' : ''}">
						<div class="flex items-center gap-2 flex-wrap">
							<span class="text-[11px] font-medium text-gray-500 dark:text-gray-400">R{node.round}</span>
							<span class="text-xs text-gray-700 dark:text-gray-200 truncate">{node.label}</span>
							{#if node.active}
								<span class="text-[10px] px-1.5 py-px rounded-full bg-black text-white dark:bg-white dark:text-black">
									{$i18n.t('Active')}
								</span>
							{/if}
							{#if node.status}
								<span class="text-[10px] text-gray-400">{node.status}</span>
							{/if}
						</div>
						{#if node.summary}
							<div class="mt-1 text-[11px] text-gray-500 dark:text-gray-400 truncate">{node.summary}</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="text-xs text-gray-400 dark:text-gray-500">
			{loaded ? $i18n.t('No tree nodes for this chat') : $i18n.t('Loading')}…
		</div>
	{/if}
</div>
