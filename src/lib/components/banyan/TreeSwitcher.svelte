<!--
	banyan 渲染组件 5/5：TreeSwitcher（统一设计 §6.2 / §8 G2）

	事件 schema → 渲染契约：
	  输入 BanyanBranchEvent（同一消息块只保留最新一份）：
	    { type:'branch', branches:[{id, label, active}], ts? }
	  渲染：分支 pills，挂在消息块顶端；active 分支高亮；
	  点击 pill → dispatch 'switch'（聊天内仅切换活动分支视图，引擎回投影线性消息流；
	  全功能树操作在 /tree/[chatId] 页）。

	mock：`<TreeSwitcher mock />` 渲染内置样例分支。
-->
<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	import { mockBranchEvent } from './mock';
	import type { BanyanBranchEvent } from './types';

	const i18n = getContext<Writable<i18nType>>('i18n');
	const dispatch = createEventDispatcher<{ switch: { id: string } }>();

	export let event: BanyanBranchEvent | null = null;
	/** story 开关：不接引擎，渲染内置样例 */
	export let mock = false;

	$: branchEvent = mock ? mockBranchEvent : event;

	const switchHandler = (id: string) => {
		if (!branchEvent) return;
		const branch = branchEvent.branches.find((b) => b.id === id);
		if (!branch || branch.active) return;
		dispatch('switch', { id });
	};
</script>

{#if branchEvent && branchEvent.branches?.length > 1}
	<div class="w-full flex items-center gap-1.5 flex-wrap" role="tablist" aria-label={$i18n.t('Conversation branches')}>
		<span class="text-[11px] text-gray-400 dark:text-gray-500 shrink-0">
			{$i18n.t('Branches')}
		</span>
		{#each branchEvent.branches as branch (branch.id)}
			<button
				type="button"
				role="tab"
				aria-selected={branch.active}
				class="px-2.5 py-1 rounded-full text-[11px] border transition max-w-52 truncate {branch.active
					? 'bg-black text-white border-black dark:bg-white dark:text-black dark:border-white'
					: 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}"
				on:click={() => switchHandler(branch.id)}
				title={branch.label}
			>
				{branch.label}
			</button>
		{/each}
	</div>
{/if}
