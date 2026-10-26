// C3b 设备页纯函数单测:formatNodeHeartbeatAge / isNodeOnline / nodeStatusSummary
// (redGrouping.test.ts 同款)。在线判定正本=引擎 180s(C3 协议锁定),前端
// 只做兜底口径;status 为引擎侧自由形状的宽松载荷,摘要提取必须全防御。
import { describe, expect, it } from 'vitest';
import {
	formatNodeHeartbeatAge,
	isNodeOnline,
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
		expect(s).toEqual({ version: 'fa24340', uptime: '3600', last_seq: 5, goals: 3 });
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
			counts: { running_goals: NaN }
		});
		expect(s).toEqual({ version: 'fa24340' });
	});
});
