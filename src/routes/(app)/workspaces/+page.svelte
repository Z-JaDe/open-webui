<script lang="ts">
	// /workspaces — v3 工作空间(设计-工作空间v1):空间=主Agent+地盘+能力包(+预发通道)。
	// 正本两层:主仓 workspaces/(内置)∪ ~/.banyan/workspaces/(自建);引擎热载直读。
	// 页面即视图,Chat 即编辑器:自建空间在其会话里说人话即可改;内置空间在气根空间改。
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import {
		getBanyanWorkspaces,
		type BanyanWorkspace,
		type BanyanWorkspaceListResult
	} from '$lib/apis/banyan';

	let loaded = false;
	let error = '';
	let spaces: BanyanWorkspace[] = [];
	let selected = '';
	let detail: BanyanWorkspace | null = null;
	let tab = 'agent';
	let selSkill = '';
	let selRole = '';
	let selScope = '';
	// RF1-D:注册表级警告(同名冲突/坏配置空间)。后端 banyan 仓并行加键,
	// 缺键(旧引擎)时 undefined → 不渲染,向后兼容。
	let registryConflicts: string[] | undefined;
	let registryErrors: Record<string, string> | undefined;

	async function refresh() {
		try {
			const result: BanyanWorkspaceListResult = await getBanyanWorkspaces();
			spaces = result.workspaces;
			registryConflicts = result.conflicts;
			registryErrors = result.errors;
			error = ''; // F14:refresh 成功清 error(失败横幅不再跨刷新滞留)
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	async function select(id: string) {
		selected = id;
		tab = 'agent';
		selSkill = '';
		selRole = '';
		selScope = '';
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
				<!-- F14:失败态不与空态卡并显——引擎不可达时只出错误横幅(带重试) -->
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400 mb-6">
					引擎不可达:{error}
					<button
						class="ml-2 underline underline-offset-2 hover:opacity-70"
						on:click={() => refresh()}
					>
						重试
					</button>
				</div>
			{/if}

			{#if registryConflicts && registryConflicts.length > 0}
				<!-- RF1-D:同名冲突(内置 ∪ 自建不做覆盖,单一真相)——冲突名不在
				workspaces 列表里,不点选只示警 -->
				<div class="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/30 p-4 text-sm text-amber-600 dark:text-amber-400 mb-6">
					空间名冲突(同名不覆盖):{registryConflicts.join('、')}
				</div>
			{/if}

			{#if registryErrors && Object.keys(registryErrors).length > 0}
				<!-- RF1-D:坏配置空间(id → 错误摘要) -->
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400 mb-6">
					{#each Object.entries(registryErrors) as [id, err] (id)}
						<!-- _layer_ 哨兵键=层目录整体不可读(RF3a-2),不是空间 id -->
						<div>
							{id.startsWith('_layer_') ? '工作空间层目录不可读' : `坏空间 ${id}`}:{err.slice(0, 80)}
						</div>
					{/each}
				</div>
			{/if}

			{#if loaded && !error}
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
								{#if s.degraded}<span class="text-red-500">配置降级中:{s.error?.slice?.(0, 40) ?? ''}</span>{/if}
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
									{detail.builtin ? '内置空间:在气根空间里 Chat 修改(=改主仓)。' : '自建空间:在其会话里 Chat 修改。'}
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
								{#if detail.skills.length === 0}
									<span class="text-xs text-gray-400">无技能</span>
								{:else}
									<div class="flex flex-wrap gap-2 mb-3">
										{#each detail.skills as sk (sk)}
											<button
												class="text-xs px-2 py-1 rounded-lg font-mono transition {selSkill === sk
													? 'bg-gray-900 text-white dark:bg-white dark:text-black'
													: 'bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-200'}"
												on:click={() => (selSkill = selSkill === sk ? '' : sk)}
											>
												{sk}
											</button>
										{/each}
									</div>
									{#if selSkill}
										{@const body = detail.skills_detail?.find((x) => x.name === selSkill)?.body ?? ''}
										<pre class="text-xs leading-relaxed whitespace-pre-wrap text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 max-h-96 overflow-y-auto">{body}</pre>
									{/if}
								{/if}
								{:else if tab === 'knowledge'}
									{@const scopeButtons = [
										...detail.knowledge_scopes,
										// P2-2:「(空间私有)」域引擎恒扫描(knowledge_detail 里恒有条目)但
										// 从不进 knowledge_scopes 投影——补入口使扫描结果可达;条件渲染,
										// 后端未发该条目时(旧引擎/无私有知识)不显示,无新键依赖。
										...(detail.knowledge_detail?.some((x) => x.scope === '(空间私有)') &&
										!detail.knowledge_scopes.includes('(空间私有)')
											? ['(空间私有)']
											: [])
									]}
									{#if scopeButtons.length === 0}
										<span class="text-xs text-gray-400">未挂知识域</span>
									{:else}
										<div class="flex flex-wrap gap-2 mb-3">
											{#each scopeButtons as k (k)}
												<button
													class="text-xs px-2 py-1 rounded-lg transition {selScope === k
														? 'bg-gray-900 text-white dark:bg-white dark:text-black'
														: 'bg-gray-100 dark:bg-gray-850 text-gray-700 dark:text-gray-200'}"
													on:click={() => (selScope = selScope === k ? '' : k)}
												>
													{k}
												</button>
											{/each}
										</div>
									{#if selScope}
										{@const kd = detail.knowledge_detail?.find((x) => x.scope === selScope)}
										<div class="text-[11px] text-gray-400 mb-1">{selScope} · 共 {kd?.total ?? 0} 条</div>
										<div class="space-y-1 max-h-72 overflow-y-auto">
											{#each kd?.items ?? [] as it (it.file)}
												<div class="flex items-center gap-2 text-xs bg-gray-50 dark:bg-gray-900/50 rounded px-2 py-1.5">
													<span class="text-gray-800 dark:text-gray-100 truncate">{it.title}</span>
													<span class="ml-auto text-[10px] text-gray-400 font-mono truncate">{it.file}</span>
												</div>
											{:else}
												<div class="text-xs text-gray-400">该域暂无条目</div>
											{/each}
										</div>
									{/if}
								{/if}
							{:else if tab === 'tools'}
								<div class="text-[11px] text-gray-400 mb-1">工具白名单</div>
								<div class="flex flex-wrap gap-1 mb-3">
									{#each detail.tools as t (t)}
										<span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850 font-mono">{t}</span>
									{/each}
								</div>
								<div class="text-[11px] text-gray-400 mb-1">可派 subagent 角色(点击看正文)</div>
								<div class="flex flex-wrap gap-1 mb-3">
									{#each detail.roles as r (r)}
										<button
											class="text-[11px] px-1.5 py-0.5 rounded transition {selRole === r
												? 'bg-gray-900 text-white dark:bg-white dark:text-black'
												: 'bg-gray-100 dark:bg-gray-850'}"
											on:click={() => (selRole = selRole === r ? '' : r)}
										>
											{r}
										</button>
									{/each}
								</div>
								{#if selRole}
									{@const rd = detail.roles_detail?.find((x) => x.name === selRole)}
									{#if rd}
										<div class="text-[11px] text-gray-400 mb-1">
											{rd.description} · tier={rd.tier} · memory={rd.memory} · 工具:{rd.tools.join(', ') || '无'}
										</div>
										<pre class="text-xs leading-relaxed whitespace-pre-wrap text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 max-h-72 overflow-y-auto">{rd.prompt}</pre>
									{/if}
								{/if}
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
