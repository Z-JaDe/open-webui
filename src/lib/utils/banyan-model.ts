/**
 * banyan 档位模型判定(RF-34,对话面共享判据;照后端
 * open_webui/utils/banyan_attach.is_banyan_model 口径):
 * - 引擎 /v1/models 档位条目原样透传:顶层 `meta.kind === 'tier'`;
 * - `banyan-` 前缀 id 兜底(banyan-duty / banyan-fast)。
 *
 * banyan 架构下模型参数归档位(引擎 tier)、人格归 Agent md 正本——
 * 对话高级设置(Controls 旋钮)与个人区 system prompt 对档位模型是
 * 死旋钮/人格冲突源,调用点据此整体隐藏。
 */
export const isBanyanTierModel = (
	model?: { id?: string; meta?: Record<string, unknown> } | null
): boolean => {
	if (!model) return false;
	if ((model as { meta?: Record<string, unknown> })?.meta?.kind === 'tier') return true;
	return String(model?.id ?? '').startsWith('banyan-');
};
