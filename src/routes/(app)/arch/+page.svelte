<script lang="ts">
	// banyan /arch:架构权威介绍页(WE-7,统一设计 §8 G3 追加路由)
	// 正本在 banyan 主仓 docs/architecture.md,此处镜像渲染;更新随 fork 同步流程搬运。
	import { getContext, onMount } from 'svelte';
	import type i18nType from '$lib/i18n';

	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';

	// @ts-ignore md raw import has no local typings in this repo
	import architectureMd from '$lib/assets/architecture.md?raw';

	const i18n: typeof i18nType = getContext('i18n');

	let loaded = false;
	onMount(() => {
		loaded = true;
	});
</script>

<svelte:head>
	<title>{$i18n.t('Architecture')}</title>
</svelte:head>

<div class="flex flex-col h-full min-h-0">
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-3xl mx-auto w-full px-4 py-8">
			<div class="flex items-center gap-2 mb-5">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
				>
					B
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">
					{$i18n.t('Architecture')}
				</h1>
			</div>

			{#if loaded}
				<div class="prose dark:prose-invert max-w-full text-sm">
					<Markdown content={architectureMd} id="banyan-architecture" />
				</div>
			{/if}
		</div>
	</div>
</div>
