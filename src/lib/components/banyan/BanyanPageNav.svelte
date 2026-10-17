<!--
	banyan 任务工作台导航 pills（钩点③）：registry / cards / audit / inbox / cal 列表页共用；
	waves/tree 为详情页，由各自入口进入。
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let tabs = [
		{ id: 'registry', label: 'Registry', href: '/registry' },
		{ id: 'cards', label: 'Cards', href: '/cards' },
		{ id: 'audit', label: 'Audit', href: '/audit' },
		{ id: 'inbox', label: 'Inbox', href: '/inbox' },
		{ id: 'cal', label: 'Calendar', href: '/cal' }
	];

	$: active = $page.url.pathname;
</script>

<div class="flex items-center gap-1 flex-wrap px-8 lg:px-28 xl:px-40 pt-3">
	{#each tabs as tab (tab.id)}
		<a
			href="{tab.href}{active.includes('/waves/') || active.includes('/tree/') ? '' : $page.url.searchParams.has('mock') ? '?mock=1' : ''}"
			class="px-3 py-1.5 rounded-lg text-xs font-medium transition {active === tab.href ||
			active.startsWith(tab.href + '/')
				? 'bg-black/[0.05] dark:bg-white/[0.08] text-black dark:text-white'
				: 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900'}"
		>
			{$i18n.t(tab.label)}
		</a>
	{/each}
</div>
