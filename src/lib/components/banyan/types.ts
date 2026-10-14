// banyan 渲染协议（统一设计 §6.2 / §8 G1）
//
// 引擎在 OpenAI 兼容 SSE 之外发送私有行：data:{"banyan":{type,...}}。
// fork 后端把它转发为 socket 事件 {type:'banyan', data:<BanyanEvent>}，
// Chat.svelte 钩点①将其追加进 message.banyanEvents[]，本目录组件按序渲染。
//
// 所有事件共享字段：type（判别字段）+ 可选 ts（引擎时间戳，epoch ms）。

/** 计划卡中的一个波次（静态规划视图） */
export type BanyanPlanWave = {
	/** 波次序号（从 1 开始） */
	index: number;
	title?: string;
	/** 依赖的波次序号 */
	depends_on?: number[];
	tasks: BanyanPlanTask[];
};

export type BanyanPlanTask = {
	task_id: string;
	title: string;
	/** 依赖的 task_id 列表 */
	deps?: string[];
};

/** plan 事件 → PlanCard */
export type BanyanPlanEvent = {
	type: 'plan';
	plan_id: string;
	title?: string;
	/** pending=待批准；approved/rejected/revised 为 resolve 后回填 */
	status: 'pending' | 'approved' | 'rejected' | 'revised';
	/** 核心假设 */
	hypothesis?: string;
	waves: BanyanPlanWave[];
	/** 验收标准 */
	acceptance?: string[];
	/** 风险 */
	risks?: string[];
	/** 回滚方式 */
	rollback?: string;
	/** 备选方案（“选 B”按钮提交该选项） */
	alt_option?: string;
	ts?: number;
};

export type BanyanTaskStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped' | 'blocked';

/** wave_update 事件 → WaveBoard（同一 task_id 按 upsert 合并，不刷屏） */
export type BanyanWaveUpdateEvent = {
	type: 'wave_update';
	plan_id: string;
	wave: number;
	tasks: {
		task_id: string;
		title?: string;
		status: BanyanTaskStatus;
		/** 依赖的 task_id 列表；依赖失败且未完成 → 沿依赖标红(blocked) */
		deps?: string[];
		/** 单行进度说明 */
		detail?: string;
	}[];
	ts?: number;
};

/** tool 事件 → ToolTimeline（按 call_id upsert；默认折叠只显示最近 3 行） */
export type BanyanToolEvent = {
	type: 'tool';
	call_id: string;
	name: string;
	args_summary?: string;
	status: 'running' | 'ok' | 'error';
	output_summary?: string;
	started_at?: number;
	ended_at?: number;
	ts?: number;
};

/** subagent 事件 → SubagentCard（按 subagent_id upsert；latest_action 换词动画） */
export type BanyanSubagentEvent = {
	type: 'subagent';
	subagent_id: string;
	role?: string;
	title?: string;
	latest_action?: string;
	status: 'running' | 'done' | 'failed' | 'stopped';
	/** 子会话入口（引擎子会话 id） */
	session_id?: string;
	started_at?: number;
	ended_at?: number;
	ts?: number;
};

/** branch 事件 → TreeSwitcher（同一消息块只保留最新一份分支 pills） */
export type BanyanBranchEvent = {
	type: 'branch';
	branches: {
		id: string;
		label: string;
		active: boolean;
	}[];
	ts?: number;
};

export type BanyanEvent =
	| BanyanPlanEvent
	| BanyanWaveUpdateEvent
	| BanyanToolEvent
	| BanyanSubagentEvent
	| BanyanBranchEvent;

/** PlanCard 按钮提交给引擎的决策体（POST /banyan/api/plans/:id/resolve） */
export type BanyanPlanResolveBody = {
	decision: 'approved' | 'rejected' | 'revised';
	/** decision='revised' 时选择备选方案时附带说明 */
	choice?: string;
};

export const BANYAN_PLAN_STATUS_LABEL: Record<BanyanPlanEvent['status'], string> = {
	pending: '待批准',
	approved: '已批准',
	rejected: '已驳回',
	revised: '已选 B'
};

export const BANYAN_TASK_STATUS_LABEL: Record<BanyanTaskStatus, string> = {
	pending: '排队',
	running: '执行中',
	done: '完成',
	failed: '失败',
	skipped: '跳过',
	blocked: '受阻'
};

/** 判别是否为合法 banyan 事件（容错：包一层 {banyan:{...}} 的也展开） */
export const unwrapBanyanEvent = (data: unknown): BanyanEvent | null => {
	if (!data || typeof data !== 'object') return null;
	const payload = (data as any).banyan ?? data;
	if (!payload || typeof payload !== 'object' || typeof payload.type !== 'string') return null;
	return payload as BanyanEvent;
};

/** 波次×任务进度格的归并规则：wave_update.tasks 按 task_id upsert 到现有格子上 */
export const mergeWaveTasks = (
	existing: Record<string, BanyanWaveUpdateEvent['tasks'][number]>,
	incoming: BanyanWaveUpdateEvent['tasks']
): Record<string, BanyanWaveUpdateEvent['tasks'][number]> => {
	const next = { ...existing };
	for (const task of incoming) {
		const prev = next[task.task_id];
		next[task.task_id] = {
			...prev,
			...task,
			title: task.title ?? prev?.title ?? task.task_id
		};
	}
	return next;
};

/**
 * 依赖传导：某任务失败时，把所有（直接/间接）依赖它的未完成任务标为 blocked。
 * blocked 属于渲染层推断，不回写正本。
 */
export const propagateBlocked = (
	tasks: Record<string, BanyanWaveUpdateEvent['tasks'][number]>
): Record<string, BanyanWaveUpdateEvent['tasks'][number]> => {
	const failed = new Set(
		Object.values(tasks)
			.filter((t) => t.status === 'failed')
			.map((t) => t.task_id)
	);
	if (failed.size === 0) return tasks;

	const next = { ...tasks };
	let changed = true;
	while (changed) {
		changed = false;
		for (const task of Object.values(next)) {
			if (task.status !== 'pending' && task.status !== 'running') continue;
			const blocked = (task.deps ?? []).some((dep) => failed.has(dep));
			if (blocked && next[task.task_id]?.status !== 'blocked') {
				next[task.task_id] = { ...task, status: 'blocked' };
				changed = true;
			}
		}
	}
	return next;
};

/** epoch ms → 耗时字符串 */
export const formatDuration = (start?: number, end?: number): string => {
	if (!start) return '';
	const endMs = end ?? Date.now();
	const seconds = Math.max(0, Math.round((endMs - start) / 1000));
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	return `${minutes}m ${seconds % 60}s`;
};

/** epoch ms → HH:mm:ss */
export const formatClock = (ts?: number): string => {
	if (!ts) return '';
	const date = new Date(ts);
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};
