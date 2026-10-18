<script lang="ts">
	// banyan /arch:架构页(WE-7,统一设计 §8 G3 追加路由)。
	// D4/F5 升格为"系统状态的家":状态卡(BanyanEngineStatus 组件复用,登录即可见,
	// 无 admin 依赖 D11)+ 三进程一句话说明 + 存储单根路径(D26,数据源 /status 的
	// engine.home 字段)。正本架构文档在 banyan 主仓 docs/architecture.md,下方镜像渲染。
	import { getContext, onMount } from 'svelte';
	import type i18nType from '$lib/i18n';

	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import BanyanEngineStatus from '$lib/components/admin/BanyanEngineStatus.svelte';
	import PiSessions from '$lib/components/banyan/PiSessions.svelte';
	import { getBanyanStatus } from '$lib/apis/banyan';

	// @ts-ignore md raw import has no local typings in this repo
	import architectureMd from '$lib/assets/architecture.md?raw';

	const i18n: typeof i18nType = getContext('i18n');

	let loaded = false;
	let home = '';
	onMount(async () => {
		// 存储单根(D26):BANYAN_HOME 收纳一切(引擎库/工作区/日志/技能投影);取不到静默
		try {
			home = (await getBanyanStatus()).engine.home ?? '';
		} catch {
			home = '';
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>架构</title>
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
					架构
				</h1>
			</div>

			<!-- D4:系统状态的家——三进程一句话 + 存储单根 + 引擎状态卡 -->
			<div class="mb-6 space-y-4">
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 space-y-2 text-sm"
				>
					<div class="font-medium text-black dark:text-white">系统</div>
					<p class="text-gray-500 dark:text-gray-400">
						三个进程：引擎（:8000，编排、存储正本、K1 事件流）· sidecar（:8100，技能投影）· WebUI（:8080，身份与呈现）。
					</p>
					<p class="text-gray-500 dark:text-gray-400">
						存储根（BANYAN_HOME）：
						<span class="break-all font-mono text-xs text-gray-700 dark:text-gray-300">
							{home || '引擎不可达'}
						</span>
					</p>
				</div>

				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-xs"
					data-testid="banyan-arch-status"
				>
					<div class="text-sm font-medium text-black dark:text-white mb-3">
						引擎状态
					</div>
					<BanyanEngineStatus />
				</div>
			</div>

			{#if loaded}
				<div class="prose dark:prose-invert max-w-full text-sm">
					<Markdown content={architectureMd} id="banyan-architecture" />
				</div>
			{/if}

			<!-- F15/D28:sidecar Pi 会话(手工/休眠会话可见性,只读) -->
			<div
				class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mt-6 text-xs"
				data-testid="banyan-pi-sessions"
			>
				<div class="text-sm font-medium text-black dark:text-white mb-3">
					Pi 会话（sidecar，只读）
				</div>
				<PiSessions />
			</div>
		</div>
	</div>
</div>
