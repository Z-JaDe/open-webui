// V4W-1/V4W-2 红测(mock fetch,nodeCommands.test.ts 同款):
// - getBanyanGoals:代理层聚合响应(云端条目 cloud:true / 顶层 cloud 状态)→
//   前端类型 BanyanGoalEntry.cloud 透传(缺省 undefined=本地);
// - getBanyanGoalConvs:云回退响应顶层 cloud:true → BanyanGoalConvs.cloud
//   (转录页云 goal 徽标数据面);
// - getBanyanStatus:顶层 cloud 状态(ok/host/engine 概要)透传;
// - getBanyanSystemTasks:引擎 GET /api/system-tasks {tasks:[{kind,ts,payload}]}
//   → BanyanSystemTask[](epoch 秒→ms;payload 摘要原样字符串);
// - systemTaskIcon/systemTaskLabel:kind 前缀→图标/词(审查🔍/知识📚/自动化⚙)。
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	getBanyanGoalConvs,
	getBanyanGoals,
	getBanyanStatus,
	getBanyanSystemTasks,
	systemTaskIcon,
	systemTaskLabel
} from './index';

const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
let responseBody: unknown = {};

const okResponse = () =>
	Promise.resolve({
		ok: true,
		status: 200,
		statusText: 'OK',
		json: () => Promise.resolve(responseBody)
	});

beforeEach(() => {
	calls.length = 0;
	responseBody = {};
	(globalThis as any).localStorage = { token: 'test-jwt' };
	vi.stubGlobal(
		'fetch',
		vi.fn((url: string, init?: RequestInit) => {
			calls.push({ url, init });
			return okResponse();
		})
	);
});

describe('getBanyanGoals 云来源标记透传', () => {
	it('云端条目 cloud:true 透传,本地条目 cloud=undefined', async () => {
		responseBody = {
			goals: [
				{ goalId: 'g-local', objective: '本地', kind: 'chat', phase: 'run', status: 'running', createdAt: 100, settledAt: null, summary: null, error: null },
				{ goalId: 'g-cloud', objective: '杭州审查', kind: 'review', phase: 'done', status: 'completed', createdAt: 200, settledAt: 300, summary: 's', error: null, cloud: true }
			],
			cloud: { ok: true, host: 'login.pyrris.com', count: 1 }
		};
		const goals = await getBanyanGoals();
		expect(goals).toHaveLength(2);
		expect(goals[0].cloud).toBeUndefined();
		expect(goals[1].cloud).toBe(true);
		expect(calls[0].url).toContain('/banyan/api/goals');
	});
});

describe('getBanyanGoalConvs 云回退徽标数据面', () => {
	it('顶层 cloud:true 透传(转录页可看云 goal)', async () => {
		responseBody = {
			manager: { name: '管理者', conversationId: 'c1', transcript: [] },
			subagents: [],
			reviewers: [],
			cloud: true
		};
		const convs = await getBanyanGoalConvs('g-cloud');
		expect(convs.cloud).toBe(true);
		expect(calls[0].url).toContain('/banyan/api/goals/g-cloud/convs');
	});

	it('本地 convs 无 cloud 键(undefined,不渲染云徽标)', async () => {
		responseBody = {
			manager: { name: '管理者', conversationId: 'c1', transcript: [] },
			subagents: [],
			reviewers: []
		};
		const convs = await getBanyanGoalConvs('g-local');
		expect(convs.cloud).toBeUndefined();
	});
});

describe('getBanyanStatus 云概要透传', () => {
	it('顶层 cloud{ok,host,engine} → BanyanEngineStatus.cloud', async () => {
		responseBody = {
			engine: { status: 'ok', version: '4.0' },
			sidecar: { ok: true },
			tiers: [],
			agents: [],
			counts: { inbox: {}, plans_running: 0 },
			cloud: { ok: true, host: 'login.pyrris.com', engine: { status: 'ok', last_seq: 9, version: '4.1' } }
		};
		const st = await getBanyanStatus();
		expect(st.cloud?.ok).toBe(true);
		expect(st.cloud?.host).toBe('login.pyrris.com');
		expect(st.cloud?.engine?.version).toBe('4.1');
	});

	it('云挂时 ok:false + error 透传(页面诚实展示)', async () => {
		responseBody = {
			engine: { status: 'ok' },
			sidecar: { ok: false },
			tiers: [],
			agents: [],
			counts: { inbox: {}, plans_running: 0 },
			cloud: { ok: false, host: 'login.pyrris.com', error: 'ConnectError' }
		};
		const st = await getBanyanStatus();
		expect(st.cloud?.ok).toBe(false);
		expect(st.cloud?.error).toBe('ConnectError');
	});

	it('env 缺(代理零行为)无 cloud 键 → undefined 不炸', async () => {
		responseBody = {
			engine: { status: 'ok' },
			sidecar: { ok: false },
			tiers: [],
			agents: [],
			counts: { inbox: {}, plans_running: 0 }
		};
		const st = await getBanyanStatus();
		expect(st.cloud).toBeUndefined();
	});
});

describe('getBanyanSystemTasks 引擎系统任务读面', () => {
	it('{tasks:[…]} → BanyanSystemTask[](ts 秒→ms;payload 摘要字符串)', async () => {
		responseBody = {
			tasks: [
				{ kind: 'review.run', ts: 1793000000, payload: '{"run_id":"rev-1","findings_n":2}' },
				{ kind: 'knowledge.settled', ts: 1793000060, payload: '{"settled":["g1"]}' },
				{ kind: 'automation.fired', ts: 1793000120, payload: '{"id":"aut-1","status":"ok"}' }
			]
		};
		const tasks = await getBanyanSystemTasks({ limit: 50 });
		expect(calls[0].url).toContain('/banyan/api/system-tasks?limit=50');
		expect(tasks).toHaveLength(3);
		expect(tasks[0].kind).toBe('review.run');
		expect(tasks[0].ts).toBe(1793000000 * 1000);
		expect(tasks[0].payload).toContain('rev-1');
	});

	it('空任务 → [](引擎可达但无系统任务事件)', async () => {
		responseBody = { tasks: [] };
		const tasks = await getBanyanSystemTasks();
		expect(tasks).toEqual([]);
	});
});

describe('systemTaskIcon/systemTaskLabel kind 前缀映射', () => {
	it('三前缀图标:审查🔍/知识📚/自动化⚙;未知前缀中性兜底', () => {
		expect(systemTaskIcon('review.run')).toBe('🔍');
		expect(systemTaskIcon('review.finding')).toBe('🔍');
		expect(systemTaskIcon('knowledge.settled')).toBe('📚');
		expect(systemTaskIcon('knowledge.goal_started')).toBe('📚');
		expect(systemTaskIcon('automation.fired')).toBe('⚙');
		expect(systemTaskIcon('other.thing')).toBe('·');
	});

	it('三前缀词表:审查/知识/自动化;未知原样', () => {
		expect(systemTaskLabel('review.run')).toBe('审查');
		expect(systemTaskLabel('knowledge.settled')).toBe('知识');
		expect(systemTaskLabel('automation.fired')).toBe('自动化');
		expect(systemTaskLabel('weird.kind')).toBe('weird.kind');
	});
});
