<script lang="ts">
	// /arch/webui:WebUI × banyan 引擎对接子页——一条消息的完整旅行·/banyan/api 代理面·存储与身份。
	// 事实全部出自源码:webui 侧 middleware/openai.py/banyan_*.py + 引擎侧 human/v1_api.py、chat_store.py。
	import { onMount } from 'svelte';

	onMount(() => {
		const post = () => {
			if (window.parent !== window) {
				const inner = document.querySelector('.max-w-full');
				const height = inner
					? Math.ceil(inner.getBoundingClientRect().height) + 2
					: document.documentElement.scrollHeight;
				window.parent.postMessage(
					{ type: 'banyan-arch-webui-height', height },
					window.location.origin
				);
			}
		};
		post();
		const ro = new ResizeObserver(post);
		ro.observe(document.body);
		window.addEventListener('resize', post);
		return () => {
			ro.disconnect();
			window.removeEventListener('resize', post);
		};
	});

	const proxyTags = [
		'方案 plans / plan registry',
		'会话树 tree / switch',
		'登记簿 registry',
		'知识 cards',
		'审计 events',
		'场景包 packs',
		'信箱 inbox(裁决/已读/归档)',
		'日历四件',
		'状态 status',
		'子代理取消 /work/{id}/cancel'
	];
	const touchpoints = [
		{ n: 'BanyanEngineStatus', d: 'getBanyanStatus → {engine, sidecar, tiers, agents, counts};引擎侧 30s 缓存,页面不轮询' },
		{ n: 'PiSessions(只读)', d: '/banyan/api/pi/sessions + 展开拉 /pi/sessions/{id}/tree;状态徽标/树文本头 60 字' },
		{ n: 'PackListCard', d: '/api/packs:包名·描述·模板/技能/特化 Agent 计数' },
		{ n: '/arch 花名册', d: 'status.agents:统一目录 agents/*.md 的名称/职责/档位/工具/记忆/输出' }
	];
</script>

<svelte:head>
	<title>WebUI 对接架构</title>
</svelte:head>

<div class="h-screen overflow-y-auto">
	<div class="max-w-full mx-auto w-full px-4 py-6">
		<div class="flex items-baseline justify-between mb-4">
			<h1 class="text-lg font-semibold text-gray-900 dark:text-white">
				WebUI × 引擎对接:一条消息的旅行 · 代理面 · 存储与身份
			</h1>
			<span class="text-[11px] text-gray-400 dark:text-gray-500">
				fork :8080 · 引擎 :8000 · 事实出处 middleware/openai.py + human/v1_api.py
			</span>
		</div>

		<!-- ═══ 图一:一条消息的完整旅行 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图一 · 一条消息的完整旅行(发出去 → 流式回来的全链路)
			</div>
			<svg viewBox="0 0 1080 620" class="w-full h-auto" role="img" aria-label="消息旅行时序图">
				<defs>
					<marker id="w-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
						<path d="M0,0 L10,5 L0,10 z" class="fill-gray-400 dark:fill-gray-600" />
					</marker>
				</defs>
				<!-- 泳道头 -->
				<rect x="24" y="14" width="300" height="40" rx="8" class="fill-blue-100/70 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" />
				<text x="174" y="39" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">WebUI 前端(Chat.svelte)</text>
				<rect x="390" y="14" width="300" height="40" rx="8" class="fill-gray-100 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
				<text x="540" y="39" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">WebUI 后端(:8080)</text>
				<rect x="756" y="14" width="300" height="40" rx="8" class="fill-amber-100/70 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-700" />
				<text x="906" y="39" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">引擎(:8000)+ pi 内核</text>

				<!-- ① -->
				<line x1="174" y1="66" x2="174" y2="96" class="stroke-gray-300 dark:stroke-gray-700" />
				<line x1="324" y1="100" x2="388" y2="100" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<text x="356" y="92" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">①</text>
				<text x="356" y="116" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">POST /api/chat/completions</text>
				<!-- ② -->
				<rect x="390" y="126" width="300" height="52" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
				<text x="540" y="146" text-anchor="middle" font-size="10.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">② middleware:is_banyan_model 判定</text>
				<text x="540" y="164" text-anchor="middle" font-size="9.5" class="fill-gray-500 dark:fill-gray-400">model id banyan-* 前缀 / meta.kind=tier——档位即模型</text>
				<!-- ③ -->
				<line x1="690" y1="178" x2="754" y2="178" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<text x="722" y="170" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">③</text>
				<text x="722" y="194" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">引擎=OpenAI 连接直连,+X-Banyan-Conv</text>
				<!-- ④ 引擎内部 -->
				<rect x="756" y="206" width="300" height="104" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
				<g font-size="10" text-anchor="middle">
					<text x="906" y="228" font-weight="600" class="fill-gray-900 dark:fill-gray-100">④ _stream_turn:订阅先行 → chat 后台跑</text>
					<text x="906" y="246" class="fill-gray-600 dark:fill-gray-400">ConvHub.subscribe(conv) 先于一切(:297)</text>
					<text x="906" y="262" class="fill-gray-600 dark:fill-gray-400">值班秘书 DutyOnGoal(LRU tier:conv)</text>
					<text x="906" y="278" class="fill-gray-600 dark:fill-gray-400">每轮 POST /conv submit(记忆在 durable 会话)</text>
					<text x="906" y="294" class="fill-gray-600 dark:fill-gray-400">pi ReAct → GLM 流式</text>
				</g>
				<!-- ⑤ 引擎内部 -->
				<rect x="756" y="322" width="300" height="70" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
				<g font-size="10" text-anchor="middle">
					<text x="906" y="344" font-weight="600" class="fill-gray-800 dark:fill-gray-100">⑤ pi_event 镜像落行(agent.py:460-470)</text>
					<text x="906" y="362" class="fill-gray-500 dark:fill-gray-400">text_delta → on_chunk → chatstore 行</text>
					<text x="906" y="378" class="fill-gray-500 dark:fill-gray-400">append_row 落库后 ConvHub.publish(:92)</text>
				</g>
				<line x1="906" y1="310" x2="906" y2="320" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<!-- ⑥ -->
				<line x1="756" y1="404" x2="692" y2="404" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<text x="724" y="396" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑥</text>
				<rect x="390" y="412" width="300" height="70" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
				<g font-size="10" text-anchor="middle">
					<text x="540" y="434" font-weight="600" class="fill-gray-800 dark:fill-gray-100">⑦ banyan_passthrough_wrapper(:38-52)</text>
					<text x="540" y="452" class="fill-gray-500 dark:fill-gray-400">frame_lines(:270-295):delta→正文 chunk</text>
					<text x="540" y="468" class="fill-gray-500 dark:fill-gray-400">ticket/toolCall→私有行 · state.updated→wave_update</text>
				</g>
				<!-- ⑧ -->
				<line x1="390" y1="500" x2="176" y2="500" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<text x="283" y="492" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑧</text>
				<text x="283" y="516" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">SSE 流 → 钩点①写 message.banyanEvents → 流式渲染</text>
				<text x="14" y="572" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">帧格式:引擎在 OpenAI 流里混入 data:&#123;"banyan": …&#125; 私有行,webui 改写成前端事件通道——两侧行协议对齐,中间不改语义</text>
				<text x="14" y="594" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">同一条链路也承载方案流:wave_update 帧 → /arch·方案视图实时刷新;ticket 帧 → 信箱徽标</text>
			</svg>
		</div>

		<!-- ═══ 图二:/banyan/api 代理面 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图二 · /banyan/api 代理面——前端所有 banyan 数据都走这一条管道
			</div>
			<svg viewBox="0 0 1080 210" class="w-full h-auto" role="img" aria-label="代理面">
				<g font-size="10.5" text-anchor="middle">
					<rect x="24" y="24" width="250" height="66" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" />
					<text x="149" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">浏览器(登录态)</text>
					<text x="149" y="66" class="fill-gray-500 dark:fill-gray-400">src/lib/apis/banyan/</text>
					<text x="149" y="82" class="fill-gray-500 dark:fill-gray-400">统一 BASE = /banyan/api</text>

					<rect x="380" y="24" width="300" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="530" y="48" font-weight="600" class="fill-gray-800 dark:fill-gray-100">webui 后端 routers/banyan.py</text>
					<text x="530" y="66" class="fill-gray-500 dark:fill-gray-400">get_verified_user 登录门槛(:191)</text>
					<text x="530" y="82" class="fill-gray-500 dark:fill-gray-400">BANYAN_TOKEN 在场→替换 Bearer;未设→透传</text>

					<rect x="786" y="24" width="270" height="66" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="921" y="48" font-weight="600" class="fill-gray-900 dark:fill-gray-100">引擎 /api/*(:8000)</text>
					<text x="921" y="66" class="fill-gray-500 dark:fill-gray-400">catch-all 1:1 转发(:204)</text>
					<text x="921" y="82" class="fill-gray-500 dark:fill-gray-400">专有:/health · SSE /events→/api/events</text>
				</g>
				<line x1="274" y1="57" x2="378" y2="57" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<line x1="680" y1="57" x2="784" y2="57" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#w-ar)" />
				<text x="14" y="130" font-size="11" font-weight="600" class="fill-gray-700 dark:fill-gray-300">这条管道上跑的业务(前端 API 客户端函数清单):</text>
			</svg>
			<div class="flex flex-wrap gap-1.5 mt-2 text-[10.5px]">
				{#each proxyTags as t}
					<span class="rounded-md bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 px-2 py-1 text-gray-600 dark:text-gray-400">
						{t}
					</span>
				{/each}
			</div>
		</div>

		<!-- ═══ 图三:存储与身份 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-3">
				图三 · 存储与身份——零双写,各守各的正本
			</div>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
				<div class="rounded-lg border border-blue-200/70 dark:border-gray-800 bg-blue-50/50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">会话消息:零双写(D16')</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">chat id = 引擎 sess_*;消息唯一落点 = 引擎行(K1 可重建)——webui 不写 chat.db 消息,消息级操作对 banyan 会话一律 404(banyan_chat_adapter)。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">webui.db:仅身份与偏好</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">登录态/界面设置/缓存/uploads,零消息;账号体系在 WebUI 侧(管理员注册制),引擎不设账号面。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">托管:引擎直接服务前端</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">BANYAN_STATIC 托管 fork build(候选序:env &gt; PyInstaller 包内 &gt; BANYAN_WEBUI_DIR/build &gt; ../banyan-webui/build);同源免去 CORS,/banyan/api 同源直达。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">桌面壳(Tauri):只是壳</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">dock/托盘/⌘⇧B 唤起;拉起引擎与 sidecar;remote.json 可指远端引擎——业务逻辑零份拷贝。</div>
				</div>
			</div>
		</div>

		<!-- ═══ 组件触点 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
			<div class="text-sm font-medium text-black dark:text-white mb-2">fork 侧的 banyan 组件触点</div>
			<div class="space-y-1.5 text-[11px]">
				{#each touchpoints as t}
					<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 px-3 py-2">
						<span class="font-semibold text-gray-800 dark:text-gray-200">{t.n}</span>
						<span class="text-gray-500 dark:text-gray-400"> — {t.d}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>
