// RF-C3c 红测(mock fetch):
// - F-1:sendBanyanNodeCommand 带/不带 space_id 两形态——chat_turn 载荷形态
//   由面板下拉决定,本测把线上形态(POST body)钉死;
// - F-3:listBanyanNodeCommands 读面——引擎 GET /api/nodes/{id}/commands 返回
//   {commands:[…]} 包装(协议口径同 F-10),行 {id,kind,created_at,claimed_at,
//   done_at,state(pending|claimed|done|expired),result(≤200 字摘要)} → 前端类型;
// - F-10:listBanyanNodes 主路径 {nodes:[…]} 包装(裸数组兜底保留,两形状回归钉子)。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	listBanyanNodeCommands,
	listBanyanNodes,
	sendBanyanNodeCommand
} from './index';

// node 环境:request() 读 localStorage.token——测试桩注入
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
	vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
		calls.push({ url, init });
		return okResponse();
	}));
});

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('F-1:sendBanyanNodeCommand 带/不带 space_id 两形态(mock fetch)', () => {
	it('面板选中空间 → POST body 的 payload 带 space_id', async () => {
		responseBody = { command_id: 'cmd_abc123' };
		const out = await sendBanyanNodeCommand('n-1', 'chat_turn', {
			text: '云指挥',
			space_id: 'alpha'
		});
		expect(out.command_id).toBe('cmd_abc123');
		expect(calls).toHaveLength(1);
		expect(calls[0].url).toBe('/banyan/api/nodes/n-1/commands');
		expect(calls[0].init?.method).toBe('POST');
		const body = JSON.parse(String(calls[0].init?.body));
		expect(body).toEqual({ kind: 'chat_turn', payload: { text: '云指挥', space_id: 'alpha' } });
	});

	it('节点未上报空间目录 → 载荷只有 text(不带 space_id 键)', async () => {
		await sendBanyanNodeCommand('n-1', 'chat_turn', { text: '裸文本' });
		const body = JSON.parse(String(calls[0].init?.body));
		expect(body).toEqual({ kind: 'chat_turn', payload: { text: '裸文本' } });
		expect('space_id' in body.payload).toBe(false);
	});
});

describe('F-3:listBanyanNodeCommands(指令历史读面)', () => {
	it('GET {commands:[…]} 包装,引擎行 → 前端类型(state 四态+epoch 秒→ms)', async () => {
		responseBody = {
			commands: [
				{
					id: 'cmd_done',
					kind: 'chat_turn',
					created_at: 1792988400,
					claimed_at: 1792988460,
					done_at: 1792988470,
					state: 'done',
					result: '好的,已执行'
				},
				{
					id: 'cmd_exp',
					kind: 'goal_abort',
					created_at: 1792987400,
					claimed_at: null,
					done_at: 1792988000,
					state: 'expired',
					result: 'expired: unclaimed >600s'
				},
				{
					id: 'cmd_pend',
					kind: 'goal_card_resolve',
					created_at: 1792988500,
					claimed_at: null,
					done_at: null,
					state: 'pending',
					result: ''
				}
			]
		};
		const rows = await listBanyanNodeCommands('n-1');
		expect(calls[0].url).toBe('/banyan/api/nodes/n-1/commands');
		expect(calls[0].init?.method).toBe('GET');
		expect(rows).toHaveLength(3);
		expect(rows[0]).toEqual({
			id: 'cmd_done',
			kind: 'chat_turn',
			created_at: 1792988400_000, // epoch 秒 → ms
			claimed_at: 1792988460_000,
			done_at: 1792988470_000,
			state: 'done',
			result: '好的,已执行'
		});
		expect(rows[2].state).toBe('pending');
		expect(rows[2].claimed_at).toBeUndefined();
	});

	it('空历史/坏形状防御:[] 不炸', async () => {
		responseBody = { commands: [] };
		expect(await listBanyanNodeCommands('n-1')).toEqual([]);
		responseBody = {};
		expect(await listBanyanNodeCommands('n-1')).toEqual([]);
	});
});

describe('F-10:listBanyanNodes 主路径 {nodes:[…]}(裸数组兜底保留)', () => {
	it('引擎实况形状:对象包装 → 取 nodes(主路径)', async () => {
		responseBody = {
			nodes: [{ node_id: 'n-1', name: 'mac', online: true, status: {} }]
		};
		const rows = await listBanyanNodes();
		expect(rows).toHaveLength(1);
		expect(rows[0].node_id).toBe('n-1');
		expect(rows[0].name).toBe('mac');
	});

	it('裸数组(形状漂移兜底)同样可用', async () => {
		responseBody = [{ node_id: 'n-2', name: 'cloud', online: false }];
		const rows = await listBanyanNodes();
		expect(rows).toHaveLength(1);
		expect(rows[0].node_id).toBe('n-2');
	});
});
