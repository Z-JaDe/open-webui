<!-- 
	banyan 渲染组件 1/5：PlanCard（统一设计 §6.2 / §8 G2）

	事件 schema → 渲染契约：
	  输入 BanyanPlanEvent（src/lib/components/banyan/types.ts）：
	    { type:'plan', plan_id, title?, status:'pending'|'approved'|'rejected'|'revised',
	      hypothesis?, waves:[{index,title?,depends_on?,tasks:[{task_id,title,deps?}]}],
	      acceptance?, risks?, rollback?, alt_option?, ts? }
	  渲染：结构化方案卡（假设/波次/验收/风险/回滚）；
	  status==='pending' 时展示原生按钮：批准 / 驳回 / 选 B（备选方案）。
	  按钮 → POST /banyan/api/plans/:plan_id/resolve  body {decision:'approved'|'rejected'|'revised', choice?}
	  成功后本地回填 status（引擎回流的 plan 事件 upsert 同 plan_id 时亦会覆盖）。

	mock：`<PlanCard mock />` 渲染内置样例（src/lib/components/banyan/mock.ts）。
-->
<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	import { resolveBanyanPlan } from '$lib/apis/banyan';
	import { mockPlanEvent } from './mock';
	import {
		BANYAN_PLAN_STATUS_LABEL,
		type BanyanPlanEvent,
		type BanyanPlanResolveBody
	} from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ resolve: BanyanPlanResolveBody }>();

	export let event: BanyanPlanEvent | null = null;
	/** story 开关：不接引擎，渲染内置样例 */
	export let mock = false;

	$: plan = mock ? mockPlanEvent : event;

	let resolving = false;
	let showAltOption = false;

	const resolveHandler = async (decision: BanyanPlanResolveBody['decision']) => {
		if (!plan || plan.status !== 'pending' || resolving) return;
		resolving = true;
		try {
			await resolveBanyanPlan(plan.plan_id, { decision });
			plan = { ...plan, status: decision };
			dispatch('resolve', { decision });
			toast.success(
				decision === 'approved'
					? $i18n.t('Plan approved')
					: decision === 'rejected'
						? $i18n.t('Plan rejected')
						: $i18n.t('Switched to alternative plan')
			);
		} catch (error) {
			toast.error(`${$i18n.t('Failed to resolve plan')}: ${error}`);
		} finally {
			resolving = false;
		}
	};

	$: statusTone =
		plan?.status === 'approved'
			? 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20'
			: plan?.status === 'rejected'
				? 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20'
				: plan?.status === 'revised'
					? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
					: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
</script>

{#if plan}
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-gray-50 dark:bg-gray-900/40 p-3 w-full space-y-2.5">
		<div class="flex items-start justify-between gap-2">
			<div class="flex items-center gap-2 min-w-0">
				<div class="self-center size-6 shrink-0 rounded-lg bg-black/[0.04] dark:bg-white/[0.06] flex items-center justify-center text-[11px] font-medium">
					B
				</div>
				<div class="min-w-0">
					<div class="text-sm font-medium text-black dark:text-white truncate">
						{plan.title ?? $i18n.t('Execution Plan')}
					</div>
					<div class="text-[11px] text-gray-500 dark:text-gray-400 truncate">
						{plan.plan_id}
					</div>
				</div>
			</div>
			<span class="shrink-0 text-[11px] px-2 py-0.5 rounded-full border {statusTone}">
				{$i18n.t(BANYAN_PLAN_STATUS_LABEL[plan.status])}
			</span>
		</div>

		{#if plan.hypothesis}
			<div class="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
				<span class="font-medium text-gray-700 dark:text-gray-200">{$i18n.t('Hypothesis')}:</span>
				{plan.hypothesis}
			</div>
		{/if}

		<div class="space-y-1.5">
			{#each plan.waves as wave (wave.index)}
				<div class="flex items-start gap-2 text-xs">
					<span class="shrink-0 mt-px px-1.5 py-0.5 rounded-md bg-black/[0.05] dark:bg-white/[0.08] font-medium text-gray-600 dark:text-gray-300">
						W{wave.index}
					</span>
					<div class="min-w-0">
						<span class="text-gray-700 dark:text-gray-200">{wave.title ?? $i18n.t('Wave')} {wave.index}</span>
						<span class="text-gray-400 dark:text-gray-500">
							· {wave.tasks.map((task) => task.title).join($i18n.t('、'))}
							{#if wave.depends_on?.length}
								← W{wave.depends_on.join(', W')}
							{/if}
						</span>
					</div>
				</div>
			{/each}
		</div>

		<div class="grid gap-2 md:grid-cols-3 text-xs">
			{#if plan.acceptance?.length}
				<div class="rounded-lg bg-black/[0.03] dark:bg-white/[0.04] p-2">
					<div class="font-medium text-gray-600 dark:text-gray-300 mb-1">{$i18n.t('Acceptance')}</div>
					<ul class="space-y-0.5 text-gray-500 dark:text-gray-400 list-disc list-inside">
						{#each plan.acceptance as item}
							<li>{item}</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if plan.risks?.length}
				<div class="rounded-lg bg-black/[0.03] dark:bg-white/[0.04] p-2">
					<div class="font-medium text-gray-600 dark:text-gray-300 mb-1">{$i18n.t('Risks')}</div>
					<ul class="space-y-0.5 text-gray-500 dark:text-gray-400 list-disc list-inside">
						{#each plan.risks as item}
							<li>{item}</li>
						{/each}
					</ul>
				</div>
			{/if}
			{#if plan.rollback}
				<div class="rounded-lg bg-black/[0.03] dark:bg-white/[0.04] p-2">
					<div class="font-medium text-gray-600 dark:text-gray-300 mb-1">{$i18n.t('Rollback')}</div>
					<div class="text-gray-500 dark:text-gray-400">{plan.rollback}</div>
				</div>
			{/if}
		</div>

		{#if plan.alt_option}
			<div class="text-xs">
				<button
					type="button"
					class="text-blue-600 dark:text-blue-400 hover:underline"
					on:click={() => (showAltOption = !showAltOption)}
				>
					{showAltOption ? $i18n.t('Hide alternative') : $i18n.t('Show alternative plan (B)')}
				</button>
				{#if showAltOption}
					<div class="mt-1 rounded-lg border border-blue-500/20 bg-blue-500/5 p-2 text-gray-600 dark:text-gray-300">
						{plan.alt_option}
					</div>
				{/if}
			</div>
		{/if}

		{#if plan.status === 'pending'}
			<div class="flex items-center gap-2 pt-0.5">
				<Tooltip content={$i18n.t('Approve and start execution')}>
					<button
						type="button"
						class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
						disabled={resolving}
						on:click={() => resolveHandler('approved')}
					>
						<Check className="size-3.5" strokeWidth="2" />
						{$i18n.t('Approve')}
					</button>
				</Tooltip>
				<Tooltip content={$i18n.t('Reject this plan')}>
					<button
						type="button"
						class="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50 transition"
						disabled={resolving}
						on:click={() => resolveHandler('rejected')}
					>
						<XMark className="size-3.5" strokeWidth="2" />
						{$i18n.t('Reject')}
					</button>
				</Tooltip>
				{#if plan.alt_option}
					<Tooltip content={$i18n.t('Choose the alternative plan')}>
						<button
							type="button"
							class="px-3 py-1.5 text-xs font-medium rounded-lg border border-blue-500/30 text-blue-600 dark:text-blue-400 hover:bg-blue-500/10 disabled:opacity-50 transition"
							disabled={resolving}
							on:click={() => resolveHandler('revised')}
						>
							{$i18n.t('Choose B')}
						</button>
					</Tooltip>
				{/if}
			</div>
		{/if}
	</div>
{/if}
