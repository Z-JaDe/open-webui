<script lang="ts">
	// banyan 场景包卡片(RF-37):/arch 花名册区块旁的场景包一览。
	// 数据源 getBanyanPacks() → 引擎 GET /api/packs(fork 代理桥 /banyan/api/*)。
	// 只读展示面:引擎不可达/暂无包都降级为一行说明,不抛错不炸页面
	//(与引擎侧「降级=少一行,不是 500」同一纪律)。
	import { onMount } from 'svelte';

	import { getBanyanPacks, type BanyanPack } from '$lib/apis/banyan';

	let packs: BanyanPack[] = [];
	let loaded = false;
	let error: string | null = null;

	const faceLabel = (p: BanyanPack): string => {
		const parts: string[] = [];
		if (p.prompts.length) parts.push(`模板 ${p.prompts.length}`);
		if (p.skills.length) parts.push(`技能 ${p.skills.length}`);
		if (p.agents.length) parts.push(`特化 Agent ${p.agents.length}`);
		return parts.length ? parts.join(' · ') : '空包';
	};

	onMount(async () => {
		try {
			packs = await getBanyanPacks();
		} catch (e) {
			error = `${e}`;
		} finally {
			loaded = true;
		}
	});
</script>

<div class="rounded-xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 p-4 h-full">
	<div class="flex items-center gap-2 mb-3">
		<div
			class="self-center flex size-6 shrink-0 items-center justify-center rounded-md bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
		>
			P
		</div>
		<h2 class="text-sm font-semibold text-gray-900 dark:text-white">场景包</h2>
		{#if loaded && !error}
			<span class="text-xs text-gray-400">{packs.length}</span>
		{/if}
	</div>

	{#if !loaded}
		<div class="text-xs text-gray-400 py-2">加载中…</div>
	{:else if error}
		<div class="text-xs text-gray-400 py-2">引擎不可达,场景包列表暂缺</div>
	{:else if packs.length === 0}
		<div class="text-xs text-gray-400 py-2">暂无场景包($BANYAN_HOME/packs)</div>
	{:else}
		<ul class="flex flex-col gap-2">
			{#each packs as p (p.id)}
				<li class="rounded-lg bg-gray-50 dark:bg-gray-850 p-3">
					<div class="flex items-center gap-2 flex-wrap">
						<span class="text-sm font-medium text-gray-900 dark:text-white">{p.id}</span>
						<span class="text-[11px] text-gray-400">{faceLabel(p)}</span>
					</div>
					{#if p.description}
						<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{p.description}</p>
					{/if}
					{#if p.prompts.length || p.skills.length || p.agents.length}
						<div class="mt-2 flex flex-wrap gap-1">
							{#each p.prompts as n}
								<span
									class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[11px] text-gray-600 dark:text-gray-300"
								>模板:{n}</span
								>
							{/each}
							{#each p.skills as n}
								<span
									class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[11px] text-gray-600 dark:text-gray-300"
								>技能:{n}</span
								>
							{/each}
							{#each p.agents as n}
								<span
									class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[11px] text-gray-600 dark:text-gray-300"
								>Agent:{n}</span
								>
							{/each}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>
