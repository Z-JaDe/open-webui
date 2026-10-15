// banyan 引擎 API 客户端：数据源统一走 /banyan/api/*（fork 后端代理桥 → 引擎）。
// 见 FORKING.md 与 backend/open_webui/routers/banyan.py。

import { WEBUI_BASE_URL } from '$lib/constants';

export const BANYAN_API_BASE_URL = `${WEBUI_BASE_URL}/banyan/api`;

export type BanyanRegistryEntry = {
	id: string;
	/** 断言描述 */
	assertion: string;
	/** 绑定的 chat/task/plan */
	scope?: string;
	status: 'green' | 'red' | 'unknown' | 'quarantined';
	last_checked_at?: number;
	last_result?: string;
	hits?: number;
	created_at?: number;
};

export type BanyanCard = {
	id: string;
	title: string;
	/** 卡内容（经验/结论） */
	content: string;
	scope?: string;
	weight?: number;
	status: 'pending' | 'approved' | 'rejected';
	source?: string;
	created_at?: number;
};

export type BanyanAuditEvent = {
	id: string;
	chat_id?: string;
	message_id?: string;
	type: string;
	payload?: Record<string, any>;
	ts: number;
};

export type BanyanPlanSnapshot = {
	plan: import('$lib/components/banyan/types').BanyanPlanEvent;
	/** plan_id 下全部 wave_update 事件（按序），直接喂给 WaveBoard */
	wave_updates: import('$lib/components/banyan/types').BanyanWaveUpdateEvent[];
};

export type BanyanTreeNode = {
	id: string;
	/** 轮次（user→assistant 为一轮） */
	round: number;
	label: string;
	parent_id: string | null;
	children: string[];
	active: boolean;
	status?: 'done' | 'running' | 'failed' | 'abandoned';
	summary?: string;
};

export type BanyanTreeSnapshot = {
	chat_id: string;
	nodes: BanyanTreeNode[];
	active_path: string[];
};

// ── 引擎响应 → fork 页面形状的映射层（WE-9 收口）──
// 引擎端点返回的是存储投影（orch_* 行 / 审卡队列 / 事件采样），与页面期望的
// 渲染形状不同；全部差异在本层吸收，页面组件不感知（?mock=1 样例与本映射同形）。

const asArray = (v: unknown): any[] => (Array.isArray(v) ? v : []);

/** 引擎时间戳（epoch 秒，容错毫秒）→ epoch ms */
const toMs = (v: unknown): number | undefined => {
	if (typeof v !== 'number' || !(v > 0)) return undefined;
	return v > 1e12 ? v : v * 1000;
};

const parseJsonLoose = (v: unknown): any[] => {
	if (Array.isArray(v)) return v;
	if (typeof v === 'string') {
		try {
			const p = JSON.parse(v);
			return Array.isArray(p) ? p : [];
		} catch {
			return [];
		}
	}
	return [];
};

/** 引擎登记簿 last_result(pass|fail|unknown) + accepted(0=降权出池) → 页面四态 */
const toRegistryStatus = (raw: any): BanyanRegistryEntry['status'] => {
	if (raw?.accepted === 0 || raw?.accepted === false) return 'quarantined';
	if (raw?.last_result === 'pass') return 'green';
	if (raw?.last_result === 'fail') return 'red';
	return 'unknown';
};

const request = async (
	method: 'GET' | 'POST',
	path: string,
	body?: Record<string, any>
): Promise<any> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}${path}`, {
		method,
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${localStorage.token}`
		},
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	});

	if (!res.ok) {
		let detail = `${res.status} ${res.statusText}`;
		try {
			const json = await res.json();
			detail = json?.detail ?? detail;
		} catch {}
		throw new Error(detail);
	}

	return res.json();
};

////////////////////////////
// 断言登记簿 /registry
////////////////////////////
export const getBanyanRegistry = async (token: string = localStorage.token): Promise<BanyanRegistryEntry[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/registry`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 /api/registry 返回 orch_regs 行数组:
	// {id, plan_id, task_id, fingerprint, kind, spec(断言原文), last_result, last_detail,
	//  last_checked_at, accepted, created_at} → BanyanRegistryEntry
	const rows = asArray(await res.json());
	return rows.map((r: any) => ({
		id: String(r?.id ?? ''),
		assertion: String(r?.spec ?? r?.fingerprint ?? r?.id ?? ''),
		scope: r?.plan_id || r?.task_id || undefined,
		status: toRegistryStatus(r),
		last_checked_at: toMs(r?.last_checked_at),
		last_result: r?.last_detail || r?.last_result || undefined,
		created_at: toMs(r?.created_at)
	}));
};

////////////////////////////
// 语义卡 /cards
////////////////////////////
export const getBanyanCards = async (token: string = localStorage.token): Promise<BanyanCard[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/cards`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 /api/cards 返回审卡队列(pending)数组:
	// {id, subject, context, options, default, objection, evidence_refs} → BanyanCard
	const rows = asArray(await res.json());
	return rows.map((c: any) => ({
		id: String(c?.id ?? ''),
		title: String(c?.subject ?? c?.id ?? ''),
		content: String(c?.context ?? ''),
		status: 'pending' as const,
		source:
			Array.isArray(c?.evidence_refs) && c.evidence_refs.length
				? c.evidence_refs.map(String).join(', ')
				: undefined,
		scope: c?.objection ? `反方:${c.objection}` : undefined
	}));
};

export const resolveBanyanCard = async (
	cardId: string,
	decision: 'approved' | 'rejected',
	token: string = localStorage.token
) => {
	// 引擎契约:POST /api/cards/resolve,body={id, decision}(非 RESTful 子路径)
	return request('POST', `/cards/resolve`, { id: cardId, decision });
};

////////////////////////////
// 知识卡(K3)/registry 页区块(RFF P1:此前 /cards 页接的是审卡队列,
// 知识卡真端点 /api/knowledge/cards 无人消费——F6 缺口)
////////////////////////////
export type BanyanKnowledgeCard = {
	id: string;
	/** 卡名:索引 path 基名去扩展(引擎 cards 表无 title 列) */
	name: string;
	kind?: string;
	scope?: string;
	weight?: number;
	status: string;
	used?: number;
	wrong?: number;
	updated?: number;
};

export const getBanyanKnowledgeCards = async (
	query: { status?: string; limit?: number } = {},
	token: string = localStorage.token
): Promise<{ cards: BanyanKnowledgeCard[]; total: number }> => {
	const params = new URLSearchParams();
	if (query.status) params.set('status', query.status);
	params.set('limit', String(query.limit ?? 200));
	const res = await fetch(`${BANYAN_API_BASE_URL}/knowledge/cards?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/knowledge/cards 返回
	// {cards:[{id,path,kind,scope,status,weight,used,wrong,updated}], total} → BanyanKnowledgeCard
	const raw: any = await res.json();
	const cards = asArray(raw?.cards).map((c: any): BanyanKnowledgeCard => {
		const path = typeof c?.path === 'string' ? c.path : '';
		const base = path.split('/').pop()?.replace(/\.(md|markdown)$/i, '') || '';
		return {
			id: String(c?.id ?? ''),
			name: base || String(c?.id ?? ''),
			kind: c?.kind ? String(c.kind) : undefined,
			scope: c?.scope ? String(c.scope) : undefined,
			weight: typeof c?.weight === 'number' ? c.weight : undefined,
			status: String(c?.status ?? 'unknown'),
			used: Number(c?.used ?? 0),
			wrong: Number(c?.wrong ?? 0),
			updated: toMs(c?.updated)
		};
	});
	return { cards, total: Number(raw?.total ?? cards.length) };
};

////////////////////////////
// 事件浏览 /audit
////////////////////////////
export const getBanyanAuditEvents = async (
	query: { chat_id?: string; type?: string; limit?: number } = {},
	token: string = localStorage.token
): Promise<BanyanAuditEvent[]> => {
	const params = new URLSearchParams();
	if (query.chat_id) params.set('chat_id', query.chat_id);
	if (query.type) params.set('type', query.type);
	params.set('limit', String(query.limit ?? 200));
	const res = await fetch(`${BANYAN_API_BASE_URL}/audit?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 /api/audit 返回分层审计采样数组:{subject, high_risk, ref, ts(epoch 秒)}
	// → BanyanAuditEvent(chat_id/type 过滤由页面客户端二次过滤兜底)
	const rows = asArray(await res.json());
	return rows.map((d: any, i: number) => ({
		id: `aud-${i}-${d?.ts ?? ''}`,
		type: d?.high_risk ? 'auto.high_risk' : 'auto.low_risk',
		ts: toMs(d?.ts) ?? Date.now(),
		payload: { subject: d?.subject, ref: d?.ref, high_risk: !!d?.high_risk }
	}));
};

////////////////////////////
// 方案与波次 /plans
////////////////////////////
// 引擎 plan 状态(open|pending_approval|rejected|running|blocked|finished|revised)→ 页面四态
const PLAN_STATUS_MAP: Record<string, import('$lib/components/banyan/types').BanyanPlanEvent['status']> = {
	open: 'pending',
	pending_approval: 'pending',
	approved: 'approved',
	running: 'approved',
	blocked: 'approved',
	finished: 'approved',
	rejected: 'rejected',
	revised: 'revised'
};

// 引擎 orch_tasks.status → WaveBoard 六态(词表一致,透传兜底 pending)
const TASK_STATUS_MAP: Record<string, import('$lib/components/banyan/types').BanyanTaskStatus> = {
	pending: 'pending',
	running: 'running',
	done: 'done',
	failed: 'failed',
	skipped: 'skipped',
	blocked: 'blocked'
};

export const getBanyanPlan = async (
	planId: string,
	token: string = localStorage.token
): Promise<BanyanPlanSnapshot> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/plans/${encodeURIComponent(planId)}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/plans/:id 返回 {plan:{id,contract_json,status,...}, tasks:[orch_tasks 行],
	// contract(提交时契约 dict,重启即失;兜底 plan.contract_json 反序列化)}
	// → BanyanPlanSnapshot{plan: BanyanPlanEvent, wave_updates: BanyanWaveUpdateEvent[]}
	const raw: any = await res.json();
	const row = raw?.plan ?? {};
	const id = String(row.id ?? planId);
	let contract: any = raw?.contract;
	if (!contract && typeof row.contract_json === 'string') {
		try {
			contract = JSON.parse(row.contract_json);
		} catch {
			contract = null;
		}
	}
	const waves = asArray(contract?.waves);
	const plan: import('$lib/components/banyan/types').BanyanPlanEvent = {
		type: 'plan',
		plan_id: id,
		status: PLAN_STATUS_MAP[String(row.status ?? '')] ?? 'pending',
		hypothesis: asArray(contract?.assumptions).map(String).join('；') || undefined,
		waves: waves.map((w: any, i: number) => ({
			index: i + 1,
			tasks: asArray(w?.tasks).map((t: any) => ({
				task_id: String(t?.id ?? ''),
				title: String(t?.title || t?.id || ''),
				deps: asArray(t?.deps).map(String)
			}))
		})),
		risks: asArray(contract?.risks).map(String),
		rollback: contract?.rollback ? String(contract.rollback) : undefined
	};

	// orch_tasks 行按 wave_no 分组 → 每 wave 一条 wave_update(spec_id=契约任务 id,
	// 与 PlanCard deps 同名空间;deps_json/status_reason 是 JSON 串/文本,防御性解析)。
	// 引擎 wave_no 从 0 计(契约波序枚举下标),页面 wave 从 1 计(PlanCard index 同轴)→ +1
	const byWave = new Map<number, import('$lib/components/banyan/types').BanyanWaveUpdateEvent['tasks']>();
	for (const t of asArray(raw?.tasks)) {
		const w = Number(t?.wave_no);
		const wave = Number.isFinite(w) && w >= 0 ? w + 1 : 1;
		const list = byWave.get(wave) ?? [];
		list.push({
			task_id: String(t?.spec_id || t?.id || ''),
			title: t?.title ? String(t.title) : undefined,
			status: TASK_STATUS_MAP[String(t?.status ?? 'pending')] ?? 'pending',
			deps: parseJsonLoose(t?.deps_json).map(String),
			detail: t?.status_reason ? String(t.status_reason) : undefined
		});
		byWave.set(wave, list);
	}
	const wave_updates: import('$lib/components/banyan/types').BanyanWaveUpdateEvent[] = [
		...byWave.entries()
	]
		.sort((a, b) => a[0] - b[0])
		.map(([wave, tasks]) => ({ type: 'wave_update' as const, plan_id: id, wave, tasks }));

	return { plan, wave_updates };
};

/** PlanCard 批准/驳回/选B 按钮的原生提交目标 */
export const resolveBanyanPlan = async (
	planId: string,
	body: import('$lib/components/banyan/types').BanyanPlanResolveBody,
	token: string = localStorage.token
) => {
	return request('POST', `/plans/${encodeURIComponent(planId)}/resolve`, body);
};

////////////////////////////
// 会话树 /tree
////////////////////////////
export const getBanyanTree = async (chatId: string, token: string = localStorage.token): Promise<BanyanTreeSnapshot> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/chats/${encodeURIComponent(chatId)}/tree`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/chats/:id/tree 返回线性树投影:
	// {chat_id, nodes:[{turn_id, seq, status(success|error|streaming), summary(≤50 字)}],
	//  active_leaf, branches:[{turn_id, branches:[后继 turn_id]}]}
	// → BanyanTreeSnapshot{id/round/label/parent_id/children/active/status}
	const raw: any = await res.json();
	const turns: any[] = asArray(raw?.nodes);
	const statusOf = (s: unknown): BanyanTreeNode['status'] =>
		s === 'error' ? 'failed' : s === 'streaming' ? 'running' : 'done';
	const nodes: BanyanTreeNode[] = turns.map((t: any, i: number) => ({
		id: String(t?.turn_id ?? `turn-${i}`),
		round: i + 1,
		label: `轮 ${i + 1}${t?.summary ? ` · ${t.summary}` : ''}`,
		parent_id: i > 0 ? String(turns[i - 1]?.turn_id ?? `turn-${i - 1}`) : null,
		children: i + 1 < turns.length ? [String(turns[i + 1]?.turn_id ?? `turn-${i + 1}`)] : [],
		active: true, // 线性树:全链在活动路径上(多分支后由 active_path 决定)
		status: statusOf(t?.status),
		summary: t?.summary || undefined
	}));
	return {
		chat_id: String(raw?.chat_id ?? chatId),
		nodes,
		active_path: turns.map((t: any, i: number) => String(t?.turn_id ?? `turn-${i}`))
	};
};

export const switchBanyanTreeNode = async (
	chatId: string,
	nodeId: string,
	token: string = localStorage.token
) => {
	return request('POST', `/chats/${encodeURIComponent(chatId)}/tree/switch`, { node_id: nodeId });
};

export const rerunBanyanTreeNode = async (
	chatId: string,
	nodeId: string,
	token: string = localStorage.token
) => {
	return request('POST', `/chats/${encodeURIComponent(chatId)}/tree/rerun`, { node_id: nodeId });
};

////////////////////////////
// 子代理 /subagents
////////////////////////////
export const stopBanyanSubagent = async (
	subagentId: string,
	token: string = localStorage.token
) => {
	return request('POST', `/subagents/${encodeURIComponent(subagentId)}/stop`);
};
