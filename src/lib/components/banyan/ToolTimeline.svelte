<!--
	banyan 渲染组件 3/5：ToolTimeline（统一设计 §6.2 / §8 G2）

	事件 schema → 渲染契约：
	  输入 BanyanToolEvent 列表（按 call_id upsert：running → ok/error 原地更新，不新增行）：
	    { type:'tool', call_id, name, args_summary?, status:'running'|'ok'|'error',
	      output_summary?, started_at?, ended_at?, ts? }
	  渲染：工具时间线，默认折叠、只显示最近 3 行（含 running 行），可展开全量；
	  每行：状态点 + 名称 + 参数摘要 + 耗时/时间。

	mock：`<ToolTimeline mock />` 渲染内置样例工具流。
-->
<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	import { mockToolEvents } from './mock';
	import { formatClock, formatDuration, type BanyanToolEvent } from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');

	/** 按 call_id upsert 后的全量工具事件（按首现顺序） */
	export let events: BanyanToolEvent[] = [];
	/** story 开关：不接引擎，渲染内置样例 */
	export let mock = false;
	/** 折叠时保留的最近行数 */
	const COLLAPSED_COUNT = 3;

	$: sourceEvents = mock ? mockToolEvents : events;

	// call_id upsert：后到的同名 call 覆盖原行，保持首现行位次
	$: merged = (() => {
		const order: string[] = [];
		const byId: Record<string, BanyanToolEvent> = {};
		for (const event of sourceEvents) {
			if (!byId[event.call_id]) order.push(event.call_id);
			byId[event.call_id] = { ...byId[event.call_id], ...event };
		}
		return order.map((id) => byId[id]);
	})();

	let expanded = false;

	$: visible = expanded ? merged : merged.slice(-COLLAPSED_COUNT);
	$: hiddenCount = Math.max(0, merged.length - COLLAPSED_COUNT);

	const dotClass = (status: BanyanToolEvent['status']): string => {
		switch (status) {
			case 'ok':
				return 'bg-green-500';
			case 'error':
				return 'bg-red-500';
			default:
				return 'bg-blue-500 animate-pulse';
		}
	};
</script>

{#if merged.length > 0}
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-2.5 w-full">
		<button
			type="button"
			class="w-full flex items-center justify-between gap-2 text-left"
			on:click={() => (expanded = !expanded)}
		>
			<div class="text-xs font-medium text-gray-600 dark:text-gray-300">
				{$i18n.t('Tool Timeline')}
				<span class="text-gray-400 dark:text-gray-500 font-normal">· {merged.length}</span>
			</div>
			<ChevronDown className="size-3.5 text-gray-400 transition {expanded ? 'rotate-180' : ''}" strokeWidth="2" />
		</button>

		<div class="mt-1.5 space-y-1">
			{#if !expanded && hiddenCount > 0}
				<div class="text-[11px] text-gray-400 dark:text-gray-500">
					… {$i18n.t('{n} earlier calls hidden', { n: hiddenCount })}
				</div>
			{/if}
			{#each visible as call (call.call_id)}
				<div class="flex items-start gap-2 text-xs min-w-0">
					<span class="shrink-0 mt-1.5 size-1.5 rounded-full {dotClass(call.status)}"></span>
					<div class="min-w-0 flex-1 flex items-baseline gap-1.5 flex-wrap">
						<span class="font-medium text-gray-700 dark:text-gray-200">{call.name}</span>
						{#if call.args_summary}
							<span class="text-gray-500 dark:text-gray-400 truncate max-w-full">{call.args_summary}</span>
						{/if}
						{#if call.output_summary}
							<span class="text-gray-400 dark:text-gray-500 truncate">→ {call.output_summary}</span>
						{/if}
					</div>
					<span class="shrink-0 text-[10px] text-gray-400 dark:text-gray-500 tabular-nums">
						{#if call.started_at}
							{formatDuration(call.started_at, call.ended_at)}
						{/if}
						{formatClock(call.ended_at ?? call.started_at)}
					</span>
				</div>
			{/each}
		</div>
	</div>
{/if}
