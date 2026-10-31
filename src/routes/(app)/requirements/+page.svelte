<script lang="ts">
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import {
		listBanyanRequirements,
		createBanyanRequirement,
		updateBanyanRequirement,
		REQ_STATUS_COLORS,
		REQ_STATUS_LABELS,
		type BanyanRequirement
	} from '$lib/apis/banyan';

	let reqs: BanyanRequirement[] = [];
	let loaded = false;
	let error = '';
	let newTitle = '';
	let selected: BanyanRequirement | null = null;
	let dead = false;
	let timer: ReturnType<typeof setInterval> | undefined;

	async function refresh() {
		try {
			reqs = await listBanyanRequirements();
			error = '';
		} catch (e: any) {
			error = e?.message?.slice(0, 80) ?? '加载失败';
		}
	}

	async function create() {
		if (!newTitle.trim()) return;
		try {
			await createBanyanRequirement(newTitle.trim());
			newTitle = '';
			await refresh();
		} catch (e: any) {
			error = e?.message?.slice(0, 80) ?? '创建失败';
		}
	}

	async function setStatus(
		id: string,
		status: 'open' | 'in_progress' | 'blocked' | 'done' | 'dropped'
	) {
		try {
			await updateBanyanRequirement(id, { status });
			await refresh();
		} catch (e: any) {
			error = e?.message?.slice(0, 80) ?? '更新失败';
		}
	}

	// 构建树视图(父子关系)
	$: roots = reqs.filter((r) => !r.parent_id);
	$: childrenOf = (pid: string) => reqs.filter((r) => r.parent_id === pid);
	$: goalIdsOf = (r: BanyanRequirement) => {
		try {
			return JSON.parse(r.goal_ids || '[]') as string[];
		} catch {
			return [];
		}
	};

	onMount(() => {
		void (async () => {
			await refresh();
			if (!dead) loaded = true;
		})();
		timer = setInterval(() => {
			if (!dead) void refresh();
		}, 30_000);
		return () => {
			dead = true;
			if (timer) clearInterval(timer);
		};
	});
</script>

<svelte:head>
	<title>需求树</title>
</svelte:head>

<div class="flex flex-col h-full min-h-0 w-full max-w-full transition-width duration-200 ease-in-out {$showSidebar ? 'sm:ml-64' : ''} max-w-full">
	<div class="flex-1 overflow-y-auto p-4 sm:p-6 max-w-4xl mx-auto w-full">
		<h1 class="text-2xl font-bold mb-4">需求树</h1>

		{#if error}
			<div class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 mb-4">
				{error}
				<button class="underline ml-2" on:click={() => void refresh()}>重试</button>
			</div>
		{/if}

		<div class="flex gap-2 mb-6">
			<input
				class="flex-1 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-base min-h-11 dark:border-gray-700 dark:bg-gray-900"
				placeholder="新需求标题..."
				bind:value={newTitle}
				on:keydown={(e) => e.key === 'Enter' && create()}
			/>
			<button
				class="rounded-xl bg-gray-900 text-white px-5 py-2.5 text-base font-medium min-h-11 dark:bg-white dark:text-black"
				on:click={create}>创建</button
			>
		</div>

		{#if !loaded}
			<div class="text-center text-gray-400 py-12">加载中...</div>
		{:else if reqs.length === 0}
			<div class="text-center text-gray-400 py-12 border border-dashed border-gray-200 rounded-xl dark:border-gray-800">
				暂无需求——气根 Agent 通过 req_create 录入
			</div>
		{:else}
			<div class="space-y-3">
				{#each roots as root (root.id)}
					<div class="rounded-xl border border-gray-100 dark:border-gray-800 p-4">
						<div
							class="flex items-center justify-between w-full text-left cursor-pointer"
							on:click={() => (selected = selected?.id === root.id ? null : root)}
							on:keydown={(e) => e.key === 'Enter' && (selected = selected?.id === root.id ? null : root)}
							role="button"
							tabindex="0"
						>
							<div class="flex-1 min-w-0">
								<div class="font-medium truncate">{root.title}</div>
								<div class="text-xs text-gray-400 mt-0.5 flex gap-2 items-center flex-wrap">
									<span class={REQ_STATUS_COLORS[root.status] ?? ''}>{REQ_STATUS_LABELS[root.status] ?? root.status}</span>
									{#if root.blocked_by}
										<span class="text-red-400">← 阻塞于 {root.blocked_by}</span>
									{/if}
									{#each goalIdsOf(root) as gid}
										<span class="text-blue-400 font-mono text-[10px]">{gid}</span>
									{/each}
								</div>
							</div>
							<div class="flex gap-1 ml-3 shrink-0">
								{#if root.status !== 'done'}
									<button
										class="text-xs px-2 py-1 rounded bg-green-50 text-green-600 dark:bg-green-950"
										on:click|stopPropagation={() => setStatus(root.id, 'done')}>完成</button
									>
								{/if}
								{#if root.status === 'open'}
									<button
										class="text-xs px-2 py-1 rounded bg-blue-50 text-blue-600 dark:bg-blue-950"
										on:click|stopPropagation={() => setStatus(root.id, 'in_progress')}>开始</button
									>
								{/if}
								{#if root.status !== 'dropped' && root.status !== 'done'}
									<button
										class="text-xs px-2 py-1 rounded bg-gray-50 text-gray-500 dark:bg-gray-800"
										on:click|stopPropagation={() => setStatus(root.id, 'dropped')}>放弃</button
									>
								{/if}
							</div>
						</div>

						{#if selected?.id === root.id}
							<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-sm text-gray-600 dark:text-gray-400">
								{root.detail || '(无描述)'}
								<div class="text-xs text-gray-400 mt-2">
									ID: {root.id} · 创建于 {new Date(root.created_at * 1000).toLocaleDateString()}
								</div>
							</div>
						{/if}

						{#if childrenOf(root.id).length > 0}
							<div class="mt-3 pl-4 border-l-2 border-gray-100 dark:border-gray-800 space-y-2">
								{#each childrenOf(root.id) as child (child.id)}
									<div class="flex items-center justify-between text-sm">
										<div class="flex-1 min-w-0">
											<span class="truncate">{child.title}</span>
											<span class="text-xs {REQ_STATUS_COLORS[child.status] ?? ''} ml-2">{REQ_STATUS_LABELS[child.status] ?? child.status}</span>
											{#each goalIdsOf(child) as gid}
												<span class="text-blue-400 font-mono text-[10px] ml-1">{gid}</span>
											{/each}
										</div>
										<div class="flex gap-1 ml-2 shrink-0">
											{#if child.status !== 'done'}
												<button
													class="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600"
													on:click={() => setStatus(child.id, 'done')}>✓</button
												>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
