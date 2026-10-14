<script lang="ts">
	// /tree — 树视图入口页：输入 chat id → /tree/[chatId]（钩点③）。
	// ?mock=1 时预填样例 chat id。
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { goto } from '$app/navigation';

	import type i18nType from '$lib/i18n';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: $i18n.t('Tree') });

	let chatId = '';

	const go = () => {
		if (!chatId.trim()) return;
		const mock = new URLSearchParams(window.location.search).has('mock') ? '?mock=1' : '';
		goto(`/tree/${encodeURIComponent(chatId.trim())}${mock}`);
	};

	onMount(() => {
		if (new URLSearchParams(window.location.search).has('mock')) {
			chatId = 'chat-mock-77';
		}
	});
</script>

<svelte:head><title>{$i18n.t('Tree')} · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-16 pt-3">
	<div class="max-w-md space-y-2">
		<div class="text-sm text-gray-500 dark:text-gray-400">
			{$i18n.t('Enter a chat id to open its conversation tree')}
		</div>
		<form
			class="flex items-center gap-2"
			on:submit={(e) => {
				e.preventDefault();
				go();
			}}
		>
			<input
				class="flex-1 text-xs rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-850 outline-none"
				placeholder="chat-mock-77"
				bind:value={chatId}
			/>
			<button
				type="submit"
				class="px-3 py-2 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 transition"
			>
				{$i18n.t('Open')}
			</button>
		</form>
	</div>
</div>
