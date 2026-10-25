<script lang="ts">
	// /workspaces — v3 工作空间(设计-工作空间v1):空间=主Agent+地盘+能力包(+预发通道)。
	// 正本两层:主仓 workspaces/(内置)∪ ~/.banyan/workspaces/(自建);引擎热载直读。
	// 页面即视图,Chat 即编辑器:自建空间在其会话里说人话即可改;内置空间在自举空间改。
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import { getBanyanWorkspaces, type BanyanWorkspace } from '$lib/apis/banyan';

	let loaded = false;
	let error = '';
	let spaces: BanyanWorkspace[] = [];
	let selected = '';
	let detail: BanyanWorkspace | null = null;
	let tab = 'agent';

	async function refresh() {
		try {
			spaces = await getBanyanWorkspaces();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	async function select(id: string) {
		selected = id;
		tab = 'agent';
		const cached = spaces.find((s) => s.id === id);
		if (cached?.agent_prompt) {
			detail = cached;
			return;
		}
		try {
			const { getBanyanWorkspace } = await import('$lib/apis/banyan');
			detail = await getBanyanWorkspace(id);
		} catch {
			detail = cached ?? null;
		}
	}

	const TABS = [
		{ id: 'agent', label: '主Agent' },
		{ id: 'roots', label: '地盘' },
		{ id: 'skills', label: '技能' },
		{ id: 'knowledge', label: '知识' },
		{ id: 'tools', label: '工具与角色' },
		{ id: 'staging', label: '预发通道' }
	];

	onMount(() => {
		void (async () => {
			await refresh();
			if (spaces.length > 0) await select(spaces[0].id);
			loaded = true;
		})();
	});
</script>

<svelte:head>
	<title>工作空间 · banyan</title>
</svelte:head>

<div
	class="flex flex-col h-full min-h-0 w-full max-w-full transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-4xl mx-auto w-full px-4 py-8">
			<div class="flex items-center gap-2 mb-1">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
				>
					W
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">工作空间</h1>
			</div>
			<p class="text-xs text-gray-400 dark:text-gray-500 mb-6">
				空间 = 主Agent + 地盘 + 能力包;新会话一律跑所选空间的主Agent。内置空间随主仓版本;自建空间在本页展示、在其会话里 Chat 修改。
			</p>

			{#if error}
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
					引擎不可达:{error}
				</div>
			{/if}

			{#if loaded}
				<!-- 空间卡片 -->
				<div class="grid gap-3 md:grid-cols-2 mb-8">
					{#each spaces as s (s.id)}
						<button
							class="text-left rounded-xl border p-4 transition {selected === s.id
								? 'border-gray-900/30 dark:border-white/30 bg-gray-50 dark:bg-gray-900'
								: 'border-gray-100 dark:border-gray-850 hover:bg-gray-50 dark:hover:bg-gray-900/50'}"
							on:click={() => select(s.id)}
						>
							<div class="flex items-center justify-between gap-2 mb-1">
								<span class="text-sm font-semibold text-gray-900 dark:text-white">{s.name}</span>
								<span class="text-[10px] px-1.5 py-0.5 rounded-full {s.builtin
									? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
									: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'}">
									{s.builtin ? '内置' : '自建'}
								</span>
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{s.description}</div>
							<div class="mt-2 flex items-center gap-3 text-[10px] text-gray-400">
								<span>主Agent:{s.agent.model || s.agent.tier}</span>
								{#if s.staging}<span class="text-amber-500">预发通道</span>{/if}
								{#if s.degraded}<span class="text-red-500">配置降级中:{s.error.slice(0, 40)}</span>{/if}
							</div>
						</button>
					{:else}
						<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center md:col-span-2">
							暂无空间——内置空间随主仓 workspaces/ 提供;自建空间放 ~/.banyan/workspaces/&lt;id&gt;/
						</div>
					{/each}
				</div>

				<!-- 选中空间详情 -->
				{#if detail}
					<div class="rounded-xl border border-gray-100 dark:border-gray-850">
						<div class="flex items-center gap-1 px-2 pt-2 overflow-x-auto">
							{#each TABS as t (t.id)}
								<button
									class="px-3 py-1.5 text-xs font-medium rounded-lg transition {tab === t.id
										? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white'
										: 'text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-900'}"
									on:click={() => (tab = t.id)}
								>
									{t.label}
								</button>
							{/each}
						</div>
						<div class="p-4 border-t border-gray-100 dark:border-gray-850">
							{#if tab === 'agent'}
								<div class="text-[11px] text-gray-400 mb-2">
									AGENT.md(该空间每个新会话的系统提示词;model={detail.agent.model || '(随档位)'} · tier={detail.agent.tier})。
									{detail.builtin ? '内置空间:在自举空间里 Chat 修改(=改主仓)。' : '自建空间:在其会话里 Chat 修改。'}
								</div>
								<pre class="text-xs leading-relaxed whitespace-pre-wrap text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 max-h-96 overflow-y-auto">{detail.agent_prompt}</pre>
							{:else if tab === 'roots'}
								<div class="text-xs text-gray-500 dark:text-gray-400 space-y-1">
									{#each detail.roots as r (r)}
										<div class="font-mono text-[11px] bg-gray-50 dark:bg-gray-900/50 rounded px-2 py-1">{r}</div>
									{:else}
										<div class="text-gray-400">roots 为空(默认引擎工作区)</div>
									{/each}
								</div>
							{:else if tab === 'skills'}
								<div class="flex flex-wrap gap-2">
									{#each detail.skills as sk (sk)}
										<span class="text-xs px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-200 font-mono">{sk}</span>
									{:else}
										<span class="text-xs text-gray-400">无技能</span>
									{/each}
								</div>
							{:else if tab === 'knowledge'}
								<div class="flex flex-wrap gap-2">
									{#each detail.knowledge_scopes as k (k)}
										<span class="text-xs px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-200">{k}</span>
									{:else}
										<span class="text-xs text-gray-400">未挂知识域</span>
									{/each}
								</div>
							{:else if tab === 'tools'}
								<div class="text-[11px] text-gray-400 mb-1">工具白名单</div>
								<div class="flex flex-wrap gap-1 mb-3">
									{#each detail.tools as t (t)}
										<span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850 font-mono">{t}</span>
									{/each}
								</div>
								<div class="text-[11px] text-gray-400 mb-1">可派 subagent 角色</div>
								<div class="flex flex-wrap gap-1">
									{#each detail.roles as r (r)}
										<span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850">{r}</span>
									{/each}
								</div>
							{:else if tab === 'staging'}
								{#if detail.staging}
									<div class="text-xs text-gray-500 dark:text-gray-400 space-y-1">
										{#each Object.entries(detail.staging_config ?? {}) as [k, v] (k)}
											<div class="font-mono text-[11px] bg-gray-50 dark:bg-gray-900/50 rounded px-2 py-1">{k} = {v}</div>
										{/each}
										<div class="text-[11px] text-amber-500 pt-1">
											改码 → build-verify → deploy-staging → validate-staging → promote(技能四件,正文见空间 skills/)
										</div>
									</div>
								{:else}
									<div class="text-xs text-gray-400">本空间无预发通道</div>
								{/if}
							{/if}
						</div>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>
