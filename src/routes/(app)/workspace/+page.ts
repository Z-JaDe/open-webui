// v3 工作空间(设计-工作空间v1):旧 Open WebUI 工作空间页已删除(与 banyan 空间概念
// 重复,用户裁决直接删);旧链接一律重定向到新空间页。
import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = () => {
	throw redirect(302, '/workspaces');
};
