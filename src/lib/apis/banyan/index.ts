// banyan 引擎 API 客户端：数据源统一走 /banyan/api/*（fork 后端代理桥 → 引擎）。
// 见 FORKING.md 与 backend/open_webui/routers/banyan.py。

import { WEBUI_BASE_URL } from '$lib/constants';

export const BANYAN_API_BASE_URL = `${WEBUI_BASE_URL}/banyan/api`;

export type BanyanAgentDesign = {
	name: string;
	description: string;
	tier: string;
	model: string;
	tools: string[];
	memory: string;
	output: string;
	runtime_prompts: string[];
	prompt: string;
};

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
	/** 引擎方案行原始状态（RF-20b：blocked=完成门/攻击门拦截；PLAN_STATUS_MAP 会把
	 * blocked 折进 approved，下钻页靠本字段渲染拦截提示条） */
	engine_status?: string;
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
	method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
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
	// 引擎 plan 状态(open|pending_approval|rejected|running|blocked|finished|revised|
	// orphaned[TA-2:重启孤儿复位,可重新批准重入])→ 页面五态;blocked 折进 approved,
	// 原始态经 BanyanPlanSnapshot.engine_status 透出(RF-20b 完成门拦截提示条用)
	const PLAN_STATUS_MAP: Record<string, import('$lib/components/banyan/types').BanyanPlanEvent['status']> = {
		open: 'pending',
		pending_approval: 'pending',
		approved: 'approved',
		running: 'approved',
		blocked: 'approved',
		finished: 'approved',
		rejected: 'rejected',
		revised: 'revised',
		orphaned: 'orphaned'
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

	return { plan, wave_updates, engine_status: String(row.status ?? '') };
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
// 方案列表 /plans(F1/D2 方案列表页:状态分组一屏全览,点入下钻)
////////////////////////////
export type BanyanPlanListItem = {
	id: string;
	/** open|pending_approval|running|blocked|finished|rejected|revised|orphaned */
	status: string;
	/** 联 orch_problems.subject(无 problem 的方案为空串,渲染回退 id) */
	subject: string;
	/** epoch ms(引擎给 epoch 秒,本层换算) */
	created_at?: number;
	tasks: { total: number; done: number; failed: number; skipped: number };
};

export const getBanyanPlans = async (
	query: { status?: string; limit?: number } = {},
	token: string = localStorage.token
): Promise<BanyanPlanListItem[]> => {
	const params = new URLSearchParams();
	if (query.status) params.set('status', query.status); // 逗号多值(V-15 惯例),空=全部
	params.set('limit', String(query.limit ?? 50));
	const res = await fetch(`${BANYAN_API_BASE_URL}/plans?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/plans 返回
	// {plans:[{id,status,subject,created_at(epoch 秒),tasks:{total,done,failed,skipped}}]}
	const raw: any = await res.json();
	return asArray(raw?.plans).map((p: any): BanyanPlanListItem => ({
		id: String(p?.id ?? ''),
		status: String(p?.status ?? ''),
		subject: String(p?.subject ?? ''),
		created_at: toMs(p?.created_at),
		tasks: {
			total: Number(p?.tasks?.total ?? 0),
			done: Number(p?.tasks?.done ?? 0),
			failed: Number(p?.tasks?.failed ?? 0),
			skipped: Number(p?.tasks?.skipped ?? 0)
		}
	}));
};

////////////////////////////
// 方案断言登记簿 /registry?plan_id=X（RF-20b：下钻页红绿断言分组）
////////////////////////////
export type BanyanPlanAssertion = {
	id: string;
	/** 断言指纹：sha256 十六进制（无前缀）——分组轴不在指纹上 */
	fingerprint: string;
	/** 断言类型：红测行带 "red-" 前缀（"red-shell"），验收行为 "shell"（分组轴） */
	kind: string;
	/** 断言/红测命令原文 */
	spec: string;
	status: BanyanRegistryEntry['status'];
	/** 阶段 detail（"pre-work red"/"final green"）或 pass|fail 原文（展示用） */
	last_result?: string;
	/** 着色轴：pass=通过 / fail=未通过 / unknown=未验证（final green→pass，pre-work red→fail） */
	verdict: 'pass' | 'fail' | 'unknown';
	last_checked_at?: number;
	task_id?: string;
};

/** 红绿分组轴（RV-D P1-1 修正后的冻结契约）：引擎登记簿的 fingerprint 是
 * sha256 十六进制哈希（不含 "red-" 前缀），"red-" 前缀长在 kind 上
 * （RED_PREFIX + "shell" = "red-shell"）。按 kind 判红测，指纹轴会整组漏判。
 * （fingerprint 入参仅为测试/展示便利，不参与判定。） */
export const isRedAssertion = (
	a: Pick<BanyanPlanAssertion, 'kind' | 'fingerprint'>
): boolean => a.kind.startsWith('red-');

/** last_result + 阶段 detail → 通过/未通过/未知（RF-20：红测阶段 detail 自带色词） */
const toVerdict = (raw: any): BanyanPlanAssertion['verdict'] => {
	const result = String(raw?.last_result ?? '')
		.trim()
		.toLowerCase();
	const hay = `${result} ${raw?.last_detail ?? ''}`;
	if (result === 'pass') return 'pass';
	if (result === 'fail') return 'fail';
	if (/final green/i.test(hay)) return 'pass';
	if (/pre-work red/i.test(hay) || /(^|\s)red(\s|$)/i.test(result)) return 'fail';
	return 'unknown';
};

export const getBanyanPlanRegistry = async (
	planId: string,
	token: string = localStorage.token
): Promise<BanyanPlanAssertion[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/registry?plan_id=${encodeURIComponent(planId)}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/registry?plan_id=X 返回该方案的 orch_regs 行数组:
	// {id, plan_id, task_id, fingerprint, kind, spec, last_result, last_detail,
	//  last_checked_at, accepted, created_at}
	// RV-D P1-1 修正冻结契约:指纹=sha256 十六进制(无前缀);"red-" 前缀长在
	// kind 上("red-shell"),spec 为红测命令,last_result/last_detail 带
	// "pre-work red"/"final green" 阶段 detail。红绿分组轴=kind。
	const rows = asArray(await res.json());
	return rows.map((r: any): BanyanPlanAssertion => ({
		id: String(r?.id ?? ''),
		fingerprint: String(r?.fingerprint ?? ''),
		kind: String(r?.kind ?? ''),
		spec: String(r?.spec ?? r?.fingerprint ?? r?.id ?? ''),
		status: toRegistryStatus(r),
		last_result: r?.last_detail || r?.last_result || undefined,
		verdict: toVerdict(r),
		last_checked_at: toMs(r?.last_checked_at),
		task_id: r?.task_id ? String(r.task_id) : undefined
	}));
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

// RF-Z:rerunBanyanTreeNode 已随 /tree 页死按钮摘除(引擎无 /chats/{id}/tree/rerun
// 对端,实测 404)——分支切换仅消息流 TreeSwitcher 的 switch 通道保留(对端同样
// 缺位,待引擎补树写端点后统一恢复)。

////////////////////////////
// 场景包 /packs（RF-37：可插拔场景配置集——研发代码/国际局势分析等各一套
// Agent/提示词/技能；核心 5 Agent 常驻场景无关，包内特化 Agent 只能被
// spawn_agent 按需拉起）
////////////////////////////
export type BanyanPack = {
	/** 场景包名（=目录名，如「研发」） */
	id: string;
	/** 一句话描述（pack.json description） */
	description?: string;
	/** 场景特化 Agent 名单（只能被 spawn_agent 带 pack 拉起，零常驻成本） */
	agents: string[];
	/** 场景任务模板名 */
	prompts: string[];
	/** 场景技能名 */
	skills: string[];
	/** 在盘内容统计 */
	counts?: { prompts: number; skills: number; agents: number };
};

export const getBanyanPacks = async (
	token: string = localStorage.token
): Promise<BanyanPack[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/packs`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/packs 返回
	// {packs:[{name,description,agents,prompts,skills,counts}]}（坏包已跳过）
	// → BanyanPack
	const raw: any = await res.json();
	return asArray(raw?.packs).map((p: any): BanyanPack => ({
		id: String(p?.name ?? ''),
		description: p?.description ? String(p.description) : undefined,
		agents: asArray(p?.agents).map(String),
		prompts: asArray(p?.prompts).map(String),
		skills: asArray(p?.skills).map(String),
		counts: p?.counts ?? undefined
	}));
};

////////////////////////////
// 子代理停止（引擎对端：POST /api/work/{work_id}/cancel）
////////////////////////////
export const stopBanyanSubagent = async (
	subagentId: string,
	token: string = localStorage.token
) => {
	// RF-Z：引擎真实对端是 /work/{id}/cancel（子代理工单取消）——
	// 旧 /subagents/{id}/stop 引擎无此路由（死按钮，RV-final 携带 P1）。
	return request('POST', `/work/${encodeURIComponent(subagentId)}/cancel`);
};

////////////////////////////
// 管家信箱 /inbox（v3 W2，V-4/V-5）
// kind→category 机械映射在引擎侧；三 tab 按 category 过滤，前端不自解释。
////////////////////////////
export type BanyanInboxCategory = 'decision' | 'done' | 'notice';

export type BanyanInboxItem = {
	id: string;
	/** blocked_escalation|principle_conflict|delivery_signoff|plan_completed|notice */
	kind: string;
	category: BanyanInboxCategory;
	title: string;
	body: string;
	push: boolean;
	/** open|read|resolved|archived|expired */
	status: string;
	/** 待裁决项的预设选项（仅展示，提交用 resolve 的 decision） */
	options: string[];
	ref_kind?: string;
	ref_id?: string;
	plan_id?: string;
	task_id?: string;
	conv_id?: string;
	/** epoch ms（引擎给 epoch 秒，本层换算） */
	created_at?: number;
	/** 超时升级旁注（V-5：只 escalated+重复推送，不代决） */
	escalated?: boolean;
	/** 引擎裁决流回填（resolved 项展示用） */
	resolution?: Record<string, any>;
};

export type BanyanInboxUnread = { decision: number; done: number; notice: number };

export type BanyanInboxSnapshot = { items: BanyanInboxItem[]; unread: BanyanInboxUnread };

export const getBanyanInbox = async (
	query: { category?: BanyanInboxCategory; status?: string; limit?: number } = {},
	token: string = localStorage.token
): Promise<BanyanInboxSnapshot> => {
	const params = new URLSearchParams();
	if (query.category) params.set('category', query.category);
	if (query.status) params.set('status', query.status);
	params.set('limit', String(query.limit ?? 50));
	const res = await fetch(`${BANYAN_API_BASE_URL}/inbox?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/inbox 返回 {items:[msg 行], unread:{decision,done,notice}}
	const raw: any = await res.json();
	const items = asArray(raw?.items).map((m: any): BanyanInboxItem => ({
		id: String(m?.id ?? ''),
		kind: String(m?.kind ?? ''),
		category: (['decision', 'done', 'notice'].includes(m?.category)
			? m.category
			: 'notice') as BanyanInboxCategory,
		title: String(m?.title ?? m?.id ?? ''),
		body: String(m?.body ?? ''),
		push: !!m?.push,
		status: String(m?.status ?? 'open'),
		options: asArray(m?.options).map(String),
		ref_kind: m?.ref_kind ? String(m.ref_kind) : undefined,
		ref_id: m?.ref_id ? String(m.ref_id) : undefined,
		plan_id: m?.plan_id ? String(m.plan_id) : undefined,
		task_id: m?.task_id ? String(m.task_id) : undefined,
		conv_id: m?.conv_id ? String(m.conv_id) : undefined,
		created_at: toMs(m?.created_at),
		escalated: !!m?.escalated,
		resolution: m?.resolution && typeof m.resolution === 'object' ? m.resolution : undefined
	}));
	const unread = raw?.unread ?? {};
	return {
		items,
		unread: {
			decision: Number(unread?.decision ?? 0),
			done: Number(unread?.done ?? 0),
			notice: Number(unread?.notice ?? 0)
		}
	};
};

/** 裁决：decision 自由文本（页面预设 'approve'（批准扩围）/ 'reject'（驳回）） */
export const resolveBanyanInbox = async (
	msgId: string,
	decision: string,
	note?: string,
	token: string = localStorage.token
) => {
	return request('POST', `/inbox/${encodeURIComponent(msgId)}/resolve`, {
		decision,
		...(note ? { note } : {})
	});
};

export const readBanyanInbox = async (msgId: string, token: string = localStorage.token) => {
	return request('POST', `/inbox/${encodeURIComponent(msgId)}/read`);
};

export const archiveBanyanInbox = async (msgId: string, token: string = localStorage.token) => {
	return request('POST', `/inbox/${encodeURIComponent(msgId)}/archive`);
};

////////////////////////////
// 日历 /calendar（v3 W3，V-8 第一包：UTC 绝对时间戳，无 rrule）
// 所有 ts 均为 UTC epoch 秒；RRSVP/循环等引擎不支持的字段一律不出。
////////////////////////////
export type BanyanCalendarEvent = {
	id: string;
	title: string;
	description?: string;
	/** UTC epoch 秒 */
	start_ts: number;
	/** UTC epoch 秒 */
	end_ts?: number;
	all_day: boolean;
	/** open|cancelled（DELETE/取消语义后为 cancelled） */
	status: string;
	source?: string;
	remind_offset_s?: number;
};

export const getBanyanCalendar = async (
	query: { from: number; to: number },
	token: string = localStorage.token
): Promise<BanyanCalendarEvent[]> => {
	const params = new URLSearchParams({
		from_ts: String(Math.floor(query.from)),
		to_ts: String(Math.floor(query.to))
	});
	const res = await fetch(`${BANYAN_API_BASE_URL}/calendar/events?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	// 引擎 GET /api/calendar/events 返回 {events:[...]}（UTC epoch 秒）
	const raw: any = await res.json();
	return asArray(raw?.events).map((e: any): BanyanCalendarEvent => ({
		id: String(e?.id ?? ''),
		title: String(e?.title ?? ''),
		description: e?.description ? String(e.description) : undefined,
		start_ts: Number(e?.start_ts ?? 0),
		end_ts: typeof e?.end_ts === 'number' ? e.end_ts : undefined,
		all_day: !!e?.all_day,
		status: String(e?.status ?? 'open'),
		source: e?.source ? String(e.source) : undefined,
		remind_offset_s: typeof e?.remind_offset_s === 'number' ? e.remind_offset_s : undefined
	}));
};

export const createBanyanCalendarEvent = async (
	body: {
		title: string;
		start_ts: number;
		end_ts: number;
		all_day?: boolean;
		description?: string;
		remind_offset_s?: number;
	},
	token: string = localStorage.token
) => {
	// 引擎契约:POST /api/calendar/events → {event:{...}}
	return request('POST', `/calendar/events`, body);
};

export const updateBanyanCalendarEvent = async (
	eventId: string,
	body: Partial<{
		title: string;
		start_ts: number;
		end_ts: number;
		all_day: boolean;
		description: string;
		remind_offset_s: number | null;
	}>,
	token: string = localStorage.token
) => {
	return request('PATCH', `/calendar/events/${encodeURIComponent(eventId)}`, body);
};

/** DELETE = 取消语义（引擎置 cancelled，不物理删） */
export const deleteBanyanCalendarEvent = async (
	eventId: string,
	token: string = localStorage.token
) => {
	return request('DELETE', `/calendar/events/${encodeURIComponent(eventId)}`);
};

////////////////////////////
// 引擎聚合状态 /status（v3 W4，V-10：sidecar 不可达时 sidecar={ok:false}，不 500）
////////////////////////////
export type BanyanEngineStatus = {
	engine: {
		status: string;
		last_seq?: number;
		paused?: boolean;
		home?: string;
		workspace?: string;
		version?: string;
	};
	sidecar: { ok: boolean; roles?: string[] | Record<string, any> };
	tiers: { id: string; label?: string; desc?: string; model?: string; keyed?: boolean; default?: boolean }[];
	// RF-34:Agent 花名册(引擎统一目录正本轻量直读;output=output_kind 形态关键字)
	agents: {
		name: string;
		description?: string;
		tier?: string;
		tools?: string[];
		memory?: string;
		output?: string;
	}[];
	counts: { inbox: BanyanInboxUnread; plans_running: number };
};

export const getBanyanAgent = async (
	name: string,
	token: string = localStorage.token
): Promise<BanyanAgentDesign> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/agents/${encodeURIComponent(name)}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
};

export type BanyanGoalEntry = {
	goalId: string;
	requestId: string | null;
	kind: string;
	objective: string;
	phase: string;
	status: 'running' | 'completed' | 'failed' | 'aborted';
	createdAt: number;
	settledAt: number | null;
	summary: string | null;
	error: string | null;
};

export type BanyanGoalConvs = {
	manager: { name: string; conversationId: string; transcript: Array<{ role: string; text: string }> };
	subagents: Array<{ name: string; conversationId: string; transcript: Array<{ role: string; text: string }> }>;
	reviewers: Array<{ name: string; conversationId: string; transcript: Array<{ role: string; text: string }> }>;
};

export const getBanyanGoals = async (
	token: string = localStorage.token
): Promise<BanyanGoalEntry[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/goals`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	return (await res.json()).goals ?? [];
};

export const getBanyanGoalConvs = async (
	goalId: string,
	token: string = localStorage.token
): Promise<BanyanGoalConvs> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/goals/${encodeURIComponent(goalId)}/convs`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
};

// v3 goal 人审卡(goal 内核 awaitHumanCard 开出的卡;引擎薄代理 pi-goal /cards)。
export type BanyanGoalCard = {
	cardId: string;
	goalId: string;
	question: string;
	status: 'open' | 'approved' | 'rejected';
	createdAt: number;
};

export const getBanyanGoalCards = async (
	token: string = localStorage.token
): Promise<BanyanGoalCard[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/goals/cards`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	return (await res.json()).cards ?? [];
};

export const resolveBanyanGoalCard = async (
	cardId: string,
	decision: 'approved' | 'rejected',
	note?: string,
	token: string = localStorage.token
): Promise<unknown> => {
	const res = await fetch(
		`${BANYAN_API_BASE_URL}/goals/cards/${encodeURIComponent(cardId)}/resolve`,
		{
			method: 'POST',
			headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
			body: JSON.stringify({ decision, note: note ?? null })
		}
	);
	if (!res.ok) throw new Error(await res.text());
	return res.json();
};

// ── v3 工作空间(设计-工作空间v1):两层注册表(主仓内置 ∪ ~/.banyan/workspaces 自建) ──
export type BanyanWorkspace = {
	id: string;
	name: string;
	description: string;
	builtin: boolean;
	// model_id 死投影已删(DA-3 契约4:v3.1 后 UI 零消费,后端 banyan 仓并行删除)
	roots: string[];
	skills: string[];
	roles: string[];
	tools: string[];
	knowledge_scopes: string[];
	goal_defaults: Record<string, unknown>;
	agent: { model: string; tier: string };
	staging: boolean;
	degraded: boolean;
	error: string;
	agent_prompt?: string;
	staging_config?: Record<string, string>;
	skills_detail?: Array<{ name: string; body: string }>;
	roles_detail?: Array<{
		name: string;
		description: string;
		tier: string;
		tools: string[];
		memory: string;
		prompt: string;
	}>;
	knowledge_detail?: Array<{
		scope: string;
		total: number;
		items: Array<{ title: string; file: string }>;
	}>;
};

// RF1-D:注册表错误投影(后端 banyan 仓并行加键,向后兼容——无键时不渲染警告)
export type BanyanWorkspaceListResult = {
	workspaces: BanyanWorkspace[];
	/** 同名冲突的空间名(内置 ∪ 自建不做覆盖,单一真相) */
	conflicts?: string[];
	/** 坏配置空间:id → 错误摘要 */
	errors?: Record<string, string>;
};

export const getBanyanWorkspaces = async (
	token: string = localStorage.token
): Promise<BanyanWorkspaceListResult> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/workspaces`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	const data = await res.json();
	return {
		workspaces: data?.workspaces ?? [],
		conflicts: data?.conflicts,
		errors: data?.errors
	};
};

export const getBanyanWorkspace = async (
	spaceId: string,
	token: string = localStorage.token
): Promise<BanyanWorkspace> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/workspaces/${encodeURIComponent(spaceId)}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(await res.text());
	return (await res.json()).workspace;
};

////////////////////////////
// 设备互感知 /nodes(C3,goal-cloud 协议锁定)
// 引擎侧并行实现(RF-C3a);经 /banyan/api 通配桥 1:1 直达(routers/banyan.py:184,
// nodes 路径过 safe_bridge_path 守卫,后端零改动)。
// 管理面走 webui 用户 JWT(桥剥 Authorization 注 BANYAN_TOKEN 或透传);
// 节点自身心跳走 Caddy /engine/* 直连引擎,不经本层。
////////////////////////////
export type BanyanNodeInfo = {
	node_id: string;
	name: string;
	/** epoch ms(引擎给 epoch 秒,本层换算;容错毫秒) */
	last_heartbeat?: number;
	online: boolean;
	/** 最近一次心跳的状态载荷——引擎侧自由形状(宽松 Record),前端只做防御渲染 */
	status?: Record<string, unknown>;
	engine_version?: string;
	/** epoch ms */
	created_at?: number;
};

/** 指令 kind 封闭集(C3 协议锁定;加 kind 不加信道) */
export type BanyanNodeCommandKind = 'chat_turn' | 'goal_card_resolve' | 'goal_abort';

export type BanyanNodeCommandResult = {
	command_id: string;
};

/** 注册回执:node_token 只此一次返回(引擎库存 hash)——调用方只渲染不落存 */
export type BanyanNodeRegisterResult = {
	node_id: string;
	node_token: string;
};

/** 引擎列表载荷 → BanyanNodeInfo(裸数组为主,{nodes:[…]} 兜底;字段全防御) */
export const listBanyanNodes = async (
	token: string = localStorage.token
): Promise<BanyanNodeInfo[]> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/nodes`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	const raw: any = await res.json();
	const rows = asArray(Array.isArray(raw) ? raw : raw?.nodes);
	return rows.map(
		(n: any): BanyanNodeInfo => ({
			node_id: String(n?.node_id ?? n?.id ?? ''),
			name: String(n?.name ?? n?.node_id ?? ''),
			last_heartbeat: toMs(n?.last_heartbeat ?? n?.last_seen),
			online: !!n?.online,
			status:
				n?.status && typeof n.status === 'object' && !Array.isArray(n.status)
					? (n.status as Record<string, unknown>)
					: undefined,
			engine_version: n?.engine_version ? String(n.engine_version) : undefined,
			created_at: toMs(n?.created_at)
		})
	);
};

/** POST /api/nodes {name} → {node_id, node_token}——token 只此一次,页面显示后即焚 */
export const registerBanyanNode = async (
	name: string,
	token: string = localStorage.token
): Promise<BanyanNodeRegisterResult> => {
	const raw = await request('POST', `/nodes`, { name });
	const out: BanyanNodeRegisterResult = {
		node_id: String(raw?.node_id ?? ''),
		node_token: String(raw?.node_token ?? '')
	};
	if (!out.node_id || !out.node_token) {
		throw new Error(`引擎注册回执缺 node_id/node_token:${JSON.stringify(raw)?.slice(0, 80)}`);
	}
	return out;
};

/** POST /api/nodes/{id}/commands {kind,payload} → {command_id}(入队;回执经节点心跳异步) */
export const sendBanyanNodeCommand = async (
	nodeId: string,
	kind: BanyanNodeCommandKind,
	payload: Record<string, unknown>,
	token: string = localStorage.token
): Promise<BanyanNodeCommandResult> => {
	const raw = await request('POST', `/nodes/${encodeURIComponent(nodeId)}/commands`, {
		kind,
		payload
	});
	return { command_id: String(raw?.command_id ?? raw?.id ?? '') };
};

/** DELETE /api/nodes/{id}(吊销该节点:node_tokens 删行,心跳即拒) */
export const deleteBanyanNode = async (nodeId: string, token: string = localStorage.token) => {
	return request('DELETE', `/nodes/${encodeURIComponent(nodeId)}`);
};

// ── C3b 设备页纯函数(时间格式化/在线判定/status 防御摘要;vitest 直测,
// redGrouping.test.ts 同款)──

/** 离线判定阈值(协议锁定 180s,引擎侧正本;前端仅兜底口径一致) */
export const NODE_OFFLINE_AFTER_MS = 180_000;

/** 心跳相对时间(epoch ms → 「刚刚/N 秒/N 分钟/N 小时/N 天前」;未来/坏值防御) */
export const formatNodeHeartbeatAge = (
	ms: number | undefined,
	now: number = Date.now()
): string => {
	if (typeof ms !== 'number' || !(ms > 0)) return '—';
	const diff = now - ms;
	if (diff < 10_000) return '刚刚'; // 未来时间戳(客户端钟慢)同归「刚刚」,不渲染负数
	if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`;
	if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
	if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
	return `${Math.floor(diff / 86_400_000)} 天前`;
};

/**
 * 在线判定:引擎 `online` 布尔是正本(180s 阈值在引擎侧算,不信客户端时钟推 sent_at);
 * 引擎未给布尔(形状漂移/旧引擎)时前端按 last_heartbeat 距今 <180s 兜底,口径一致。
 */
export const isNodeOnline = (
	online: unknown,
	lastHeartbeatMs: number | undefined,
	now: number = Date.now(),
	thresholdMs: number = NODE_OFFLINE_AFTER_MS
): boolean => {
	if (typeof online === 'boolean') return online;
	if (typeof lastHeartbeatMs !== 'number' || !(lastHeartbeatMs > 0)) return false;
	return now - lastHeartbeatMs < thresholdMs;
};

/** 宽松 status 载荷 → 页面摘要四键(版本/uptime/last_seq/goals 数)。
 * 引擎侧自由形状(RF-C3a 并行),已知键位逐个探测,坏值跳过不炸——
 * 空手而归时页面渲染「—」,不做第二套状态词汇。 */
export const nodeStatusSummary = (
	status: unknown
): { version?: string; uptime?: string; last_seq?: number; goals?: number } => {
	const out: { version?: string; uptime?: string; last_seq?: number; goals?: number } = {};
	if (!status || typeof status !== 'object' || Array.isArray(status)) return out;
	const s = status as Record<string, unknown>;
	const engine = (s.engine && typeof s.engine === 'object' ? s.engine : {}) as Record<
		string,
		unknown
	>;
	const counts = (s.counts && typeof s.counts === 'object' ? s.counts : {}) as Record<
		string,
		unknown
	>;
	const ver = s.version ?? s.engine_version ?? engine.version;
	if (ver !== undefined && ver !== null && String(ver) !== '') out.version = String(ver);
	const up = s.uptime ?? s.uptime_s ?? engine.uptime;
	if (up !== undefined && up !== null && String(up) !== '') out.uptime = String(up);
	for (const v of [s.last_seq, engine.last_seq]) {
		if (typeof v === 'number' && Number.isFinite(v)) {
			out.last_seq = v;
			break;
		}
	}
	for (const v of [s.goals, s.running_goals, counts.goals, counts.running_goals]) {
		if (typeof v === 'number' && Number.isFinite(v)) {
			out.goals = v;
			break;
		}
	}
	return out;
};

export const getBanyanStatus = async (token: string = localStorage.token): Promise<BanyanEngineStatus> => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/status`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	const raw: any = await res.json();
	const engine = raw?.engine ?? {};
	const unread = raw?.counts?.inbox ?? {};
	return {
		engine: {
			status: String(engine?.status ?? 'unknown'),
			last_seq: typeof engine?.last_seq === 'number' ? engine.last_seq : undefined,
			paused: !!engine?.paused,
			home: engine?.home ? String(engine.home) : undefined,
			workspace: engine?.workspace ? String(engine.workspace) : undefined,
			version: engine?.version ? String(engine.version) : undefined
		},
		sidecar: {
			ok: !!raw?.sidecar?.ok,
			roles: raw?.sidecar?.roles ?? undefined
		},
		tiers: asArray(raw?.tiers).map((t: any) => ({
			id: String(t?.id ?? ''),
			label: t?.label ? String(t.label) : undefined,
			desc: t?.desc ? String(t.desc) : undefined,
			model: t?.model ? String(t.model) : undefined,
			keyed: !!t?.keyed,
			default: !!t?.default
		})),
		agents: asArray(raw?.agents).map((a: any) => ({
			name: String(a?.name ?? ''),
			description: a?.description ? String(a.description) : undefined,
			tier: a?.tier ? String(a.tier) : undefined,
			tools: asArray(a?.tools).map((t: any) => String(t)),
			memory: a?.memory ? String(a.memory) : undefined,
			output: a?.output ? String(a.output) : undefined
		})),
		counts: {
			inbox: {
				decision: Number(unread?.decision ?? 0),
				done: Number(unread?.done ?? 0),
				notice: Number(unread?.notice ?? 0)
			},
			plans_running: Number(raw?.counts?.plans_running ?? 0)
		}
	};
};
