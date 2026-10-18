// RV-D P1-1 红绿分组轴单测:引擎登记簿的 fingerprint 是 sha256 十六进制哈希
// (不含 "red-" 前缀),"red-" 前缀长在 kind 上("red-shell")——分组轴必须是
// kind,指纹轴在真实数据上会把红测整组漏进"交付验收"(回归元环文案颠倒)。
import { describe, expect, it } from 'vitest';
import { isRedAssertion } from './index';

describe('isRedAssertion(RV-D P1-1:红测分组轴=kind,非 fingerprint)', () => {
	it('红测行按 kind="red-shell" 分入红组(fingerprint 是纯哈希,无前缀)', () => {
		expect(
			isRedAssertion({
				kind: 'red-shell',
				fingerprint: '9f31c2b7a4d5e6f7' // 真实引擎指纹形态:sha256 十六进制,不含 "red-"
			})
		).toBe(true);
	});

	it('验收行 kind="shell" 不误判为红测(契约轴在 kind,不在指纹)', () => {
		expect(isRedAssertion({ kind: 'shell', fingerprint: '5c2e8a1d7f3b9046' })).toBe(false);
	});

	it('引擎取不到 kind 时降级不误报红组(空 kind=非红测)', () => {
		expect(isRedAssertion({ kind: '', fingerprint: '' })).toBe(false);
	});

	it('防回归:指纹前缀轴是错轴——红指纹形如 "red-..." 的旧契约不再被认可', () => {
		// 旧 fork mock 曾造出 "red-9f31c2b7a4d5e6f7" 这种指纹,引擎永远不会产生;
		// 即便指纹带前缀,只要 kind 是 shell 就不是红测(轴唯一定在 kind)。
		expect(isRedAssertion({ kind: 'shell', fingerprint: 'red-9f31c2b7a4d5e6f7' })).toBe(false);
		expect(isRedAssertion({ kind: 'red-shell', fingerprint: 'red-9f31c2b7a4d5e6f7' })).toBe(true);
	});
});
