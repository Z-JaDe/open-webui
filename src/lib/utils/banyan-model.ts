/**
 * banyan 引擎模型判定(对话面共享判据;照后端
 * open_webui/utils/banyan_attach.is_banyan_model 口径,两侧互指):
 * - v3.1 引擎 /v1/models 条目原样透传:顶层 `meta.kind === 'banyan'`
 *   (兼容旧值 'tier' / 'space');
 * - `banyan-` 前缀 id 兜底(v3 前形态兼容:v3.1 起 id=真模型名,不再命中)。
 *
 * banyan 架构下模型参数归引擎档位、人格归 Agent md 正本——
 * 对话高级设置(Controls 旋钮)与个人区 system prompt 对引擎模型是
 * 死旋钮/人格冲突源,调用点据此整体隐藏。
 */
export const isBanyanTierModel = (
	model?: { id?: string; meta?: Record<string, unknown> } | null
): boolean => {
	if (!model) return false;
	const kind = (model as { meta?: Record<string, unknown> })?.meta?.kind;
	if (kind === 'tier' || kind === 'space' || kind === 'banyan') return true;
	return String(model?.id ?? '').startsWith('banyan-');
};
