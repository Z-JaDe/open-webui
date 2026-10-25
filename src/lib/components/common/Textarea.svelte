<script lang="ts">
	import { onMount, tick } from 'svelte';

	export let value = '';
	export let placeholder = '';
	export let rows = 1;
	export let minSize: number | null = null;
	export let maxSize: number | null = null;
	export let required = false;
	export let readonly = false;
	export let className =
		'w-full rounded-lg px-3.5 py-2 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden  h-full';
	export let ariaLabel: string | null = null;

	export let onInput: (event: Event) => void = () => {};
	export let onBlur: (event: FocusEvent) => void = () => {};

	let textareaElement: HTMLTextAreaElement | null = null;

	// Adjust height on mount and after setting the element.
	// RF2-D 类级修复(同 goals/arch 页竞态形态):onMount(async) 返回 Promise,
	// Svelte 不注册其 return 的 cleanup——destroy 发生在 await tick()/rAF
	// 之后、textareaElement 绑定之前时,轮询 interval 每 100ms 永不回收
	// (Svelte 5 销毁把 bind:this 置回 null,interval 自清条件恒假)。
	// dead 标志封 destroy-before-rAF 窗口;interval 句柄提级到 onMount
	// 作用域,cleanup clearInterval 封「interval 已建后销毁」窗口(RF-3b
	// 补全:第一轮 cleanup 只置 dead 不清 interval,句柄困在 rAF 闭包)。
	onMount(() => {
		let dead = false;
		let poll: ReturnType<typeof setInterval> | undefined;
		void (async () => {
			await tick();
			if (dead) return;
			resize();

			requestAnimationFrame(() => {
				if (dead) return;
				// setInterveal to cehck until textareaElement is set
				poll = setInterval(() => {
					if (textareaElement) {
						clearInterval(poll);
						resize();
					}
				}, 100);
			});
		})();
		return () => {
			dead = true;
			clearInterval(poll);
		};
	});

	const resize = () => {
		if (textareaElement) {
			// Find all ancestors that currently have an active scroll offset.
			// This is extremely fast because reading `scrollTop` on a clean layout doesn't trigger reflow,
			// and it makes the fix 100% robust without relying on hardcoded CSS classes.
			const activeScrollParents: { el: HTMLElement; top: number }[] = [];
			let p = textareaElement.parentNode;
			while (p && p !== document.body) {
				if (p instanceof HTMLElement && p.scrollTop > 0) {
					activeScrollParents.push({ el: p, top: p.scrollTop });
				}
				p = p.parentNode;
			}
			const windowScrollY = window.scrollY;

			textareaElement.style.height = '';

			let height = textareaElement.scrollHeight;
			if (maxSize && height > maxSize) {
				height = maxSize;
			}
			if (minSize && height < minSize) {
				height = minSize;
			}

			textareaElement.style.height = `${height}px`;

			// Only restore scroll for elements that were actually scrolled.
			// This prevents layout thrashing that happens if we blindly set `.scrollTop` on every parent.
			activeScrollParents.forEach((p) => {
				if (p.el.scrollTop !== p.top) p.el.scrollTop = p.top;
			});
			if (window.scrollY !== windowScrollY) {
				window.scrollTo(window.scrollX, windowScrollY);
			}
		}
	};
</script>

<textarea
	bind:this={textareaElement}
	bind:value
	{placeholder}
	aria-label={ariaLabel || placeholder}
	class={className}
	style="field-sizing: content;"
	{rows}
	{required}
	{readonly}
	on:input={(e) => {
		resize();

		onInput(e);
	}}
	on:focus={() => {
		resize();
	}}
	on:blur={onBlur}
></textarea>
