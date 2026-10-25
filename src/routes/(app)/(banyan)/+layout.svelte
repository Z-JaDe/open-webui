<script lang="ts">
	// banyan 任务工作台共享布局（钩点③，统一设计 §6.1 / §8 G3+G5）
	// 现状路由：/cal /inbox(v2 波次五路由 /registry /cards /audit /waves /tree 已连根删除)
	// 数据源统一 /banyan/api/*（fork 后端代理桥 → 引擎）。
	// story 开关：URL 加 ?mock=1 → 各页用内置 mock 数据，不请求引擎。
	import { getContext, setContext } from 'svelte';
	import { writable } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { config, mobile, showSidebar, user } from '$lib/stores';
	import type i18nType from '$lib/i18n';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';

	const i18n: typeof i18nType = getContext('i18n');

	let itemName: string | null = null;
	let HeaderActions: any = null;
	let headerActionProps: Record<string, any> = {};

	const setHeader = ({
		itemName: nextItemName = null,
		actions = null,
		actionProps = {}
	}: {
		itemName?: string | null;
		actions?: any;
		actionProps?: Record<string, any>;
	}) => {
		itemName = nextItemName;
		HeaderActions = actions;
		headerActionProps = actionProps;
	};

	setContext('banyanLayout', {
		setHeader,
		clearHeader: () => setHeader({})
	});

	// story 开关：?mock=1 时子页不请求引擎
	const banyanMock = writable<boolean>(false);
	$: banyanMock.set($page.url.searchParams.has('mock'));
	setContext('banyanMock', banyanMock);
</script>

<div
	class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full"
>
	<div class="flex h-full min-h-0 flex-col">
		<div class="shrink-0 px-2.5 pt-2 pb-1">
			<div class="flex items-center gap-0.5 md:gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center">
						<button
							id="sidebar-toggle-button"
							class="flex size-7 items-center justify-center text-gray-400 transition"
							aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							on:click={() => {
								showSidebar.set(!$showSidebar);
							}}
							type="button"
						>
							<SidebarIcon className="size-4" />
						</button>
					</div>
				{/if}

				<div class="flex w-full min-w-0 items-center">
					<div class="flex min-w-0 flex-1 items-center gap-1 py-1">
						{#if itemName}
							<button
								class="min-w-fit px-1 text-sm select-none transition"
								aria-label={$i18n.t('Back')}
								on:click={() => goto('/goals')}
								type="button"
								>
									任务
								</button>
							{:else}
								<span class="min-w-fit px-1 text-sm select-none">任务</span>
						{/if}
						{#if itemName}
							<span class="text-sm text-gray-300 dark:text-gray-800 px-2">/</span>
							<span class="min-w-0 flex-1 truncate text-sm text-gray-900 dark:text-white">
								{itemName}
							</span>
						{/if}
					</div>

					{#if HeaderActions}
						<svelte:component this={HeaderActions} {...headerActionProps} />
					{/if}
				</div>
			</div>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto">
			<slot />
		</div>
	</div>
</div>
