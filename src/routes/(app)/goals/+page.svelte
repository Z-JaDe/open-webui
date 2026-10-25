<script lang="ts">
	// /goals:goal 会话面——列表选中 goal,右侧看内部会话转录(管理者/子代理/审查者)。
	// 数据源 /banyan/api/goals 与 /goals/:id/convs(pi-goal durable 转录,只读)。
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import {
		getBanyanGoalConvs,
		getBanyanGoals,
		type BanyanGoalConvs,
		type BanyanGoalEntry
	} from '$lib/apis/banyan';

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
				{ id: 'manager', label: `管理者(${convs.manager.transcript.length})` },
				...convs.subagents.map((sa, i) => ({
					id: `sub:${i}`,
					label: `${sa.name}(${sa.transcript.length})`
				})),
				...convs.reviewers.map((rv, i) => ({
					id: `rev:${i}`,
					label: `审:${rv.name}(${rv.transcript.length})`
				}))
			]
		: [];

	$: activeTranscript =
		convs === null
			? null
			: tab === 'manager'
				? convs.manager.transcript
				: tab.startsWith('sub:')
					? convs.subagents[Number(tab.slice(4))]?.transcript ?? []
					: convs.reviewers[Number(tab.slice(4))]?.transcript ?? [];

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
				后台 goal 的内部会话转录(管理者/常驻子代理/审查者)——只读,正本在 pi-goal durable 存储;每 8s 刷新列表。
			</p>

			{#if error}
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
					引擎不可达:{error}
				</div>
			{/if}

			{#if loaded}
				<div class="flex flex-col lg:flex-row gap-4" data-testid="banyan-goals-page">
					<!-- 左:goal 列表 -->
					<div class="lg:w-72 shrink-0 rounded-xl border border-gray-100 dark:border-gray-850 p-2 max-h-[70vh] overflow-y-auto">
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
						{#if !goals.length}
							<div class="px-3 py-6 text-center text-xs text-gray-400 dark:text-gray-500">还没有 goal</div>
						{/if}
					</div>

					<!-- 右:会话转录 -->
					<div class="flex-1 min-w-0 rounded-xl border border-gray-100 dark:border-gray-850 p-4 max-h-[70vh] overflow-y-auto">
						{#if !selected}
							<div class="text-sm text-gray-400 dark:text-gray-500 py-12 text-center">← 选一个 goal 查看内部会话</div>
						{:else if convsLoading}
							<div class="text-sm text-gray-400 dark:text-gray-500 py-12 text-center">加载转录…</div>
						{:else if convsError}
							<div class="text-sm text-red-500 dark:text-red-400 py-6 text-center">{convsError}</div>
						{:else if convs}
							<div class="flex flex-wrap gap-1.5 mb-4">
								{#each tabs as t}
									<button
										class="px-2.5 py-1 rounded-full text-[11px] transition {tab === t.id
											? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
											: 'bg-gray-50 dark:bg-gray-900 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
										on:click={() => (tab = t.id)}
									>
										{t.label}
									</button>
								{/each}
							</div>
							<div class="space-y-3">
								{#each activeTranscript ?? [] as m, i}
									<div class="flex {m.role === 'user' ? 'justify-end' : 'justify-start'}">
										<div
											class="max-w-[85%] rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed whitespace-pre-wrap break-words {m.role === 'user'
												? 'bg-gray-900 dark:bg-gray-100 text-gray-50 dark:text-gray-900'
												: 'bg-gray-100 dark:bg-gray-850 text-gray-800 dark:text-gray-200'}"
										>
											{m.text || '(空)'}
										</div>
									</div>
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
