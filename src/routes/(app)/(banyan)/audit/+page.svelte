<script lang="ts">
	// /audit — K1 事件正本浏览（钩点③，统一设计 §6.1 / §8 G3）
	// 数据源：GET /banyan/api/audit?chat_id=&type=&limit=（代理桥 → 引擎）。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import { getBanyanAuditEvents, type BanyanAuditEvent } from '$lib/apis/banyan';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let items: BanyanAuditEvent[] = [];
	let error: string | null = null;
	let chatIdFilter = '';
	let typeFilter = '';

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: $i18n.t('Audit') });

	const mockItems: BanyanAuditEvent[] = [
		{ id: 'e-0001', chat_id: 'chat-mock-77', type: 'plan.proposed', ts: Date.now() - 1000 * 720, payload: { plan_id: 'plan-mock-001', waves: 3 } },
		{ id: 'e-0002', chat_id: 'chat-mock-77', type: 'plan.resolved', ts: Date.now() - 1000 * 700, payload: { decision: 'approved' } },
		{ id: 'e-0003', chat_id: 'chat-mock-77', type: 'wave.started', ts: Date.now() - 1000 * 600, payload: { wave: 1, tasks: 2 } },
		{ id: 'e-0004', chat_id: 'chat-mock-77', type: 'tool.invoked', ts: Date.now() - 1000 * 540, payload: { name: 'read', target: 'backend/scheduler.py' } },
		{ id: 'e-0005', chat_id: 'chat-mock-77', type: 'subagent.spawned', ts: Date.now() - 1000 * 500, payload: { subagent_id: 'sa-worker-1', role: 'worker' } },
		{ id: 'e-0006', chat_id: 'chat-mock-77', type: 'task.failed', ts: Date.now() - 1000 * 300, payload: { task_id: 't-201', error: 'merge conflict in scheduler.py' } },
		{ id: 'e-0007', chat_id: 'chat-mock-77', type: 'assertion.red', ts: Date.now() - 1000 * 60, payload: { assertion_id: 'asr-003', missing: 'seq 4702..4707' } }
	];

	const load = async () => {
		error = null;
		const mock = new URLSearchParams(window.location.search).has('mock');
		if (mock) {
			items = mockItems;
			loaded = true;
			return;
		}
		items = await getBanyanAuditEvents({
			chat_id: chatIdFilter || undefined,
			type: typeFilter || undefined,
			limit: 300
		}).catch((e) => {
			error = `${e}`;
			toast.error(`${$i18n.t('Failed to load audit events')}: ${e}`);
			return [];
		});
		loaded = true;
	};

	// 客户端二次过滤（mock 或引擎不支持 query 时仍可用）
	$: filtered = items.filter(
		(event) =>
			(!chatIdFilter || (event.chat_id ?? '').includes(chatIdFilter)) &&
			(!typeFilter || event.type.toLowerCase().includes(typeFilter.toLowerCase()))
	);

	const payloadPreview = (payload?: Record<string, any>): string => {
		if (!payload) return '';
		try {
			return JSON.stringify(payload);
		} catch {
			return String(payload);
		}
	};

	const typeClass = (type: string): string => {
		if (type.includes('fail') || type.includes('red')) {
			return 'bg-red-500/10 text-red-600 dark:text-red-400';
		}
		if (type.includes('wave') || type.includes('task')) {
			return 'bg-blue-500/10 text-blue-600 dark:text-blue-400';
		}
		if (type.includes('plan')) {
			return 'bg-amber-500/10 text-amber-600 dark:text-amber-400';
		}
		return 'bg-gray-500/10 text-gray-500 dark:text-gray-400';
	};

	onMount(load);
</script>

<svelte:head><title>{$i18n.t('Audit')} · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3">
	<div class="flex items-center gap-2 flex-wrap mb-3">
		<input
			class="w-56 text-xs rounded-lg px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850 outline-none"
			placeholder={$i18n.t('Filter by chat id')}
			bind:value={chatIdFilter}
		/>
		<input
			class="w-56 text-xs rounded-lg px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850 outline-none"
			placeholder={$i18n.t('Filter by event type')}
			bind:value={typeFilter}
		/>
		<button
			type="button"
			class="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
			on:click={load}
		>
			{$i18n.t('Refresh')}
		</button>
	</div>

	{#if error}
		<div class="mb-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400">
			{$i18n.t('Engine unreachable via /banyan/api — start the engine or append ?mock=1 to preview with built-in sample data.')}
			<br />
			{error}
		</div>
	{/if}

	<div class="rounded-xl border border-gray-100 dark:border-gray-850 divide-y divide-gray-100 dark:divide-gray-850">
		{#each filtered as event (event.id)}
			<div class="px-3 py-2 flex items-start gap-3 text-xs hover:bg-gray-50 dark:hover:bg-gray-900/40">
				<span class="shrink-0 tabular-nums text-gray-400 dark:text-gray-500 w-20">
					{new Date(event.ts).toLocaleTimeString()}
				</span>
				<span class="shrink-0 px-2 py-0.5 rounded-md font-mono text-[10px] {typeClass(event.type)}">
					{event.type}
				</span>
				<div class="min-w-0 flex-1">
					<div class="text-gray-500 dark:text-gray-400 font-mono truncate">{payloadPreview(event.payload)}</div>
					{#if event.chat_id}
						<div class="text-[10px] text-gray-400">
							<a class="hover:underline" href="/audit?chat_id={event.chat_id}">{event.chat_id}</a>
						</div>
					{/if}
				</div>
			</div>
		{:else}
			<div class="px-3 py-8 text-center text-xs text-gray-400 dark:text-gray-500">
				{loaded ? $i18n.t('No events match the filters') : $i18n.t('Loading')}…
			</div>
		{/each}
	</div>
</div>
