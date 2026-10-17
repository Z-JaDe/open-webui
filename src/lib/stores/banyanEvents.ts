// banyan K1 事件流订阅(D15/F8):引擎 /api/events 全局推流全部事件,经 fork 后端
// /banyan/api/events SSE 透传(routers/banyan.py 专用端点)。前端单例 EventSource
// (浏览器原生;断线退避重连由浏览器承担,不手动重试),供徽标/方案页/信箱页/日历页
// "关注 kinds"事件驱动重取——引擎跑完即见,不靠轮询猜(D15:60s 徽标轮询退役)。
//
// 帧契约(引擎 backend/banyan/human/api.py /api/events):
//   hello 帧  {kind:'hello', seq}        连接建立即推(回显当前基线)
//   事件帧    {seq, kind, ref, payload}  kind 点分前缀:inbox.* / orchestration.* / calendar.*
//   keepalive 15s 注释帧(': keepalive') 原生 EventSource 自动忽略

import { BANYAN_API_BASE_URL } from '$lib/apis/banyan';

export type BanyanEventFrame = {
	seq: number;
	kind: string;
	ref?: string;
	payload?: Record<string, any>;
};

type BanyanEventMatcher = {
	prefixes: string[];
	cb: (frame: BanyanEventFrame) => void;
};

let source: EventSource | null = null;
const matchers = new Set<BanyanEventMatcher>();

const matches = (m: BanyanEventMatcher, kind: string) =>
	m.prefixes.some((p) => kind === p || kind.startsWith(p));

const dispatch = (frame: BanyanEventFrame) => {
	for (const m of matchers) {
		if (matches(m, frame.kind)) {
			try {
				m.cb(frame);
			} catch (e) {
				console.error('banyanEvents: listener failed', e);
			}
		}
	}
};

const ensureSource = () => {
	if (source || typeof EventSource === 'undefined') return;
	source = new EventSource(`${BANYAN_API_BASE_URL}/events`);
	source.onmessage = (e: MessageEvent) => {
		let frame: BanyanEventFrame;
		try {
			frame = JSON.parse(e.data);
		} catch {
			return;
		}
		// hello 帧只是基线回显,不触发重取;断线重连后数据快照由订阅方各自的
		// 首次 load 兜底(数据在引擎,丢的只是通知——D15 口径)。
		if (!frame || typeof frame.kind !== 'string' || frame.kind === 'hello') return;
		dispatch(frame);
	};
	// onerror:浏览器原生按内置间隔退避重连;引擎不可达是常态,静默。
	source.onerror = () => {};
};

/**
 * 订阅 K1 事件(点分前缀匹配,如 ['inbox.'] 或 ['orchestration.','calendar.'])。
 * 返回退订函数;最后一个订阅者退订时关闭底层 EventSource。
 */
export const subscribeBanyanEvents = (
	prefixes: string[],
	cb: (frame: BanyanEventFrame) => void
): (() => void) => {
	ensureSource();
	const matcher: BanyanEventMatcher = { prefixes, cb };
	matchers.add(matcher);
	return () => {
		matchers.delete(matcher);
		if (matchers.size === 0 && source) {
			source.close();
			source = null;
		}
	};
};

/**
 * 重取助手:把事件到达翻译成一次 load 重入。
 * - 后台只记待办,回前台补取一次(D15:"页面在 focus 时才重取,防后台风暴");
 * - 简单节流(默认 3s):窗口内多次事件只 trailing 补跑一次,终态不丢。
 */
export const createBanyanRefresher = (
	refresh: () => unknown,
	opts: { minIntervalMs?: number; requireVisible?: boolean } = {}
) => {
	const minIntervalMs = opts.minIntervalMs ?? 3000;
	const requireVisible = opts.requireVisible ?? true;
	let lastRun = 0;
	let pending = false;
	let timer: ReturnType<typeof setTimeout> | null = null;

	const run = () => {
		lastRun = Date.now();
		pending = false;
		Promise.resolve()
			.then(() => refresh())
			.catch(() => {});
	};

	const onVisible = () => {
		if (!document.hidden && pending) run();
	};

	if (requireVisible && typeof document !== 'undefined') {
		document.addEventListener('visibilitychange', onVisible);
	}

	const trigger = () => {
		if (requireVisible && typeof document !== 'undefined' && document.hidden) {
			pending = true;
			return;
		}
		const wait = minIntervalMs - (Date.now() - lastRun);
		if (wait <= 0) {
			run();
			return;
		}
		pending = true;
		if (!timer) {
			timer = setTimeout(() => {
				timer = null;
				if (pending) run();
			}, wait);
		}
	};

	const dispose = () => {
		if (timer) {
			clearTimeout(timer);
			timer = null;
		}
		if (typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', onVisible);
		}
	};

	return { trigger, dispose };
};
