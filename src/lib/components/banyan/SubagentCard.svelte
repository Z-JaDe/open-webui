<!--
	banyan 渲染组件 4/5：SubagentCard（统一设计 §6.2 / §8 G2）

	事件 schema → 渲染契约：
	  输入 BanyanSubagentEvent 列表（按 subagent_id upsert：同一子代理原地更新）：
	    { type:'subagent', subagent_id, role?, title?, latest_action?,
	      status:'running'|'done'|'failed'|'stopped', session_id?, started_at?, ended_at?, ts? }
	  渲染：子代理卡。running 时 latest_action 做换词动画（新词淡入）；
	  显示角色徽标 + 耗时（running 实时跳动）+ 子会话入口（session_id → 引擎子会话）+ 停止按钮。

	mock：`<SubagentCard mock />` 渲染内置样例子代理。
-->
<script lang="ts">
	import { getContext, createEventDispatcher, onDestroy } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { toast } from 'svelte-sonner';

	import { mockSubagentEvents } from './mock';
	import { formatDuration, type BanyanSubagentEvent } from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ stop: BanyanSubagentEvent }>();

	/** 按 subagent_id upsert 后的子代理事件列表（首现顺序） */
	export let events: BanyanSubagentEvent[] = [];
	/** story 开关：不接引擎，渲染内置样例 */
	export let mock = false;

	$: sourceEvents = mock ? mockSubagentEvents : events;

	$: cards = (() => {
		const order: string[] = [];
		const byId: Record<string, BanyanSubagentEvent> = {};
		for (const event of sourceEvents) {
			if (!byId[event.subagent_id]) order.push(event.subagent_id);
			byId[event.subagent_id] = { ...byId[event.subagent_id], ...event };
		}
		return order.map((id) => byId[id]);
	})();

	// running 卡的耗时每秒刷新
	let nowTick = Date.now();
	const timer = setInterval(() => (nowTick = Date.now()), 1000);
	onDestroy(() => clearInterval(timer));

	const roleClass = (role?: string): string => {
		switch (role) {
			case 'explorer':
				return 'bg-purple-500/10 text-purple-600 dark:text-purple-300 border-purple-500/20';
			case 'worker':
				return 'bg-blue-500/10 text-blue-600 dark:text-blue-300 border-blue-500/20';
			case 'regressor':
				return 'bg-amber-500/10 text-amber-600 dark:text-amber-300 border-amber-500/20';
			default:
				return 'bg-gray-500/10 text-gray-600 dark:text-gray-300 border-gray-500/20';
		}
	};

	const statusDotClass = (status: BanyanSubagentEvent['status']): string => {
		switch (status) {
			case 'running':
				return 'bg-blue-500 animate-pulse';
			case 'done':
				return 'bg-green-500';
			case 'failed':
				return 'bg-red-500';
			default:
				return 'bg-gray-400';
		}
	};

	const stopHandler = (card: BanyanSubagentEvent) => {
		dispatch('stop', card);
		if (!mock) {
			// 停止指令经引擎 API 下发；这里仅提示，正本状态以引擎回流为准
			toast.info($i18n.t('Stop requested for {{name}}', { name: card.title ?? card.subagent_id }));
		}
	};
</script>

{#if cards.length > 0}
	<div class="w-full grid gap-2 md:grid-cols-2">
		{#each cards as card (card.subagent_id)}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-2.5 w-full min-w-0">
				<div class="flex items-center gap-2 min-w-0">
					<span class="shrink-0 size-2 rounded-full {statusDotClass(card.status)}"></span>
					<div class="min-w-0 flex-1 truncate text-xs font-medium text-gray-700 dark:text-gray-200">
						{card.title ?? card.subagent_id}
					</div>
					{#if card.role}
						<span class="shrink-0 text-[10px] px-1.5 py-px rounded-full border {roleClass(card.role)}">
							{card.role}
						</span>
					{/if}
					<span class="shrink-0 text-[10px] text-gray-400 dark:text-gray-500 tabular-nums">
						{formatDuration(card.started_at, card.status === 'running' ? nowTick : card.ended_at)}
					</span>
				</div>

				{#if card.status === 'running' && card.latest_action}
					{#key card.latest_action}
						<div class="mt-1 text-[11px] text-gray-500 dark:text-gray-400 truncate animate-in fade-in duration-300">
							{card.latest_action}
						</div>
					{/key}
				{:else if card.latest_action}
					<div class="mt-1 text-[11px] text-gray-400 dark:text-gray-500 truncate">
						{card.latest_action}
					</div>
				{/if}

				<div class="mt-1.5 flex items-center gap-2">
					{#if card.session_id}
						<a
							class="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
							href="/audit?session_id={encodeURIComponent(card.session_id)}"
						>
							{$i18n.t('Open subagent session')}
						</a>
					{/if}
					{#if card.status === 'running'}
						<button
							type="button"
							class="ml-auto text-[11px] px-2 py-0.5 rounded-md border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
							on:click={() => stopHandler(card)}
						>
							{$i18n.t('Stop')}
						</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>
{/if}
