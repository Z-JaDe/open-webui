<script lang="ts">
	// banyan v3 工作空间:以 Agent 维度组织——每个 Agent 一份设计档案。
	// 数据源 = 引擎 Agent md 正本(agents/*.md:七要素 frontmatter + 提示词全文),
	// 经 /banyan/api/agents/{name} 只读取;此处零拷贝、零编辑(正本在引擎)。
	import { onMount } from 'svelte';
	import {
		getBanyanAgent,
		getBanyanStatus,
		type BanyanAgentDesign,
		type BanyanEngineStatus as StatusData
	} from '$lib/apis/banyan';
	import PackListCard from '$lib/components/banyan/PackListCard.svelte';

	let loaded = false;
	let error = '';
	let agents: StatusData['agents'] = [];
	let tiers: StatusData['tiers'] = [];

	let selected = '';
	let design: BanyanAgentDesign | null = null;
	let designLoading = false;
	let designError = '';

	// goal 内核自带工具 + pi 沙箱件(Agent md 之外的工具面)。
	const kernelTools = [
		{ name: 'goal_report', from: 'goal 内核', desc: '报告目标状态 done/blocked' },
		{ name: 'plan_update', from: 'goal 内核', desc: '维护计划文档,每轮回放' },
		{ name: 'subagent', from: 'goal 内核', desc: '常驻子代理 spawn/send/stop/status' },
		{ name: 'read / write / edit / bash', from: 'pi 内建', desc: '工作区沙箱工具' }
	];

	const memoryLabel = (m?: string) =>
		m === 'persistent' ? '持久(跨轮保留)' : m === 'fresh' ? '单轮(用完即弃)' : m ?? '-';
	const outputLabel = (o?: string) =>
		o === 'json' ? 'JSON 契约' : o === 'markdown' ? 'Markdown' : o === 'text' ? '自由文本' : o ?? '-';

	async function selectAgent(name: string) {
		selected = name;
		design = null;
		designError = '';
		designLoading = true;
		try {
			design = await getBanyanAgent(name);
		} catch (e) {
			designError = e instanceof Error ? e.message : String(e);
		}
		designLoading = false;
	}

	onMount(async () => {
		try {
			const status = await getBanyanStatus();
			agents = status.agents ?? [];
			tiers = status.tiers ?? [];
			if (agents.length) await selectAgent(agents[0]!.name);
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
				以 Agent 维度组织——每个 Agent 一份设计档案;正本是引擎 <span class="font-mono">agents/*.md</span>(七要素 + 提示词全文),此处只读零拷贝。
			</p>

			{#if error}
				<div class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
					引擎不可达:{error}
				</div>
			{/if}

			{#if loaded && agents.length}
				<!-- ═══ Agent 维度:列表 + 设计档案 ═══ -->
				<div class="flex flex-col lg:flex-row gap-4 mb-6" data-testid="banyan-workspace-agents">
					<!-- 左:Agent 列表 -->
					<div class="lg:w-56 shrink-0 rounded-xl border border-gray-100 dark:border-gray-850 p-2">
						<div class="text-xs font-medium text-gray-500 dark:text-gray-400 px-2 py-1.5">Agent({agents.length})</div>
						{#each agents as agent (agent.name)}
							<button
								class="w-full text-left px-3 py-2 rounded-lg text-sm transition {selected === agent.name
									? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white font-medium'
									: 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
								on:click={() => selectAgent(agent.name)}
							>
								{agent.name}
								{#if agent.tier}
									<span class="ml-1.5 text-[10px] font-mono text-gray-400 dark:text-gray-500">{agent.tier}</span>
								{/if}
							</button>
						{/each}
					</div>

					<!-- 右:设计档案 -->
					<div class="flex-1 min-w-0 rounded-xl border border-gray-100 dark:border-gray-850 p-4">
						{#if designLoading}
							<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">加载设计档案…</div>
						{:else if designError}
							<div class="text-sm text-red-500 dark:text-red-400 py-4">设计档案不可得:{designError}</div>
						{:else if design}
							<div class="flex items-baseline justify-between mb-3 flex-wrap gap-2">
								<div class="text-base font-semibold text-gray-900 dark:text-white">{design.name}</div>
								<div class="text-xs text-gray-400 dark:text-gray-500">
									档位 <span class="font-mono">{design.tier}</span>
									{#if design.model}· 显式模型 <span class="font-mono">{design.model}</span>{/if}
								</div>
							</div>
							<p class="text-xs text-gray-500 dark:text-gray-400 mb-4">{design.description}</p>

							<!-- 七要素 -->
							<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4 text-[11px]">
								<div class="rounded-lg bg-gray-50 dark:bg-gray-900 p-2">
									<div class="text-gray-400 dark:text-gray-500 mb-0.5">工具({design.tools.length})</div>
									<div class="font-mono text-gray-700 dark:text-gray-300 break-all">{design.tools.join(', ') || '-'}</div>
								</div>
								<div class="rounded-lg bg-gray-50 dark:bg-gray-900 p-2">
									<div class="text-gray-400 dark:text-gray-500 mb-0.5">记忆</div>
									<div class="text-gray-700 dark:text-gray-300">{memoryLabel(design.memory)}</div>
								</div>
								<div class="rounded-lg bg-gray-50 dark:bg-gray-900 p-2">
									<div class="text-gray-400 dark:text-gray-500 mb-0.5">输出</div>
									<div class="text-gray-700 dark:text-gray-300">{outputLabel(design.output)}</div>
								</div>
								<div class="rounded-lg bg-gray-50 dark:bg-gray-900 p-2">
									<div class="text-gray-400 dark:text-gray-500 mb-0.5">运行时提示注入</div>
									<div class="text-gray-700 dark:text-gray-300">{design.runtime_prompts.length ? design.runtime_prompts.join(', ') : '—'}</div>
								</div>
							</div>

							<!-- 提示词全文 -->
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">提示词全文(正本逐字)</div>
							<pre class="text-[11.5px] leading-relaxed text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 rounded-lg p-3 whitespace-pre-wrap break-words max-h-[32rem] overflow-y-auto">{design.prompt}</pre>
						{/if}
					</div>
				</div>

				<!-- ═══ 附:内核工具面 + 档位 ═══ -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
					<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4" data-testid="banyan-workspace-kernel-tools">
						<div class="text-sm font-medium text-black dark:text-white mb-3">goal 内核与沙箱件(Agent md 之外)</div>
						<div class="space-y-1.5">
							{#each kernelTools as kt}
								<div class="text-[11px] flex gap-2">
									<span class="font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{kt.name}</span>
									<span class="text-gray-400 dark:text-gray-500">— {kt.from} · {kt.desc}</span>
								</div>
							{/each}
						</div>
					</div>
					<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4" data-testid="banyan-workspace-tiers">
						<div class="text-sm font-medium text-black dark:text-white mb-3">模型档位(引擎 cfg.tiers)</div>
						<div class="overflow-x-auto">
							<table class="w-full text-left text-xs">
								<thead>
									<tr class="text-gray-400 dark:text-gray-500">
										<th class="py-1 pr-3 font-medium">档位</th>
										<th class="py-1 pr-3 font-medium">模型</th>
										<th class="py-1 pr-3 font-medium">密钥</th>
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
