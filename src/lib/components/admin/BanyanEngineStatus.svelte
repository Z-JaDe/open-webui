<!--
	BanyanEngineStatus（v3 W4，hook④；V-10）
	只读状态卡：GET /banyan/api/status（代理桥 → 引擎聚合 sidecar 健康，30s 缓存）。
	渲染：引擎健康 / sidecar 健康 / 档位表 / 信箱计数；加载失败显示"引擎不可达"。
	全部禁写——本组件不发任何非 GET 请求。
-->
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';

	import type i18nType from '$lib/i18n';
	import { getBanyanStatus, type BanyanEngineStatus } from '$lib/apis/banyan';

	const i18n = getContext<Writable<i18nType>>('i18n');

	let loaded = false;
	let status: BanyanEngineStatus | null = null;
	let error: string | null = null;

	const engineHealthy = (s: BanyanEngineStatus) => s.engine.status === 'running' || s.engine.status === 'ok';

	const fmtRoles = (roles?: string[] | Record<string, any>) => {
		if (!roles) return '';
		if (Array.isArray(roles)) return roles.join(', ');
		return Object.keys(roles).join(', ');
	};

	onMount(async () => {
		status = await getBanyanStatus().catch((e) => {
			error = `${e}`;
			return null;
		});
		loaded = true;
	});
</script>

<div class="space-y-4 text-xs">
	{#if !loaded}
		<div class="text-gray-500 dark:text-gray-400">{$i18n.t('Loading')}…</div>
	{:else if error || !status}
		<!-- 引擎不可达是常态（V-10），明确展示、不静默伪造 -->
		<div
			class="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-red-600 dark:text-red-400"
		>
			{$i18n.t('Engine unreachable')}
			{#if error}<span class="block mt-1 text-[11px] opacity-70">{error}</span>{/if}
		</div>
	{:else}
		<!-- 引擎健康 -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 space-y-1.5">
			<div class="flex items-center gap-2">
				<span
					class="size-2 rounded-full {engineHealthy(status) && !status.engine.paused
						? 'bg-green-500'
						: 'bg-gray-400'}"
				></span>
				<span class="text-sm font-medium text-black dark:text-white">{$i18n.t('Engine')}</span>
				<span class="text-gray-500 dark:text-gray-400">
					{status.engine.status}{status.engine.paused ? ` · ${$i18n.t('paused')}` : ''}
					{status.engine.version ? ` · v${status.engine.version}` : ''}
				</span>
			</div>
			{#if status.engine.workspace || status.engine.home}
				<div class="text-gray-400 dark:text-gray-500 break-all">
					{[status.engine.workspace, status.engine.home].filter(Boolean).join(' · ')}
				</div>
			{/if}
		</div>

		<!-- sidecar 健康（引擎侧 30s 缓存聚合；不可达={ok:false}，不 500） -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 space-y-1.5">
			<div class="flex items-center gap-2">
				<span class="size-2 rounded-full {status.sidecar.ok ? 'bg-green-500' : 'bg-red-400'}"></span>
				<span class="text-sm font-medium text-black dark:text-white">{$i18n.t('Sidecar')}</span>
				<span class="text-gray-500 dark:text-gray-400">
					{status.sidecar.ok ? $i18n.t('healthy') : $i18n.t('unreachable')}
					{#if status.sidecar.ok && fmtRoles(status.sidecar.roles)}
						· {fmtRoles(status.sidecar.roles)}
					{/if}
				</span>
			</div>
		</div>

		<!-- 档位表（W1：档位即模型，引擎侧供血；只读展示） -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 space-y-2">
			<div class="text-sm font-medium text-black dark:text-white">{$i18n.t('Tiers')}</div>
			{#if status.tiers.length}
				<div class="overflow-x-auto">
					<table class="w-full text-left">
						<thead>
							<tr class="text-gray-400 dark:text-gray-500">
								<th class="py-1 pr-3 font-medium">{$i18n.t('Tier')}</th>
								<th class="py-1 pr-3 font-medium">{$i18n.t('Model')}</th>
								<th class="py-1 pr-3 font-medium">{$i18n.t('Keyed')}</th>
								<th class="py-1 font-medium">{$i18n.t('Default')}</th>
							</tr>
						</thead>
						<tbody>
							{#each status.tiers as tier (tier.id)}
								<tr class="border-t border-gray-100 dark:border-gray-850">
									<td class="py-1.5 pr-3 text-black dark:text-white">
										{tier.label ?? tier.id}
										{#if tier.desc}<span class="block text-[11px] text-gray-400">{tier.desc}</span>{/if}
									</td>
									<td class="py-1.5 pr-3 text-gray-500 dark:text-gray-400">{tier.model ?? '-'}</td>
									<td class="py-1.5 pr-3">{tier.keyed ? '✓' : '—'}</td>
									<td class="py-1.5">{tier.default ? '✓' : '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="text-gray-400 dark:text-gray-500">{$i18n.t('No tiers registered')}</div>
			{/if}
		</div>

		<!-- 信箱计数（徽标正本在 Sidebar；此处为只读聚合展示） -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 space-y-2">
			<div class="text-sm font-medium text-black dark:text-white">{$i18n.t('Inbox')}</div>
			<div class="flex items-center gap-4 text-gray-500 dark:text-gray-400">
				<span>{$i18n.t('Pending decisions')}: <b class="text-black dark:text-white">{status.counts.inbox.decision}</b></span>
				<span>{$i18n.t('Completed')}: <b class="text-black dark:text-white">{status.counts.inbox.done}</b></span>
				<span>{$i18n.t('Notices')}: <b class="text-black dark:text-white">{status.counts.inbox.notice}</b></span>
			</div>
			<div class="text-gray-500 dark:text-gray-400">
				{$i18n.t('Plans running')}: <b class="text-black dark:text-white">{status.counts.plans_running}</b>
			</div>
		</div>
	{/if}
</div>
