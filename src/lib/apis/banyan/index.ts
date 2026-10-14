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
export const getBanyanRegistry = async (token: string = localStorage.token) => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/registry`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return (await res.json()) as { items: BanyanRegistryEntry[] };
};

////////////////////////////
// 语义卡 /cards
////////////////////////////
export const getBanyanCards = async (token: string = localStorage.token) => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/cards`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return (await res.json()) as { items: BanyanCard[] };
};

export const resolveBanyanCard = async (
	cardId: string,
	decision: 'approved' | 'rejected',
	token: string = localStorage.token
) => {
	return request('POST', `/cards/${encodeURIComponent(cardId)}/resolve`, { decision });
};

////////////////////////////
// 事件浏览 /audit
////////////////////////////
export const getBanyanAuditEvents = async (
	query: { chat_id?: string; type?: string; limit?: number } = {},
	token: string = localStorage.token
) => {
	const params = new URLSearchParams();
	if (query.chat_id) params.set('chat_id', query.chat_id);
	if (query.type) params.set('type', query.type);
	params.set('limit', String(query.limit ?? 200));
	const res = await fetch(`${BANYAN_API_BASE_URL}/audit?${params.toString()}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return (await res.json()) as { items: BanyanAuditEvent[] };
};

////////////////////////////
// 方案与波次 /plans
////////////////////////////
export const getBanyanPlan = async (planId: string, token: string = localStorage.token) => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/plans/${encodeURIComponent(planId)}`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return (await res.json()) as BanyanPlanSnapshot;
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
export const getBanyanTree = async (chatId: string, token: string = localStorage.token) => {
	const res = await fetch(`${BANYAN_API_BASE_URL}/chats/${encodeURIComponent(chatId)}/tree`, {
		method: 'GET',
		headers: { Authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return (await res.json()) as BanyanTreeSnapshot;
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
