<!--
	banyan 渲染协议聚合器（钩点②挂载件，统一设计 §6.1-§6.2 / §8 G1+G2）

	事件 schema → 渲染契约：
	  输入 message.banyanEvents: BanyanEvent[]（Chat.svelte 钩点①按流式顺序追加）。
	  五组件映射与归并：
	    branch      → 仅保留最新一份 → TreeSwitcher（消息块顶端）
	    plan        → 按 plan_id upsert → PlanCard
	    wave_update → 按 plan_id 聚合（task_id upsert）→ WaveBoard
	    tool        → 按 call_id upsert → ToolTimeline（默认折叠最近 3 行）
	    subagent    → 按 subagent_id upsert → SubagentCard
	  渲染顺序（正文上方）：TreeSwitcher → PlanCard → WaveBoard → ToolTimeline → SubagentCard。
-->
<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { toast } from 'svelte-sonner';

	import PlanCard from './PlanCard.svelte';
	import WaveBoard from './WaveBoard.svelte';
	import ToolTimeline from './ToolTimeline.svelte';
	import SubagentCard from './SubagentCard.svelte';
	import TreeSwitcher from './TreeSwitcher.svelte';
	import { mockMessageEvents } from './mock';
	import {
		stopBanyanSubagent,
		switchBanyanTreeNode
	} from '$lib/apis/banyan';
	import type {
		BanyanBranchEvent,
		BanyanEvent,
		BanyanPlanEvent,
		BanyanSubagentEvent,
		BanyanToolEvent,
		BanyanWaveUpdateEvent
	} from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let events: BanyanEvent[] = [];
	export let chatId = '';
	/** story 开关：不接引擎，渲染内置样例事件流 */
	export let mock = false;

	$: sourceEvents = mock ? mockMessageEvents : (events ?? []);

	// 分流 + upsert（保持首现顺序；后到覆盖同键）
	$: partition = (() => {
		let branch: BanyanBranchEvent | null = null;
		const plans: BanyanPlanEvent[] = [];
		const planOrder: string[] = [];
		const planById: Record<string, BanyanPlanEvent> = {};
		const waves: BanyanWaveUpdateEvent[] = [];
		const tools: BanyanToolEvent[] = [];
		const subagents: BanyanSubagentEvent[] = [];

		for (const event of sourceEvents) {
			switch (event?.type) {
				case 'branch':
					branch = event;
					break;
				case 'plan':
					if (!planById[event.plan_id]) {
						planOrder.push(event.plan_id);
						plans.push(event);
					} else {
						plans.splice(
							plans.findIndex((p) => p.plan_id === event.plan_id),
							1,
							event
						);
					}
					planById[event.plan_id] = event;
					break;
				case 'wave_update':
					waves.push(event);
					break;
				case 'tool':
					tools.push(event);
					break;
				case 'subagent':
					subagents.push(event);
					break;
			}
		}
		return { branch, plans, waves, tools, subagents };
	})();

	const branchSwitchHandler = async (id: string) => {
		if (mock || !chatId) return;
		try {
			await switchBanyanTreeNode(chatId, id);
			toast.success($i18n.t('Switched branch'));
		} catch (error) {
			toast.error(`${$i18n.t('Failed to switch branch')}: ${error}`);
		}
	};

	const subagentStopHandler = async (subagent: BanyanSubagentEvent) => {
		if (mock) return;
		try {
			await stopBanyanSubagent(subagent.subagent_id);
		} catch (error) {
			toast.error(`${$i18n.t('Failed to stop subagent')}: ${error}`);
		}
	};
</script>

{#if partition.branch || partition.plans.length > 0 || partition.waves.length > 0 || partition.tools.length > 0 || partition.subagents.length > 0}
	<div class="mb-2 space-y-2">
		<TreeSwitcher
			event={partition.branch}
			{mock}
			on:switch={(e) => branchSwitchHandler(e.detail.id)}
		/>

		{#each partition.plans as plan (plan.plan_id)}
			<PlanCard event={plan} {mock} />
		{/each}

		{#if partition.waves.length > 0}
			<WaveBoard events={partition.waves} plan={partition.plans[0] ?? null} {mock} />
		{/if}

		<ToolTimeline events={partition.tools} {mock} />
		<SubagentCard events={partition.subagents} {mock} on:stop={(e) => subagentStopHandler(e.detail)} />
	</div>
{/if}
