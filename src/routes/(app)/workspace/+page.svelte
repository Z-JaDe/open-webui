<script lang="ts">
	// banyan v3 工作空间:D24 五面退役后,这里重生为 banyan 的运行资产面——
	// Agent 花名册(引擎 agents/*.md)/ 工具聚合(花名册∪goal 内核工具)/ 模型档位 / 场景包。
	// 身份与界面偏好仍在 webui.db;业务正本在引擎与知识仓(零拷贝,只读投影)。
	import { onMount } from 'svelte';
	import { getBanyanStatus, type BanyanEngineStatus as StatusData } from '$lib/apis/banyan';
	import PackListCard from '$lib/components/banyan/PackListCard.svelte';

	let loaded = false;
	let error = '';
	let home = '';
	let agents: StatusData['agents'] = [];
	let tiers: StatusData['tiers'] = [];

	// goal 内核(pi-goal)自带工具 + pi 内建沙箱件——与花名册聚合后即全系统工具面。
	const kernelTools = [
		{ name: 'goal_report', from: 'goal 内核(管理者收口)', desc: '报告目标状态 done/blocked' },
		{ name: 'plan_update', from: 'goal 内核(注意力锚)', desc: '维护计划文档,每轮回放' },
		{ name: 'subagent', from: 'goal 内核(常驻子代理)', desc: 'spawn/send/stop/status,答案自动回流' },
		{ name: 'read / write / edit / bash', from: 'pi 内建(CodingTools)', desc: '工作区沙箱工具' }
	];

	const memoryLabel = (m?: string) =>
		m === 'persistent' ? '持久' : m === 'fresh' ? '单轮' : m ?? '-';

	$: rosterTools = Array.from(new Set(agents.flatMap((a) => a.tools ?? []))).sort();

	onMount(async () => {
		try {
			const status = await getBanyanStatus();
			home = status.engine.home ?? '';
			agents = status.agents ?? [];
			tiers = status.tiers ?? [];
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>工作空间</title>
</svelte:head>

<div class="flex flex-col h-full min-h-0 w-full max-w-full">
	<div class="flex-1 overflow-y-auto">
		<div class="max-w-full mx-auto w-full px-4 py-8">
			<div class="flex items-center gap-2 mb-1">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[11px] font-semibold text-gray-700 dark:text-gray-200"
				>
					W
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">工作空间</h1>
			</div>
			<p class="text-xs text-gray-400 dark:text-gray-500 mb-6">
				运行资产只读投影——Agent 正本在 <span class="font-mono">{home || '引擎'}/agents/</span>,知识/技能正本在知识仓;此处零拷贝。
			</p>

			{#if error}
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
					引擎不可达:{error}
				</div>
			{/if}

			{#if loaded && agents.length}
				<!-- ═══ Agent 花名册 ═══ -->
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mb-6" data-testid="banyan-workspace-agents">
					<div class="text-sm font-medium text-black dark:text-white mb-3">Agent 花名册({agents.length})</div>
					<div class="overflow-x-auto">
						<table class="w-full text-left text-xs">
							<thead>
								<tr class="text-gray-400 dark:text-gray-500">
									<th class="py-1 pr-3 font-medium">名字</th>
									<th class="py-1 pr-3 font-medium">职责</th>
									<th class="py-1 pr-3 font-medium">档位</th>
									<th class="py-1 pr-3 font-medium">工具</th>
									<th class="py-1 pr-3 font-medium">记忆</th>
									<th class="py-1 font-medium">输出</th>
								</tr>
							</thead>
							<tbody>
								{#each agents as agent (agent.name)}
									<tr class="border-t border-gray-100 dark:border-gray-850 align-top">
										<td class="py-1.5 pr-3 text-black dark:text-white whitespace-nowrap">{agent.name}</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400 max-w-[18rem]">{agent.description || '-'}</td>
										<td class="py-1.5 pr-3 font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{agent.tier ?? '-'}</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">{agent.tools?.length ? agent.tools.join(', ') : '-'}</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400 whitespace-nowrap">{memoryLabel(agent.memory)}</td>
										<td class="py-1.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">{agent.output ?? '-'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>

				<!-- ═══ 工具聚合 ═══ -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
					<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4" data-testid="banyan-workspace-tools">
						<div class="text-sm font-medium text-black dark:text-white mb-3">Agent 工具(花名册聚合,{rosterTools.length})</div>
						<div class="flex flex-wrap gap-1.5">
							{#each rosterTools as t}
								<span class="rounded-md bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 px-2 py-1 text-[11px] font-mono text-gray-600 dark:text-gray-400">{t}</span>
							{/each}
						</div>
						<p class="text-[11px] text-gray-400 dark:text-gray-500 mt-2">工具面随 Agent 定义变化;HTTP 回调工具(open_ticket 等)由引擎注册表按运行下发。</p>
					</div>
					<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4" data-testid="banyan-workspace-kernel-tools">
						<div class="text-sm font-medium text-black dark:text-white mb-3">goal 内核与沙箱件(pi-goal / pi)</div>
						<div class="space-y-1.5">
							{#each kernelTools as kt}
								<div class="text-[11px] flex gap-2">
									<span class="font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{kt.name}</span>
									<span class="text-gray-400 dark:text-gray-500">— {kt.from} · {kt.desc}</span>
								</div>
							{/each}
						</div>
					</div>
				</div>

				<!-- ═══ 模型档位 ═══ -->
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mb-6" data-testid="banyan-workspace-tiers">
					<div class="text-sm font-medium text-black dark:text-white mb-3">模型档位(引擎 cfg.tiers)</div>
					<div class="overflow-x-auto">
						<table class="w-full text-left text-xs">
							<thead>
								<tr class="text-gray-400 dark:text-gray-500">
									<th class="py-1 pr-3 font-medium">档位</th>
									<th class="py-1 pr-3 font-medium">模型</th>
									<th class="py-1 pr-3 font-medium">已配密钥</th>
									<th class="py-1 font-medium">默认</th>
								</tr>
							</thead>
							<tbody>
								{#each tiers as t (t.id)}
									<tr class="border-t border-gray-100 dark:border-gray-850">
										<td class="py-1.5 pr-3 text-black dark:text-white">{t.id}</td>
										<td class="py-1.5 pr-3 font-mono text-gray-700 dark:text-gray-300">{t.model}</td>
										<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">{t.keyed ? '✓' : '—'}</td>
										<td class="py-1.5 text-gray-500 dark:text-gray-400">{t.default ? '✓' : '—'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>

				<!-- ═══ 场景包 ═══ -->
				<div class="mb-2">
					<PackListCard />
				</div>
			{:else if loaded}
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 text-sm text-gray-400 dark:text-gray-500">
					{error ? '状态不可得' : '花名册不可得(引擎未返回 agents)'}
				</div>
			{/if}
		</div>
	</div>
</div>
