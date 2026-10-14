// banyan 组件 mock 故事数据（story 开关）。
//
// 用法一（组件内）：<PlanCard mock /> 直接渲染内置样例；
// 用法二（路由）：URL 加 ?mock=1，路由层把 mock 事件喂给组件，不请求引擎。
// 无法真连引擎时的验证门槛靠这份数据走通全部渲染路径。

import type {
	BanyanBranchEvent,
	BanyanPlanEvent,
	BanyanSubagentEvent,
	BanyanToolEvent,
	BanyanWaveUpdateEvent
} from './types';

const now = Date.now();

export const mockPlanEvent: BanyanPlanEvent = {
	type: 'plan',
	plan_id: 'plan-mock-001',
	title: '重构 banyan 调度器为波次模型',
	status: 'pending',
	hypothesis: '现有 scheduler 串行执行是吞吐瓶颈；按依赖分波并发可在不牺牲正确性的前提下提速。',
	waves: [
		{
			index: 1,
			title: '探路',
			tasks: [
				{ task_id: 't-101', title: '梳理现有依赖图', deps: [] },
				{ task_id: 't-102', title: '锁定回归基线', deps: [] }
			]
		},
		{
			index: 2,
			title: '改造',
			depends_on: [1],
			tasks: [
				{ task_id: 't-201', title: '实现波次调度器', deps: ['t-101'] },
				{ task_id: 't-202', title: '迁移存量用例', deps: ['t-101', 't-102'] }
			]
		},
		{
			index: 3,
			title: '收口',
			depends_on: [2],
			tasks: [{ task_id: 't-301', title: '全量回归 + 落账断言', deps: ['t-201', 't-202'] }]
		}
	],
	acceptance: ['167 个存量用例全绿', '波次并发度 ≥ 3', 'SIGKILL 后重启可恢复'],
	risks: ['依赖图解析错误可能导致空转', '波次收口与账本水位不一致'],
	rollback: 'revert 调度器切换 commit，chat.db/K1 不受伤',
	alt_option: '保守方案：仅并行化无依赖任务，不做完整波次模型（收益约 40%，风险更低）',
	ts: now - 1000 * 60 * 12
};

export const mockWaveUpdateEvents: BanyanWaveUpdateEvent[] = [
	{
		type: 'wave_update',
		plan_id: 'plan-mock-001',
		wave: 1,
		tasks: [
			{ task_id: 't-101', title: '梳理现有依赖图', status: 'done', detail: '17 节点 23 边' },
			{ task_id: 't-102', title: '锁定回归基线', status: 'done', detail: '基线 commit 9f31c2' }
		],
		ts: now - 1000 * 60 * 9
	},
	{
		type: 'wave_update',
		plan_id: 'plan-mock-001',
		wave: 2,
		tasks: [
			{ task_id: 't-201', title: '实现波次调度器', status: 'running', detail: '依赖单据生成中' },
			{ task_id: 't-202', title: '迁移存量用例', status: 'pending', deps: ['t-101', 't-102'] }
		],
		ts: now - 1000 * 60 * 3
	}
];

export const mockToolEvents: BanyanToolEvent[] = [
	{
		type: 'tool',
		call_id: 'call-01',
		name: 'read',
		args_summary: 'backend/scheduler.py',
		status: 'ok',
		output_summary: '412 行',
		started_at: now - 1000 * 60 * 10,
		ended_at: now - 1000 * 60 * 10 + 1200
	},
	{
		type: 'tool',
		call_id: 'call-02',
		name: 'grep',
		args_summary: '"def schedule" backend/',
		status: 'ok',
		output_summary: '命中 6 处',
		started_at: now - 1000 * 60 * 9,
		ended_at: now - 1000 * 60 * 9 + 340
	},
	{
		type: 'tool',
		call_id: 'call-03',
		name: 'bash',
		args_summary: 'pytest -x tests/test_scheduler.py',
		status: 'error',
		output_summary: '2 failed / 14 passed',
		started_at: now - 1000 * 60 * 5,
		ended_at: now - 1000 * 60 * 5 + 21000
	},
	{
		type: 'tool',
		call_id: 'call-04',
		name: 'edit',
		args_summary: 'backend/scheduler.py:88',
		status: 'running',
		started_at: now - 1000 * 40
	}
];

export const mockSubagentEvents: BanyanSubagentEvent[] = [
	{
		type: 'subagent',
		subagent_id: 'sa-explorer-1',
		role: 'explorer',
		title: '依赖图探索',
		latest_action: '正在读取 scheduler.py 的依赖声明',
		status: 'running',
		session_id: 'pi-sess-explorer-1',
		started_at: now - 1000 * 60 * 11
	},
	{
		type: 'subagent',
		subagent_id: 'sa-worker-1',
		role: 'worker',
		title: '波次调度器实现',
		latest_action: '编写 merge queue 冲突检测',
		status: 'running',
		session_id: 'pi-sess-worker-1',
		started_at: now - 1000 * 60 * 4
	},
	{
		type: 'subagent',
		subagent_id: 'sa-regress-1',
		role: 'regressor',
		title: '回归攻击',
		latest_action: '已产出 3 个失败断言，等待人工分流',
		status: 'done',
		session_id: 'pi-sess-regress-1',
		started_at: now - 1000 * 60 * 8,
		ended_at: now - 1000 * 60 * 2
	}
];

export const mockBranchEvent: BanyanBranchEvent = {
	type: 'branch',
	branches: [
		{ id: 'round-1', label: '轮 1 · 探路', active: false },
		{ id: 'round-2a', label: '轮 2 · 波次模型', active: true },
		{ id: 'round-2b', label: '轮 2 · 保守并行', active: false }
	],
	ts: now - 1000 * 60 * 6
};

/** ResponseMessage 场景：按序混合事件流（branch 在最前，符合“挂消息块顶端”） */
export const mockMessageEvents: (BanyanBranchEvent | BanyanPlanEvent | BanyanWaveUpdateEvent | BanyanToolEvent | BanyanSubagentEvent)[] =
	[
		mockBranchEvent,
		mockPlanEvent,
		...mockWaveUpdateEvents,
		...mockToolEvents,
		...mockSubagentEvents
	];
