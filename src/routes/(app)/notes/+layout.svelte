<script lang="ts">
	// banyan D23（完整方案 §12.5）：Notes 禁用——笔记+note-chat 是方案外内容孤岛，
	// 个人手记走对话/知识卡。布局层直接渲染退役占位（覆盖 /notes、/notes/new、/notes/[id]，
	// 路由文件保留；恢复=换回 slot 并恢复后端 notes.enable 缺省）。
	// 后端开关跟进：ENABLE_NOTES（config 'notes.enable'）缺省翻转归 RF-10。
	import { WEBUI_NAME } from '$lib/stores';
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import FeatureRetired from '$lib/components/common/FeatureRetired.svelte';

	const i18n = getContext<Writable<i18nType>>('i18n');
</script>

<svelte:head>
	<!-- LICENSE covers this Open WebUI browser-title identifier.
	Do not alter, remove, obscure, or replace it except as LICENSE permits:
	https://docs.openwebui.com/license. -->
	<title>
		{$i18n.t('Notes')} / {$WEBUI_NAME}
	</title>
</svelte:head>

<div
	class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out max-w-full"
>
	<div class="flex-1 min-h-0 max-h-full overflow-y-auto flex flex-col">
		<FeatureRetired code="D23" name={$i18n.t('Notes')} />
	</div>
</div>
