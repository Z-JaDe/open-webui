<script lang="ts">
	// /devices — 设备互感知(C3,goal-cloud 协议锁定):同账号名下节点清单 + 指挥下发。
	// 数据源 /banyan/api/nodes*(通配桥 → 云引擎);webui 用户 JWT 墙(登录即可见,与 workspaces 同口径)。
	// 指令 = 封闭集 chat_turn|goal_card_resolve|goal_abort,入队后经节点心跳搭车取走(异步,页面只示「已入队」)。
	// 注册 node_token 只显示一次(引擎库存 hash,不可再查)——不落 localStorage、不进日志。
	import { onMount } from 'svelte';
	import { showSidebar } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import {
		listBanyanNodes,
		listBanyanNodeCommands,
		registerBanyanNode,
		sendBanyanNodeCommand,
		deleteBanyanNode,
		formatNodeHeartbeatAge,
		isNodeOnline,
		nodeSpaces,
		nodeStatusSummary,
		type BanyanNodeCommandEntry,
		type BanyanNodeInfo,
		type BanyanNodeCommandKind,
		type BanyanNodeRegisterResult
	} from '$lib/apis/banyan';

	let loaded = false;
	let error = '';
	let nodes: BanyanNodeInfo[] = [];
	/** 指令历史(RF-C3c F-3 回执可见面):node_id → 最近指令,随列表 30s 刷新 */
	let cmdHistory: Record<string, BanyanNodeCommandEntry[]> = {};

	// ── 注册流(node_token 只此一次)──
	let showAdd = false;
	let newName = '';
	let registering = false;
	let newToken: BanyanNodeRegisterResult | null = null; // 唯一持有处;关闭即焚,不落存
	let tokenCopied = false;

	// ── 指令下发(节点卡内联小面板;同一时刻只开一张卡)──
	let cmdNodeId = '';
	let cmdKind: BanyanNodeCommandKind = 'chat_turn';
	let cmdText = '';
	let cmdSpaceId = ''; // RF-C3c F-1:可选空间(节点上报目录;''=目标节点默认会话)
	let cmdCardId = '';
	let cmdCardDecision: 'approved' | 'rejected' = 'approved';
	let cmdGoalId = '';
	let sending = false;

	// ── 删除(两步内联确认,不引新弹窗件)──
	let confirmDeleteId = '';
	let deleting = false;

	async function refresh() {
		try {
			nodes = await listBanyanNodes();
			error = ''; // F14 同款:成功清 error,失败横幅不跨刷新滞留
			// 指令历史随列表拉(F-3):逐节点读面,单节点失败不拖垮列表(保留旧值)
			const fetched: Record<string, BanyanNodeCommandEntry[]> = {};
			await Promise.all(
				nodes.map(async (n) => {
					try {
						fetched[n.node_id] = await listBanyanNodeCommands(n.node_id);
					} catch {
						fetched[n.node_id] = cmdHistory[n.node_id] ?? [];
					}
				})
			);
			cmdHistory = fetched;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	const online = (n: BanyanNodeInfo) => isNodeOnline(n.online, n.last_heartbeat);
	const heartbeatAge = (n: BanyanNodeInfo) => formatNodeHeartbeatAge(n.last_heartbeat);
	const registeredAt = (n: BanyanNodeInfo) =>
		n.created_at ? new Date(n.created_at).toLocaleString() : '—';
	const history = (n: BanyanNodeInfo) => cmdHistory[n.node_id] ?? [];

	async function addDevice() {
		const name = newName.trim();
		if (!name || registering) return;
		registering = true;
		try {
			newToken = await registerBanyanNode(name); // 只此一次回显
			tokenCopied = false;
			newName = '';
			showAdd = false;
			toast.success('设备已注册,请立即保存令牌(只显示这一次)');
			await refresh();
		} catch (e) {
			toast.error(e instanceof Error ? e.message : String(e));
		}
		registering = false;
	}

	const closeTokenPanel = () => {
		newToken = null; // 即焚:此后任何人(含本页)无法再取回
	};

	async function copyToken() {
		if (!newToken) return;
		try {
			await navigator.clipboard.writeText(newToken.node_token);
			tokenCopied = true;
		} catch {
			toast.error('复制失败——请手动选中复制');
		}
	}

	function openCommand(n: BanyanNodeInfo) {
		if (cmdNodeId === n.node_id) {
			cmdNodeId = '';
			return;
		}
		cmdNodeId = n.node_id;
		cmdKind = 'chat_turn';
		cmdText = '';
		cmdSpaceId = '';
		cmdCardId = '';
		cmdCardDecision = 'approved';
		cmdGoalId = '';
	}

	const cmdTarget = () => nodes.find((n) => n.node_id === cmdNodeId) ?? null;

	async function sendCommand() {
		const n = cmdTarget();
		if (!n || sending) return;
		// 载荷按 C3 协议(chat_turn 文本+可选 space_id/goal_card_resolve 卡 id+裁决/goal_abort goal id)
		let payload: Record<string, unknown>;
		if (cmdKind === 'chat_turn') {
			if (!cmdText.trim()) return;
			// F-1:选中空间才带 space_id(未选/无目录 → 只有 text,走目标节点默认会话;
			// 默认会话未绑空间时引擎诚实失败回执,见「指令历史」)
			payload = cmdSpaceId
				? { text: cmdText.trim(), space_id: cmdSpaceId }
				: { text: cmdText.trim() };
		} else if (cmdKind === 'goal_card_resolve') {
			if (!cmdCardId.trim()) return;
			payload = { card_id: cmdCardId.trim(), decision: cmdCardDecision };
		} else {
			if (!cmdGoalId.trim()) return;
			payload = { goal_id: cmdGoalId.trim() };
		}
		sending = true;
		try {
			const { command_id } = await sendBanyanNodeCommand(n.node_id, cmdKind, payload);
			// F-3/F-8:回执现在有可见面(节点卡「指令历史」),文案与实际能力对齐;
			// 心跳节拍=60s 挂 15s 关节(实际约一分钟)
			const where = command_id ? `(${command_id.slice(0, 12)}…)` : '';
			toast.success(`已入队${where}——节点下次心跳(约一分钟)取走,回执见节点卡「指令历史」`);
			cmdNodeId = '';
			cmdText = '';
			cmdSpaceId = '';
			cmdCardId = '';
			cmdGoalId = '';
		} catch (e) {
			toast.error(e instanceof Error ? e.message : String(e));
		}
		sending = false;
	}

	async function removeDevice(n: BanyanNodeInfo) {
		if (confirmDeleteId !== n.node_id || deleting) return;
		deleting = true;
		try {
			await deleteBanyanNode(n.node_id);
			toast.success(`已删除 ${n.name}(其 node_token 即时失效)`);
			confirmDeleteId = '';
			if (cmdNodeId === n.node_id) cmdNodeId = '';
			await refresh();
		} catch (e) {
			toast.error(e instanceof Error ? e.message : String(e));
		}
		deleting = false;
	}

	onMount(() => {
		// W5/RF2-D 竞态纪律:组件在 await refresh() 完成前被销毁时,cleanup 跑在
		// setInterval 赋值之前(clearInterval 捕获 undefined 无操作),IIFE 随后
		// 仍会 setInterval → 已销毁组件每 30s 轮询永不回收。dead 标志封死该窗口。
		let timer: ReturnType<typeof setInterval> | undefined;
		let dead = false;
		void (async () => {
			await refresh();
			loaded = true;
			if (!dead) timer = setInterval(refresh, 30000);
		})();
		return () => {
			dead = true;
			clearInterval(timer);
		};
	});

	const CMD_KINDS: { id: BanyanNodeCommandKind; label: string }[] = [
		{ id: 'chat_turn', label: '发一句话' },
		{ id: 'goal_card_resolve', label: '处置人审卡' },
		{ id: 'goal_abort', label: '中止 goal' }
	];

	const kindLabel = (k: string) => CMD_KINDS.find((x) => x.id === k)?.label ?? k;

	// 指令历史 state 四态(引擎 GET /commands 投影)→ 徽标文案/配色
	const STATE_LABELS: Record<string, string> = {
		pending: '待取走',
		claimed: '已取走',
		done: '已回执',
		expired: '已过期'
	};
	const STATE_BADGES: Record<string, string> = {
		pending: 'bg-gray-100 dark:bg-gray-850 text-gray-500 dark:text-gray-400',
		claimed: 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400',
		done: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400',
		expired: 'bg-red-50 dark:bg-red-950/40 text-red-500 dark:text-red-400'
	};
	const stateLabel = (s: string) => STATE_LABELS[s] ?? s;
	const stateBadgeClass = (s: string) => STATE_BADGES[s] ?? STATE_BADGES.pending;
</script>

<svelte:head>
	<title>设备 · banyan</title>
</svelte:head>

<div
	class="flex flex-col h-full min-h-0 w-full max-w-full transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<div class="flex-1 overflow-y-auto">
		<!-- 手机响应式:safe-area 下沿(viewport-fit=cover 下刘海屏内容不贴边) -->
		<div class="max-w-4xl mx-auto w-full px-4 pt-8 pb-[max(2rem,env(safe-area-inset-bottom))]">
			<div class="flex items-center gap-2 mb-1">
				<div
					class="self-center flex size-7 shrink-0 items-center justify-center rounded-lg bg-black/[0.045] dark:bg-white/[0.06] text-[13px]"
				>
					📱
				</div>
				<h1 class="text-xl font-semibold text-gray-900 dark:text-white">设备</h1>
				<div class="ml-auto flex items-center gap-2">
					<button
						type="button"
						class="min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 transition"
						on:click={() => {
							showAdd = !showAdd;
							if (!showAdd) newName = '';
						}}
					>
						{showAdd ? '收起' : '添加设备'}
					</button>
				</div>
			</div>
			<p class="text-xs text-gray-400 dark:text-gray-500 mb-6">
				账号名下已接入的节点(本地 Mac / 云端);心跳约每分钟一次、180s
				未到判离线;指令入队后随节点下次心跳送达,回执见各节点卡「指令历史」。
			</p>

			{#if error}
				<!-- F14 同款:失败态不与空态并显——引擎不可达时只出错误横幅(带重试) -->
				<div
					class="rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400 mb-6"
				>
					引擎不可达:{error?.slice(0, 120)}
					<button
						type="button"
						class="ml-2 underline underline-offset-2 hover:opacity-70"
						on:click={() => refresh()}
					>
						重试
					</button>
				</div>
			{/if}

			<!-- 注册流:node_token 只此一次(复制按钮 + 不可再查警示;关闭即焚) -->
			{#if newToken}
				<div
					class="rounded-xl border border-amber-300/60 dark:border-amber-600/40 bg-amber-50 dark:bg-amber-950/20 p-4 mb-6 space-y-3"
					data-testid="banyan-node-token-panel"
				>
					<div class="text-sm font-semibold text-amber-700 dark:text-amber-400">
						设备令牌只显示这一次——关闭后不可再查(引擎只存 hash)
					</div>
					<!-- RF-C3c F-4:完整三键接线指引(URL 形态此前只活在运维侧 state.md,
					     注册者看不到,裸域名会打错路径);整块可选中复制 -->
					<div class="text-xs text-gray-600 dark:text-gray-300">
						把以下三行写进该设备的 <code class="font-mono">~/.banyan/cloud.env</code>
						(三键齐全才上报;令牌即下方这一个):
					</div>
					<pre
						class="text-[11px] leading-5 font-mono bg-white dark:bg-gray-900 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2.5 break-all whitespace-pre-wrap select-all"
						data-testid="banyan-node-cloud-env-guide">BANYAN_CLOUD_URL=https://banyan.pyrris.com/engine
BANYAN_NODE_ID={newToken.node_id}
BANYAN_NODE_TOKEN={newToken.node_token}</pre>
					<div class="text-[11px] text-gray-400 dark:text-gray-500">
						URL 必须带 <code class="font-mono">/engine</code> 路径(节点直连引擎的 Caddy 入口);
						保存后无需重启(下一拍自动热载)。
					</div>
					<div class="flex items-center gap-2">
						<code
							class="flex-1 min-w-0 font-mono text-xs bg-white dark:bg-gray-900 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2.5 break-all select-all"
						>
							{newToken.node_token}
						</code>
						<button
							type="button"
							class="min-h-11 md:min-h-0 shrink-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg border border-amber-300 dark:border-amber-700 hover:bg-amber-100 dark:hover:bg-amber-900/40 transition"
							on:click={copyToken}
						>
							{tokenCopied ? '已复制' : '复制'}
						</button>
					</div>
					<button
						type="button"
						class="w-full min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg bg-gray-900 text-white dark:bg-white dark:text-black hover:opacity-80 transition"
						on:click={closeTokenPanel}
					>
						我已保存,关闭(令牌即焚)
					</button>
				</div>
			{/if}

			{#if showAdd && !newToken}
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 mb-6 space-y-3">
					<div class="text-sm font-medium text-gray-900 dark:text-white">注册新设备</div>
					<div class="flex flex-col sm:flex-row gap-2">
						<!-- text-base(≥16px)防 iOS 聚焦缩放;触控行高 -->
						<input
							type="text"
							class="flex-1 min-w-0 min-h-11 md:min-h-0 text-base md:text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2.5 md:py-1.5 text-gray-900 dark:text-white outline-none focus:ring-1 focus:ring-gray-400"
							placeholder="设备名(如 Mac-mini / 云端)"
							bind:value={newName}
							on:keydown={(e) => {
								if (e.key === 'Enter') addDevice();
							}}
						/>
						<button
							type="button"
							class="min-h-11 md:min-h-0 px-4 py-2 md:py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
							disabled={registering || !newName.trim()}
							on:click={addDevice}
						>
							{registering ? '注册中…' : '生成设备令牌'}
						</button>
					</div>
					<div class="text-[11px] text-gray-400 dark:text-gray-500">
						注册即签发长效 node_token(绑本账号;无配对码);节点用它直连引擎 /engine/* 心跳上报。
					</div>
				</div>
			{/if}

			{#if loaded}
				<!-- 单列(手机)→ 双列(md+);列表卡每 30s 自动刷新 -->
				<div class="grid gap-3 md:grid-cols-2" data-testid="banyan-devices-page">
					{#each nodes as n (n.node_id)}
						{@const summary = nodeStatusSummary(n.status)}
						<div
							class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 space-y-3"
							data-testid="banyan-device-card"
						>
							<div class="flex items-start justify-between gap-2">
								<div class="min-w-0">
									<div class="flex items-center gap-2">
										<!-- 在线点:绿=online,灰=offline(正本=引擎 180s 判定) -->
										<span
											class="shrink-0 size-2 rounded-full {online(n)
												? 'bg-emerald-500'
												: 'bg-gray-400 dark:bg-gray-600'}"
											title={online(n) ? '在线' : '离线'}
										></span>
										<span class="text-sm font-semibold text-gray-900 dark:text-white truncate">
											{n.name}
										</span>
									</div>
									<div class="mt-1 text-[10px] text-gray-400 dark:text-gray-500 font-mono break-all">
										{n.node_id}
									</div>
								</div>
								<div class="shrink-0 text-right">
									<div class="text-[11px] {online(n)
										? 'text-emerald-600 dark:text-emerald-400'
										: 'text-gray-400 dark:text-gray-500'}">
										{online(n) ? '在线' : '离线'}
									</div>
									<div class="text-[10px] text-gray-400 dark:text-gray-500">
										心跳 {heartbeatAge(n)}
									</div>
								</div>
							</div>

							<!-- engine_version + status 摘要(宽松载荷防御渲染:版本/uptime/last_seq/goals 数) -->
							<div class="flex flex-wrap gap-1.5 text-[10px]">
								{#if n.engine_version || summary.version}
									<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850 font-mono">
										v {n.engine_version ?? summary.version}
									</span>
								{/if}
								{#if summary.uptime}
									<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850">
										uptime {summary.uptime}
									</span>
								{/if}
								{#if summary.last_seq !== undefined}
									<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850">
										seq {summary.last_seq}
									</span>
								{/if}
								{#if summary.goals !== undefined}
									<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-850">
										goals {summary.goals}
									</span>
								{/if}
								{#if !n.engine_version && !summary.version && !summary.uptime && summary.last_seq === undefined && summary.goals === undefined}
									<span class="text-gray-400 dark:text-gray-500">状态:—(节点未上报)</span>
								{/if}
							</div>

							<div class="text-[10px] text-gray-400 dark:text-gray-500">
								注册于 {registeredAt(n)}
							</div>

							<div class="flex flex-wrap items-center gap-2 pt-1">
								<button
									type="button"
									class="min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
									on:click={() => openCommand(n)}
								>
									{cmdNodeId === n.node_id ? '收起指令' : '发指令'}
								</button>
								{#if confirmDeleteId === n.node_id}
									<button
										type="button"
										class="min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition"
										disabled={deleting}
										on:click={() => removeDevice(n)}
									>
										{deleting ? '删除中…' : '确认删除'}
									</button>
									<button
										type="button"
										class="min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
										on:click={() => (confirmDeleteId = '')}
									>
										取消
									</button>
								{:else}
									<button
										type="button"
										class="min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 text-xs font-medium rounded-lg text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition"
										on:click={() => (confirmDeleteId = n.node_id)}
									>
										删除
									</button>
								{/if}
							</div>

							<!-- 指令小面板:kind 三选(封闭集),入队后回执经心跳异步 -->
							{#if cmdNodeId === n.node_id}
								<div
									class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/60 p-3 space-y-2.5"
									data-testid="banyan-node-command-panel"
								>
									<div class="flex flex-wrap gap-1.5">
										{#each CMD_KINDS as k (k.id)}
											<button
												type="button"
												class="px-2.5 py-1.5 min-h-11 md:min-h-0 md:py-1 rounded-full text-[11px] transition {cmdKind === k.id
													? 'bg-gray-900 text-white dark:bg-white dark:text-black'
													: 'bg-white dark:bg-gray-850 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}"
												on:click={() => (cmdKind = k.id)}
											>
												{k.label}
											</button>
										{/each}
									</div>

									{#if cmdKind === 'chat_turn'}
										{@const spaces = nodeSpaces(n.status)}
										{#if spaces.length > 0}
											<!-- RF-C3c F-1:可选空间下拉(选项=该节点心跳上报的空间目录);
											     目标会话未绑空间时必须选一个,否则引擎按协议诚实失败回执 -->
											<div class="space-y-1">
												<label
													class="block text-[10px] text-gray-500 dark:text-gray-400"
													for="banyan-cmd-space"
												>
													对话空间(新会话首转绑定;不选=目标节点默认会话)
												</label>
												<select
													id="banyan-cmd-space"
													class="w-full min-h-11 md:min-h-0 text-base md:text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2.5 md:py-1.5 text-gray-900 dark:text-white outline-none focus:ring-1 focus:ring-gray-400"
													bind:value={cmdSpaceId}
												>
													<option value="">(默认会话——已绑空间的节点适用)</option>
													{#each spaces as sp (sp.id)}
														<option value={sp.id}>{sp.name}({sp.id})</option>
													{/each}
												</select>
											</div>
										{:else}
											<div class="text-[10px] text-gray-400 dark:text-gray-500">
												目标节点默认会话(该节点未上报空间目录;若默认会话未绑空间,回执将为失败并提示需空间)
											</div>
										{/if}
										<textarea
											class="w-full text-base md:text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-gray-900 dark:text-white outline-none focus:ring-1 focus:ring-gray-400 min-h-20 resize-y"
											placeholder="要对这台设备说的话(走它的对话面,回复经心跳回程)"
											bind:value={cmdText}
										></textarea>
									{:else if cmdKind === 'goal_card_resolve'}
										<input
											type="text"
											class="w-full min-h-11 md:min-h-0 text-base md:text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2.5 md:py-1.5 text-gray-900 dark:text-white outline-none focus:ring-1 focus:ring-gray-400"
											placeholder="人审卡 card_id(/goals 页可见)"
											bind:value={cmdCardId}
										/>
										<div class="flex gap-2">
											<button
												type="button"
												class="flex-1 min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 rounded-lg text-xs font-medium transition {cmdCardDecision ===
												'approved'
													? 'bg-emerald-600 text-white'
													: 'border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}"
												on:click={() => (cmdCardDecision = 'approved')}
											>
												批准
											</button>
											<button
												type="button"
												class="flex-1 min-h-11 md:min-h-0 px-3 py-2 md:py-1.5 rounded-lg text-xs font-medium transition {cmdCardDecision ===
												'rejected'
													? 'bg-red-600 text-white'
													: 'border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'}"
												on:click={() => (cmdCardDecision = 'rejected')}
											>
												驳回
											</button>
										</div>
									{:else}
										<input
											type="text"
											class="w-full min-h-11 md:min-h-0 text-base md:text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2.5 md:py-1.5 text-gray-900 dark:text-white outline-none focus:ring-1 focus:ring-gray-400"
											placeholder="要中止的 goal_id(/goals 页可见)"
											bind:value={cmdGoalId}
										/>
									{/if}

										<div class="flex items-center gap-2">
											<button
												type="button"
												class="min-h-11 md:min-h-0 px-4 py-2 md:py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
												disabled={sending}
												on:click={sendCommand}
											>
												{sending ? '入队中…' : `确认${kindLabel(cmdKind)}`}
											</button>
											<span class="text-[10px] text-gray-400 dark:text-gray-500">
												已入队——节点下次心跳(约一分钟)取走执行,回执见下方「指令历史」
											</span>
										</div>
									</div>
								{/if}

								<!-- 指令历史(RF-C3c F-3 回执可见面):state 徽标+kind+时间+result 摘要,
								     随列表 30s 刷新;读面=引擎 GET /api/nodes/{id}/commands(最近 50 条) -->
								<div
									class="pt-1 space-y-1 border-t border-gray-100 dark:border-gray-850"
									data-testid="banyan-node-command-history"
								>
									<div class="text-[10px] text-gray-400 dark:text-gray-500">
										指令历史{history(n).length ? `(最近 ${history(n).length} 条,30s 刷新)` : ''}
									</div>
									{#each history(n).slice(0, 5) as c (c.id)}
										<div class="flex items-start gap-1.5 text-[10px] leading-4">
											<span
												class="shrink-0 px-1.5 py-0.5 rounded font-medium {stateBadgeClass(c.state)}"
											>
												{stateLabel(c.state)}
											</span>
											<span class="shrink-0 text-gray-600 dark:text-gray-300">
												{kindLabel(c.kind)}
											</span>
											<span class="shrink-0 text-gray-400 dark:text-gray-500">
												{formatNodeHeartbeatAge(c.created_at)}
											</span>
											{#if c.result}
												<span class="min-w-0 flex-1 text-gray-500 dark:text-gray-400 break-all line-clamp-2">
													{c.result}
												</span>
											{/if}
										</div>
									{:else}
										<div class="text-[10px] text-gray-400 dark:text-gray-500">
											暂无指令——下发后此处显示取走与回执状态
										</div>
									{/each}
									{#if history(n).length > 5}
										<div class="text-[10px] text-gray-400 dark:text-gray-500">
											…共 {history(n).length} 条(显示最近 5 条)
										</div>
									{/if}
								</div>
						</div>
					{:else}
						<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center md:col-span-2">
							暂无设备——点右上「添加设备」注册第一台(注册即签发设备令牌,无需配对码)。
						</div>
					{/each}
				</div>
			{:else}
				<div class="text-sm text-gray-400 dark:text-gray-500 py-12 text-center">加载设备清单…</div>
			{/if}
		</div>
	</div>
</div>
