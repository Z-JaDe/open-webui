<script lang="ts">
	// banyan D24（完整方案 §12.5）：workspace 五面退役。
	// 原逻辑按权限跳 models/knowledge/prompts/tools/skills 各面；
	// admin 落点 /workspace/models 路由已删（此前 404），五面均已退役——统一回对话首页。
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/', { replaceState: true });
	});
</script>
