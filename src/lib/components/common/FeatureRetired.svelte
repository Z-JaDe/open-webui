<script lang="ts">
	// banyan D23/D24（完整方案 §12.5）：退役面统一占位。
	// 约定：路由与组件文件保留（恢复=摘除占位换回原组件）；数据与配置正本归引擎，
	// WebUI 不再提供该维护面。后端开关跟进项见 RF-14 报告（config.py 归 RF-10）。
	export let code: string = ''; // 方案裁决编号（如 'D23' / 'D24'）
	export let name: string = ''; // 退役面名称（如 'Notes' / 'Prompts'）
</script>

<div class="flex flex-1 min-h-0 w-full items-center justify-center p-6">
	<div class="max-w-md text-center">
		<div class="text-base font-medium text-gray-900 dark:text-white">
			{name ? `${name} · ` : ''}此页面已退役
		</div>
		<div class="mt-2 text-sm text-gray-500 dark:text-gray-400">
			该功能已按 banyan 方案退役：数据与配置由引擎统一管理，WebUI 不再提供此维护面。
		</div>
		{#if code}
			<div class="mt-3 text-xs text-gray-400 dark:text-gray-600">banyan {code}</div>
		{/if}
	</div>
</div>
