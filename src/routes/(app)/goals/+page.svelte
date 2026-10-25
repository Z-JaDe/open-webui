<script lang="ts">
	// /goals:goal 会话面——列表选中 goal,右侧看内部会话转录(管理者/子代理/审查者)。
	// 转录含文本/思考/工具调用/工具结果全形态;子代理带 busy 状态。
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import {
		getBanyanGoalConvs,
		getBanyanGoals,
		type BanyanGoalConvs,
		type BanyanGoalEntry
	} from '$lib/apis/banyan';

	type TMsg = {
		role: string;
		text: string | null;
		thinking?: string | null;
		toolCalls?: Array<{ name: string; args: string }> | null;
		toolName?: string | null;
		isError?: boolean;
	};

	let loaded = false;
	let error = '';
	let goals: BanyanGoalEntry[] = [];
	let selected = '';
	let convs: BanyanGoalConvs | null = null;
	let convsLoading = false;
	let convsError = '';
	let tab = 'manager';

	const statusColor = (s: string) =>
		s === 'completed'
			? 'text-emerald-600 dark:text-emerald-400'
			: s === 'failed'
				? 'text-red-500 dark:text-red-400'
				: s === 'aborted'
					? 'text-gray-400'
					: 'text-blue-500 dark:text-blue-400';

	const phaseLabel = (g: BanyanGoalEntry) =>
		g.status === 'running' ? `${g.phase}…` : g.status;

	async function refresh() {
		try {
			goals = await getBanyanGoals();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	async function select(goalId: string) {
		selected = goalId;
		convs = null;
		convsError = '';
		tab = 'manager';
		convsLoading = true;
		try {
			convs = await getBanyanGoalConvs(goalId);
		} catch (e) {
			convsError = e instanceof Error ? e.message : String(e);
		}
		convsLoading = false;
	}

	$: tabs = convs
		? [
				{ id: 'manager', label: '管理者', icon: '🧠', count: convs.manager.transcript.length },
				...convs.subagents.map((sa, i) => ({
					id: `sub:${i}`,
					label: sa.name,
					icon: sa.busy ? '🔄' : '⏸',
					count: sa.transcript.length
				})),
				...convs.reviewers.map((rv, i) => ({
					id: `rev:${i}`,
					label: rv.name.slice(0, 12),
					icon: '🔍',
					count: rv.transcript.length
				}))
			]
		: [];

	$: activeTranscript: TMsg[] =
		convs === null
			? []
			: tab === 'manager'
				? (convs.manager.transcript as TMsg[])
				: tab.startsWith('sub:')
					? ((convs.subagents[Number(tab.slice(4))]?.transcript ?? []) as TMsg[])
					: ((convs.reviewers[Number(tab.slice(4))]?.transcript ?? []) as TMsg[]);

	onMount(() => {
		let timer: ReturnType<typeof setInterval>;
		void (async () => {
			await refresh();
			loaded = true;
			timer = setInterval(refresh, 8000);
		})();
		return () => clearInterval(timer);
	});
</script>

<svelte:head>
	<title>Goal 会话</title>
</svelte:head>

<div
	class="flex flex-col h-full min-h-0 w-full max-w-full transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-full mx-auto w-full px-4 py-8">
			<div class="flex items-center gap-2 mb-1">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
				>
					G
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">Goal 会话</h1>
			</div>
			<p class="text-xs text-gray-400 dark:text-gray-500 mb-6">
				后台 goal 的内部会话(管理者/子代理/审查者)——含工具调用与结果;正本在 pi-goal durable 存储。
			</p>

			{#if error}
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
					引擎不可达:{error}
				</div>
			{/if}

			{#if loaded}
				<div class="flex flex-col lg:flex-row gap-4" data-testid="banyan-goals-page">
					<div class="lg:w-72 shrink-0 rounded-xl border border-gray-100 dark:border-gray-850 p-2 max-h-[75vh] overflow-y-auto">
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400 px-2 py-1.5">Goal({goals.length})</div>
						{#each goals as g (g.goalId)}
							<button
								class="w-full text-left px-3 py-2 rounded-lg text-sm transition {selected === g.goalId
									? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white'
									: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
								on:click={() => select(g.goalId)}
							>
								<div class="flex items-center justify-between gap-2">
									<span class="truncate">{g.objective.slice(0, 40)}</span>
									<span class="text-[10px] whitespace-nowrap font-mono {statusColor(g.status)}">{phaseLabel(g)}</span>
								</div>
								<div class="text-[10px] text-gray-400 dark:text-gray-500 truncate">{g.goalId} · {g.kind}</div>
							</button>
						{/each}
					</div>

					<div class="flex-1 min-w-0 rounded-xl border border-gray-100 dark:border-gray-850 p-4 max-h-[75vh] overflow-y-auto">
						{#if !selected}
							<div class="text-sm text-gray-400 dark:text-gray-500 py-12 text-center">← 选一个 goal 查看内部会话</div>
						{:else if convsLoading}
							<div class="text-sm text-gray-400 dark:text-gray-500 py-12 text-center">加载转录…</div>
						{:else if convsError}
							<div class="text-sm text-red-500 dark:text-red-400 py-6 text-center">{convsError}</div>
						{:else if convs}
							<div class="flex flex-wrap gap-1.5 mb-3">
								{#each tabs as t}
									<button
										class="px-2.5 py-1 rounded-full text-[11px] transition {tab === t.id
											? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
											: 'bg-gray-50 dark:bg-gray-900 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
										on:click={() => (tab = t.id)}
									>
										{t.icon} {t.label} <span class="text-gray-400">({t.count})</span>
									</button>
								{/each}
							</div>

							{#if tab === 'manager' && convs.subagents.length > 0}
								<div class="mb-4 rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 p-3">
									<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">子代理总览</div>
									<div class="flex flex-wrap gap-2">
										{#each convs.subagents as sa}
											<div class="flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-800 px-2.5 py-1 text-[11px]">
												<span class="font-medium text-gray-700 dark:text-gray-300">{sa.name}</span>
												<span class="text-gray-400">{sa.transcript.length} 消息</span>
												{#if sa.busy}
													<span class="text-blue-500">🔄 工作中</span>
												{:else}
													<span class="text-gray-400">⏸ 空闲</span>
												{/if}
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<div class="space-y-2">
								{#each activeTranscript as m}
									{#if m.role === 'toolResult'}
										<div class="flex justify-start">
											<div class="max-w-[80%] rounded-lg border-l-2 {m.isError ? 'border-red-400 bg-red-50 dark:bg-red-950/30' : 'border-green-400 bg-green-50/50 dark:bg-gray-900'} px-3 py-1.5">
												<div class="text-[10px] font-mono text-gray-400 dark:text-gray-500 mb-0.5">⚙ result{m.toolName ? ` · ${m.toolName}` : ''}</div>
												<div class="text-[12px] text-gray-600 dark:text-gray-400 font-mono whitespace-pre-wrap break-words max-h-24 overflow-y-auto">{m.text || '(空结果)'}</div>
											</div>
										</div>
									{:else if m.toolCalls && m.toolCalls.length > 0}
										<div class="flex justify-end">
											<div class="max-w-[80%] rounded-lg border border-amber-300/50 dark:border-amber-700/50 bg-amber-50/60 dark:bg-gray-900 px-3 py-1.5">
												{#each m.toolCalls as tc}
													<div class="text-[10px] font-mono text-amber-700 dark:text-amber-400">🔧 {tc.name}</div>
													<div class="text-[11px] text-gray-500 dark:text-gray-500 font-mono whitespace-pre-wrap break-words max-h-16 overflow-y-auto">{tc.args}</div>
												{/each}
												{#if m.text}
													<div class="text-[12px] text-gray-700 dark:text-gray-300 mt-1">{m.text}</div>
												{/if}
											</div>
										</div>
									{:else if m.role === 'user'}
										<div class="flex justify-end">
											<div class="max-w-[85%] rounded-2xl bg-gray-900 dark:bg-gray-100 px-3.5 py-2 text-[13px] text-gray-50 dark:text-gray-900 whitespace-pre-wrap break-words">
												{m.text || '(空)'}
											</div>
										</div>
									{:else}
										<div class="flex justify-start">
											<div class="max-w-[85%] rounded-2xl bg-gray-100 dark:bg-gray-850 px-3.5 py-2 text-[13px] text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
												{#if m.thinking}
													<details class="mb-1">
														<summary class="text-[10px] text-gray-400 cursor-pointer">💭 思考</summary>
														<div class="text-[11px] text-gray-400 dark:text-gray-500 whitespace-pre-wrap">{m.thinking}</div>
													</details>
												{/if}
												{m.text || '(无文本输出)'}
											</div>
										</div>
									{/if}
								{:else}
									<div class="text-xs text-gray-400 dark:text-gray-500 py-8 text-center">该会话暂无消息</div>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>
