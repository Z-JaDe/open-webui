// banyan 信箱 Web 通知(F4/D10):decision 类落箱=「需要人裁决」才打扰,done/notice
// 静默落箱只动计数(信箱徽标负责)。复用 M-8 通知语义(与 routes/+layout.svelte 的
// socket 处理同款):
//   - 应用内 toast(NotificationToast,点击跳 /inbox);
//   - Web Notification 仅在页面后台 && 本 tab 是最后活跃 tab && 用户开了通知设置时发
//     (hasFocus 抑制:前台可见不打扰系统通知);权限 lazy 请求;点击聚焦并跳转。
// 去重:按卡 id(inbox.opened 天然边沿触发,这里防御同一卡重复帧)。

import { toast } from 'svelte-sonner';
import { goto } from '$app/navigation';
import { get } from 'svelte/store';
import { isLastActiveTab, settings } from '$lib/stores';
import { WEBUI_BASE_URL } from '$lib/constants';
import NotificationToast from '$lib/components/NotificationToast.svelte';

const notifiedIds = new Set<string>();

const fireNotification = (title: string, body: string) => {
	try {
		const notification = new Notification(`${title} / Open WebUI`, {
			body,
			// LICENSE covers this Open WebUI notification identifier.
			// Do not alter, remove, obscure, or replace it except as LICENSE permits:
			// https://docs.openwebui.com/license.
			icon: `${WEBUI_BASE_URL}/static/favicon.png`
		});
		notification.onclick = () => {
			window.focus();
			goto('/inbox');
		};
	} catch {
		// 通知失败静默(徽标仍事件驱动刷新,不依赖本通道)
	}
};

/**
 * decision 类信箱卡落箱通知。card 来自 K1 inbox.opened 帧 payload
 * (id/kind/category/title/body),由订阅方(Sidebar)判 category 后调用。
 */
export const notifyBanyanDecision = (card: { id?: string; title: string; body?: string }) => {
	if (card.id) {
		if (notifiedIds.has(card.id)) return;
		notifiedIds.add(card.id);
		if (notifiedIds.size > 200) {
			const oldest = notifiedIds.values().next().value;
			if (oldest !== undefined) notifiedIds.delete(oldest);
		}
	}

	// `as any`:与 +layout.svelte 同款用法;此处是 .ts,svelte-sonner 的 ComponentType
	// 对 Svelte 组件 props 做不变型推导,不收窄会报 svelte-check 误报(构建无碍)。
	toast.custom(NotificationToast as any, {
		componentProps: {
			onClick: () => {
				goto('/inbox');
			},
			title: card.title,
			content: card.body ?? ''
		},
		duration: 30000,
		unstyled: true
	});

	// Web Notification:后台 + 最后活跃 tab + 用户开启通知设置(M-8 同门槛)
	if (typeof document === 'undefined' || document.visibilityState === 'visible') return;
	if (!get(isLastActiveTab)) return;
	if (!(get(settings)?.notificationEnabled ?? false)) return;
	if (typeof Notification === 'undefined' || Notification.permission === 'denied') return;

	if (Notification.permission === 'default') {
		Notification.requestPermission()
			.then((permission) => {
				if (permission === 'granted') fireNotification(card.title, card.body ?? '');
			})
			.catch(() => {});
		return;
	}
	fireNotification(card.title, card.body ?? '');
};
