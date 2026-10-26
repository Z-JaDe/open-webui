// C3b 设备页纯函数单测:formatNodeHeartbeatAge / isNodeOnline / nodeStatusSummary
// (redGrouping.test.ts 同款)。在线判定正本=引擎 180s(C3 协议锁定),前端
// 只做兜底口径;status 为引擎侧自由形状的宽松载荷,摘要提取必须全防御。
// RF-C3c:F-2 夹具补引擎六键真实形状(goals_digest.active_goals)/F-7 uptime
// 人化/F-1 nodeSpaces(节点上报空间目录)。
import { describe, expect, it } from 'vitest';
import {
	formatNodeHeartbeatAge,
	formatNodeUptime,
	isNodeOnline,
	nodeSpaces,
	nodeStatusSummary,
	NODE_OFFLINE_AFTER_MS
} from './index';

const NOW = 1_700_000_000_000; // 固定"现在",相对时间不随真实时钟漂

describe('formatNodeHeartbeatAge(心跳相对时间)', () => {
	it('刚刚:9 秒内与未来时间戳(客户端钟慢)都归「刚刚」,不渲染负数', () => {
		expect(formatNodeHeartbeatAge(NOW, NOW)).toBe('刚刚');
		expect(formatNodeHeartbeatAge(NOW - 9_000, NOW)).toBe('刚刚');
		expect(formatNodeHeartbeatAge(NOW + 120_000, NOW)).toBe('刚刚');
	});

	it('秒/分/时/天四档落档正确', () => {
		expect(formatNodeHeartbeatAge(NOW - 10_000, NOW)).toBe('10 秒前');
		expect(formatNodeHeartbeatAge(NOW - 59_000, NOW)).toBe('59 秒前');
		expect(formatNodeHeartbeatAge(NOW - 60_000, NOW)).toBe('1 分钟前');
		expect(formatNodeHeartbeatAge(NOW - 3_599_000, NOW)).toBe('59 分钟前');
		expect(formatNodeHeartbeatAge(NOW - 3_600_000, NOW)).toBe('1 小时前');
		expect(formatNodeHeartbeatAge(NOW - 86_400_000, NOW)).toBe('1 天前');
		expect(formatNodeHeartbeatAge(NOW - 10 * 86_400_000, NOW)).toBe('10 天前');
	});

	it('坏值防御:undefined/0/负数 → 「—」(不炸、不渲染 NaN)', () => {
		expect(formatNodeHeartbeatAge(undefined, NOW)).toBe('—');
		expect(formatNodeHeartbeatAge(0, NOW)).toBe('—');
		expect(formatNodeHeartbeatAge(-5, NOW)).toBe('—');
	});
});

describe('isNodeOnline(在线判定:引擎布尔为正本,缺布尔才前端兜底)', () => {
	it('引擎给了布尔 → 直接采信(true/false 均如此,180s 阈值是引擎侧职责)', () => {
		expect(isNodeOnline(true, undefined, NOW)).toBe(true);
		expect(isNodeOnline(false, NOW - 1_000, NOW)).toBe(false); // 心跳很新但引擎判离线:正本说了算
	});

	it('引擎未给布尔(形状漂移) → 按心跳距今兜底,180s 口径与协议一致', () => {
		expect(isNodeOnline(undefined, NOW - 179_000, NOW)).toBe(true);
		expect(isNodeOnline(undefined, NOW - 181_000, NOW)).toBe(false);
		expect(isNodeOnline(null, NOW, NOW)).toBe(true);
		expect(NODE_OFFLINE_AFTER_MS).toBe(180_000);
	});

	it('兜底分支的坏值:无心跳/非数字 → 判离线(缺证据不亮绿灯)', () => {
		expect(isNodeOnline(undefined, undefined, NOW)).toBe(false);
		expect(isNodeOnline(undefined, 0, NOW)).toBe(false);
		expect(isNodeOnline('yes' as unknown, undefined, NOW)).toBe(false);
	});
});

describe('nodeStatusSummary(宽松 status 载荷防御摘要:版本/uptime/last_seq/goals)', () => {
	it('RF-C3c F-2:引擎六键真实载荷(test_60s_beat_and_payload_shape 同形)四键全提取', () => {
		const s = nodeStatusSummary({
			version: '0.1.0',
			uptime_s: 3600.5,
			engine: { status: 'ok', paused: false, last_seq: 320 },
			goals_digest: { active_goals: 2, last_event_ts: 1792988399.0 },
			duty: { active_runners: 1 },
			memory: { rss_mb: 123.4 }
		});
		expect(s).toEqual({
			version: '0.1.0',
			uptime: '1h 0m',
			last_seq: 320,
			goals: 2 // goals_digest.active_goals——修前该键永远取不到(RV-C3 F-2)
		});
	});

	it('F-2:goals_digest.active_goals 为 null(goal 未接线诚实降级) → goals 不亮', () => {
		const s = nodeStatusSummary({
			version: '0.1.0',
			engine: { last_seq: 5 },
			goals_digest: { active_goals: null, last_event_ts: 0 }
		});
		expect(s.goals).toBeUndefined();
		expect(s.last_seq).toBe(5);
	});

	it('DA-2 心跳形状(嵌套 engine/counts)四键全提取', () => {
		const s = nodeStatusSummary({
			version: 'fa24340',
			engine: { last_seq: 320 },
			counts: { running_goals: 2 }
		});
		expect(s).toEqual({ version: 'fa24340', last_seq: 320, goals: 2 });
	});

	it('平铺形状与顶层 engine_version/uptime_s 键位也认(引擎侧自由形状)', () => {
		const s = nodeStatusSummary({
			engine_version: 'fa24340',
			uptime_s: 3600,
			last_seq: 5,
			goals: 3
		});
		expect(s).toEqual({ version: 'fa24340', uptime: '1h 0m', last_seq: 5, goals: 3 });
	});

	it('未知形状/坏值:空手而归不炸——页面渲染「节点未上报」而非报错', () => {
		expect(nodeStatusSummary(undefined)).toEqual({});
		expect(nodeStatusSummary(null)).toEqual({});
		expect(nodeStatusSummary('ok')).toEqual({});
		expect(nodeStatusSummary([1, 2])).toEqual({});
		expect(nodeStatusSummary({ version: '', last_seq: 'x', goals: null })).toEqual({});
	});

	it('非数字 last_seq/goals(字符串/NaN)跳过该键,其余键照常提取', () => {
		const s = nodeStatusSummary({
			version: 'fa24340',
			engine: { last_seq: '320' },
			goals_digest: { active_goals: 'many' },
			counts: { running_goals: NaN }
		});
		expect(s).toEqual({ version: 'fa24340' });
	});
});

describe('formatNodeUptime(RF-C3c F-7:uptime 人化,<60s→Ns,<3600→Nm Ns,否则 Nh Nm)', () => {
	it('三档落档正确(秒向下取整)', () => {
		expect(formatNodeUptime(0)).toBe('0s');
		expect(formatNodeUptime(45.2)).toBe('45s');
		expect(formatNodeUptime(59.9)).toBe('59s');
		expect(formatNodeUptime(60)).toBe('1m 0s');
		expect(formatNodeUptime(61)).toBe('1m 1s');
		expect(formatNodeUptime(3599)).toBe('59m 59s');
		expect(formatNodeUptime(3600)).toBe('1h 0m');
		expect(formatNodeUptime(3617.3)).toBe('1h 0m');
		expect(formatNodeUptime(7325)).toBe('2h 2m');
		expect(formatNodeUptime(90000)).toBe('25h 0m');
	});

	it('坏值防御:负数/NaN/Infinity → undefined(不渲染)', () => {
		expect(formatNodeUptime(-5)).toBeUndefined();
		expect(formatNodeUptime(NaN)).toBeUndefined();
		expect(formatNodeUptime(Infinity)).toBeUndefined();
	});
});

describe('nodeSpaces(RF-C3c F-1:节点上报的空间目录,chat_turn 下拉数据源)', () => {
	it('status.spaces [{id,name}] 提取;无/空/坏形状 → [](隐藏下拉显示默认会话)', () => {
		expect(
			nodeSpaces({ spaces: [{ id: 'alpha', name: '甲空间' }, { id: 'beta', name: '乙空间' }] })
		).toEqual([
			{ id: 'alpha', name: '甲空间' },
			{ id: 'beta', name: '乙空间' }
		]);
		expect(nodeSpaces(undefined)).toEqual([]);
		expect(nodeSpaces({})).toEqual([]);
		expect(nodeSpaces({ spaces: [] })).toEqual([]);
		expect(nodeSpaces({ spaces: 'alpha' })).toEqual([]);
		expect(nodeSpaces({ spaces: [{ id: 'a' }, null, { nope: 1 }] })).toEqual([
			{ id: 'a', name: 'a' }
		]);
	});
});
