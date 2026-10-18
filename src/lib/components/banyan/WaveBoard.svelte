<!--
	banyan 渲染组件 2/5：WaveBoard（统一设计 §6.2 / §8 G2）

	事件 schema → 渲染契约：
	  输入 BanyanWaveUpdateEvent 列表（按流式顺序，同一 plan_id）：
	    { type:'wave_update', plan_id, wave:number,
	      tasks:[{task_id, title?, status:'pending'|'running'|'done'|'failed'|'skipped'|'blocked', deps?, detail?}] }
	  渲染：波次×任务实时进度格。
	  归并规则（upsert 不刷屏）：tasks 按 task_id 合并，后到覆盖先到的同键字段；
	  状态色：pending 灰 / running 蓝闪 / done 绿 / failed 红 / skipped 灰虚 / blocked 橙红（依赖失败传导，见 types.propagateBlocked）。
	  可选 plan 事件（BanyanPlanEvent）补齐波次标题与“规划了但未开始”的任务。
	  点击任务格触发 select 事件（全屏路由的任务检查器用）。

	mock：`<WaveBoard mock />` 渲染内置样例波次流。
-->
<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { mockPlanEvent, mockWaveUpdateEvents } from './mock';
	import {
		BANYAN_TASK_STATUS_LABEL,
		formatClock,
		mergeWaveTasks,
		propagateBlocked,
		type BanyanPlanEvent,
		type BanyanTaskStatus,
		type BanyanWaveUpdateEvent
	} from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ select: { task_id: string; status: BanyanTaskStatus; detail?: string; deps?: string[]; title?: string } }>();

	/** 该 plan_id 下按流式顺序累积的全部 wave_update 事件 */
	export let events: BanyanWaveUpdateEvent[] = [];
	/** 可选 plan 事件：补齐波次标题与未开始任务 */
	export let plan: BanyanPlanEvent | null = null;
	/** story 开关：不接引擎，渲染内置样例 */
	export let mock = false;

	type TaskCell = BanyanWaveUpdateEvent['tasks'][number] & { updated_at?: number };

	$: sourceEvents = mock ? mockWaveUpdateEvents : events;
	$: sourcePlan = mock ? mockPlanEvent : plan;

	// wave_update 归并：wave → (task_id → cell)，后到 upsert，失败沿依赖标红
	$: board = (() => {
		const waves: Record<number, Record<string, TaskCell>> = {};
		for (const event of sourceEvents) {
			const index = event.wave ?? 0;
			waves[index] = mergeWaveTasks(waves[index] ?? {}, event.tasks ?? []);
			for (const [taskId, cell] of Object.entries(waves[index])) {
				waves[index][taskId] = { ...cell, updated_at: event.ts };
			}
		}
		// plan 里规划了但还没收到 update 的任务，补 pending 格
		if (sourcePlan) {
			for (const wave of sourcePlan.waves ?? []) {
				waves[wave.index] = waves[wave.index] ?? {};
				for (const task of wave.tasks ?? []) {
					if (!waves[wave.index][task.task_id]) {
						waves[wave.index][task.task_id] = {
							task_id: task.task_id,
							title: task.title,
							status: 'pending',
							deps: task.deps
						};
					}
				}
			}
		}
		for (const index of Object.keys(waves)) {
			waves[Number(index)] = propagateBlocked(waves[Number(index)]);
		}
		return waves;
	})();

	$: waveIndexes = Object.keys(board)
		.map(Number)
		.sort((a, b) => a - b);

	$: counts = (() => {
		const tally: Record<BanyanTaskStatus, number> = {
			pending: 0,
			running: 0,
			done: 0,
			failed: 0,
			skipped: 0,
			blocked: 0
		};
		for (const index of waveIndexes) {
			for (const cell of Object.values(board[index])) tally[cell.status] += 1;
		}
		return tally;
	})();

	const statusCellClass = (status: BanyanTaskStatus): string => {
		switch (status) {
			case 'done':
				return 'bg-green-500/15 border-green-500/40 text-green-700 dark:text-green-300';
			case 'running':
				return 'bg-blue-500/15 border-blue-500/40 text-blue-700 dark:text-blue-300 animate-pulse';
			case 'failed':
				return 'bg-red-500/15 border-red-500/50 text-red-700 dark:text-red-300';
			case 'blocked':
				return 'bg-orange-500/15 border-orange-500/40 text-orange-700 dark:text-orange-300';
			case 'skipped':
				return 'bg-gray-500/5 border-dashed border-gray-400/40 text-gray-500 dark:text-gray-400';
			default:
				return 'bg-black/[0.03] dark:bg-white/[0.05] border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400';
		}
	};
</script>

<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 w-full space-y-2">
	<div class="flex items-center justify-between gap-2 flex-wrap">
		<div class="text-sm font-medium text-black dark:text-white">
			波次看板
			{#if sourcePlan?.title}
				<span class="text-gray-400 dark:text-gray-500 font-normal">· {sourcePlan.title}</span>
			{/if}
		</div>
		<div class="flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400">
			<span>完成 {counts.done}</span>
			<span>执行中 {counts.running}</span>
			<span>排队 {counts.pending}</span>
			{#if counts.failed + counts.blocked > 0}
				<span class="text-red-600 dark:text-red-400">失败/受阻 {counts.failed + counts.blocked}</span>
			{/if}
		</div>
	</div>

	<div class="space-y-1.5 overflow-x-auto">
		{#each waveIndexes as waveIndex (waveIndex)}
			<div class="flex items-stretch gap-1.5 min-w-max">
				<div class="shrink-0 w-9 flex items-center justify-center rounded-md bg-black/[0.05] dark:bg-white/[0.08] text-[11px] font-medium text-gray-600 dark:text-gray-300">
					W{waveIndex}
				</div>
				<div class="flex gap-1.5 flex-wrap">
					{#each Object.values(board[waveIndex]) as cell (cell.task_id)}
						<button
							type="button"
							class="max-w-56 text-left rounded-lg border px-2 py-1 transition hover:brightness-95 {statusCellClass(cell.status)}"
							title={cell.detail ?? cell.title ?? cell.task_id}
							on:click={() =>
								dispatch('select', {
									task_id: cell.task_id,
									status: cell.status,
									detail: cell.detail,
									deps: cell.deps,
									title: cell.title
								})}
						>
							<div class="text-[11px] font-medium truncate">{cell.title ?? cell.task_id}</div>
							<div class="text-[10px] opacity-70 truncate">
								{$i18n.t(BANYAN_TASK_STATUS_LABEL[cell.status])}
								{#if cell.detail}
									· {cell.detail}
								{/if}
								{#if cell.updated_at}
									· {formatClock(cell.updated_at)}
								{/if}
							</div>
						</button>
					{/each}
				</div>
			</div>
			{:else}
				<div class="text-xs text-gray-400 dark:text-gray-500 py-2">
					暂无波次更新
				</div>
			{/each}
	</div>
</div>
