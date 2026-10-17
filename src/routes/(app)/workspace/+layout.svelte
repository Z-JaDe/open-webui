<script lang="ts">
	// banyan D24（完整方案 §12.5）：workspace 五面（Models/Knowledge/Prompts/Skills/Tools）退役。
	// 原 Models/Knowledge/Prompts/Skills/Tools 五 tab 导航与计数条随之摘除；
	// 各面 +page.svelte 渲染 FeatureRetired 退役占位（路由与组件文件保留，恢复=换回原组件）。
	import { WEBUI_NAME, showSidebar, mobile } from '$lib/stores';
	import { page } from '$app/stores';
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
</script>

<svelte:head>
	<!-- LICENSE covers this Open WebUI browser-title identifier.
	Do not alter, remove, obscure, or replace it except as LICENSE permits:
	https://docs.openwebui.com/license. -->
	<title>
		{$i18n.t('Workspace')} / {$WEBUI_NAME}
	</title>
</svelte:head>

<div
	class="flex flex-col flex-1 min-w-0 w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: 'md:max-w-[calc(100%-42px)]'} max-w-full"
>
	<nav class="pb-1 px-2.5 pt-2 backdrop-blur-xl drag-region select-none">
		<div class="flex items-center gap-0.5 md:gap-1">
			{#if $mobile}
				<div class="{$showSidebar ? 'md:hidden' : ''} self-center flex flex-none items-center">
					<Tooltip
						content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
						interactive={true}
					>
						<button
							id="sidebar-toggle-button"
							class=" cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-"
							aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							on:click={() => {
								showSidebar.set(!$showSidebar);
							}}
						>
							<div class=" self-center p-1.5">
								<Sidebar className="size-4" />
							</div>
						</button>
					</Tooltip>
				</div>
			{/if}

			<div class="flex w-full items-center">
				<div
					class="flex min-w-0 mr-1.5 items-center px-1 text-sm font-normal text-gray-900 dark:text-gray-100"
				>
					{$page.url.pathname.startsWith('/workspace/functions') ? $i18n.t('Functions') : $i18n.t('Workspace')}
				</div>
			</div>
		</div>
	</nav>

	<div
		class="pb-1 flex-1 min-w-0 max-h-full overflow-y-auto overflow-x-hidden flex flex-col"
		id="workspace-container"
	>
		<slot />
	</div>
</div>
