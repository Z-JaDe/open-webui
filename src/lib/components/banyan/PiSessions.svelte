<!--
	banyan /arch · sidecar Pi 会话区块(F15 / D28 会话可见性,只读)。
	数据源 = /banyan/api/pi/sessions(fork 代理桥 → 引擎只读代理 sidecar
	GET /sessions | /sessions/{sid}/tree):手工 Pi 会话/休眠会话经此可见。
	K1 镜像仍是会话正本——本区块零写操作,展开行才按需拉会话树。
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { BANYAN_API_BASE_URL } from '$lib/apis/banyan';

	const i18n = getContext<Writable<i18nType>>('i18n');

	type PiSession = {
		id: string;
		status?: string;
		workspace?: string;
		cwd?: string;
		updated_at?: number;
		created_at?: number;
	};
	type PiNode = {
		id?: string;
		role?: string;
		type?: string;
		text?: string;
		content?: string;
		children?: PiNode[];
	};
	type FlatNode = { depth: number; id: string; label: string; head: string };

	let sessions: PiSession[] = [];
	let loaded = false;
	let error = '';
	let expanded = '';
	let tree: FlatNode[] = [];
	let treeLoading = false;

	// 引擎响应形状容错:裸数组 | {items} | {sessions}
	const asArray = (v: any): any[] =>
		Array.isArray(v) ? v : Array.isArray(v?.items) ? v.items : Array.isArray(v?.sessions) ? v.sessions : [];

	const request = async (path: string) => {
		const res = await fetch(`${BANYAN_API_BASE_URL}${path}`, {
			headers: { Authorization: `Bearer ${localStorage.token}` }
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body?.detail ?? `${res.status} ${res.statusText}`);
		}
		return res.json();
	};

	const workspaceTail = (session: PiSession): string =>
		String(session.workspace ?? session.cwd ?? '').split('/').filter(Boolean).pop() ?? '';

	const when = (session: PiSession): number | undefined => {
		const ts = session.updated_at ?? session.created_at;
		return typeof ts === 'number' && ts > 0 ? (ts > 1e12 ? ts : ts * 1000) : undefined;
	};

	// 会话树 → 先序扁平(id + role/type + 文本头 60 字),缩进即深度
	const flatten = (nodes: PiNode[], depth = 0, out: FlatNode[] = []): FlatNode[] => {
		for (const node of Array.isArray(nodes) ? nodes : [nodes]) {
			if (!node || typeof node !== 'object') continue;
			const text = String(node.text ?? node.content ?? '');
			out.push({
				depth,
				id: String(node.id ?? ''),
				label: String(node.role ?? node.type ?? ''),
				head: text.length > 60 ? `${text.slice(0, 60)}…` : text
			});
			if (node.children?.length) flatten(node.children, depth + 1, out);
		}
		return out;
	};

	const toggleTree = async (session: PiSession) => {
		if (expanded === session.id) {
			expanded = '';
			tree = [];
			return;
		}
		expanded = session.id;
		treeLoading = true;
		tree = [];
		try {
			tree = flatten(asArray(await request(`/pi/sessions/${session.id}/tree`)));
		} catch (e) {
			tree = [];
			error = `${e}`;
		}
		treeLoading = false;
	};

	onMount(async () => {
		try {
			sessions = asArray(await request('/pi/sessions'));
		} catch (e) {
			error = `${e}`;
		}
		loaded = true;
	});
</script>

<div class="text-xs">
	{#if !loaded}
		<div class="text-gray-500 dark:text-gray-400">{$i18n.t('Loading…')}</div>
	{:else if error && sessions.length === 0}
		<div class="text-gray-500 dark:text-gray-400">{$i18n.t('Engine unreachable')}: {error}</div>
	{:else if sessions.length === 0}
		<div class="text-gray-500 dark:text-gray-400">{$i18n.t('No Pi sessions')}</div>
	{:else}
		<ul class="divide-y divide-gray-100 dark:divide-gray-850">
			{#each sessions as session (session.id)}
				<li>
					<button
						type="button"
						class="w-full flex items-center gap-2 py-1.5 text-left hover:bg-gray-50 dark:hover:bg-gray-900 rounded px-1 -mx-1"
						on:click={() => toggleTree(session)}
					>
						<span
							class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium {'live' === (session.status ?? '').toLowerCase()
								? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
								: 'busy' === (session.status ?? '').toLowerCase()
									? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
									: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'}"
						>
							{session.status || $i18n.t('idle')}
						</span>
						<span class="font-mono text-gray-800 dark:text-gray-200 truncate">{session.id}</span>
						{#if workspaceTail(session)}
							<span class="text-gray-500 dark:text-gray-400 truncate">{workspaceTail(session)}</span>
						{/if}
						{#if when(session)}
							<span class="ml-auto shrink-0 text-gray-400">
								{new Date(when(session)!).toLocaleString()}
							</span>
						{/if}
					</button>
					{#if expanded === session.id}
						<div class="py-1 pl-3 border-l border-gray-100 dark:border-gray-850 ml-2">
							{#if treeLoading}
								<div class="text-gray-400">{$i18n.t('Loading…')}</div>
							{:else if tree.length === 0}
								<div class="text-gray-400">{$i18n.t('Empty')}</div>
							{:else}
								{#each tree as node}
									<div class="flex gap-1.5 py-0.5" style="padding-left: {node.depth * 12}px">
										<span class="font-mono text-gray-400 shrink-0">{node.id}</span>
										<span class="text-gray-500 dark:text-gray-400 shrink-0">[{node.label}]</span>
										<span class="text-gray-800 dark:text-gray-200 break-all">{node.head}</span>
									</div>
								{/each}
							{/if}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>
