<script lang="ts">
	// /arch/pi:pi 架构图示子页——被 /arch 以 iframe 嵌入,也可单独打开看大图。
	// 全图化,零长文;数据全部来自 pi-sidecar 源码与引擎 orchestration/worker.py(RF-29W/32/33)。
	import { onMount } from 'svelte';

	onMount(() => {
		// 全局样式把 html 锁了 overflow-y:hidden,内容超出会被裁掉:
		// ① 自带 h-screen 滚动容器兜底;② 向父页(/arch iframe)上报内容高度做自适应。
		const post = () => {
			if (window.parent !== window) {
				// 上报内容层真实高度——html.scrollHeight 被内滚容器钳住,会与 iframe 高度互锁
				const inner = document.querySelector('.max-w-5xl');
				const height = inner
					? Math.ceil(inner.getBoundingClientRect().height) + 2
					: document.documentElement.scrollHeight;
				window.parent.postMessage(
					{ type: 'banyan-arch-pi-height', height },
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
</script>

<svelte:head>
	<title>pi 架构图</title>
</svelte:head>

<div class="h-screen overflow-y-auto">
	<div class="max-w-full mx-auto w-full px-4 py-6">
	<div class="flex items-baseline justify-between mb-4">
		<h1 class="text-lg font-semibold text-gray-900 dark:text-white">
			pi 执行内核:架构与对接
		</h1>
		<span class="text-[11px] text-gray-400 dark:text-gray-500">
			@earendil-works/pi-coding-agent · pin 1.2.0
		</span>
	</div>

	<!-- ═══ 图一:pi 内核分层(pi 本身提供什么)═══ -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
		<div class="text-sm font-medium text-black dark:text-white mb-2">
			图一 · pi 内核分层——banyan 不写 ReAct,这 8 项全是 pi 原生能力
		</div>
		<svg viewBox="0 0 1080 590" class="w-full h-auto" role="img" aria-label="pi 内核分层图">
			<defs>
				<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
					<path d="M0,0 L10,5 L0,10 z" class="fill-gray-400 dark:fill-gray-600" />
				</marker>
			</defs>

			<!-- 载荷入口 -->
			<rect x="340" y="14" width="400" height="64" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
			<text x="540" y="38" text-anchor="middle" font-size="12.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">/run 载荷 = 执行规格</text>
			<text x="540" y="58" text-anchor="middle" font-size="11" class="fill-gray-500 dark:fill-gray-400">system_prompt · task_text · model · tools · workspace</text>
			<line x1="540" y1="78" x2="540" y2="120" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="550" y="104" font-size="10" class="fill-gray-400 dark:fill-gray-500">逐字生效,缺项即 400</text>

			<!-- 工具面(左) -->
			<rect x="24" y="122" width="234" height="190" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="141" y="146" text-anchor="middle" font-size="12.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">工具面</text>
			<g font-size="11" class="fill-gray-600 dark:fill-gray-400">
				<text x="40" y="172">内建:read / write / edit</text>
				<text x="40" y="192">bash / grep / find / ls</text>
				<text x="40" y="212">customTools 同名覆写</text>
				<text x="40" y="232">jail 扩展:路径越界即拦</text>
				<text x="40" y="252">bash:cwd 钉工作区 + env</text>
			</g>
			<line x1="258" y1="217" x2="288" y2="217" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="273" y="209" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">tools</text>

			<!-- 模型面(右) -->
			<rect x="822" y="122" width="234" height="190" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="939" y="146" text-anchor="middle" font-size="12.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">模型面 · ModelRuntime</text>
			<g font-size="11" class="fill-gray-600 dark:fill-gray-400">
				<text x="838" y="172">models.json + auth.json</text>
				<text x="838" y="192">provider/modelId 直解析</text>
				<text x="838" y="212">OpenAI 兼容流式调 GLM</text>
				<text x="838" y="232">token / cost 统计</text>
				<text x="838" y="252">无档位 / 角色映射</text>
			</g>
			<line x1="792" y1="217" x2="822" y2="217" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="807" y="209" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">model</text>

			<!-- AgentSession 中央 -->
			<rect x="290" y="122" width="500" height="190" rx="8" class="fill-amber-50/60 dark:fill-gray-950 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
			<text x="540" y="146" text-anchor="middle" font-size="13" font-weight="600" class="fill-gray-900 dark:fill-gray-100">AgentSession — ReAct 循环</text>
			<rect x="312" y="164" width="118" height="44" rx="6" class="fill-white dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="371" y="182" text-anchor="middle" font-size="10.5" class="fill-gray-700 dark:fill-gray-300">prompt(task_text)</text>
			<text x="371" y="198" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">注入 steer / followUp</text>
			<rect x="478" y="164" width="80" height="44" rx="6" class="fill-white dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="518" y="191" text-anchor="middle" font-size="11.5" class="fill-gray-700 dark:fill-gray-300">LLM</text>
			<rect x="606" y="164" width="100" height="44" rx="6" class="fill-white dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="656" y="191" text-anchor="middle" font-size="11" class="fill-gray-700 dark:fill-gray-300">工具执行</text>
			<line x1="430" y1="178" x2="476" y2="178" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<line x1="558" y1="176" x2="604" y2="176" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<line x1="604" y1="196" x2="560" y2="196" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="540" y="232" text-anchor="middle" font-size="10" class="fill-gray-400 dark:fill-gray-500">循环直至 agent_settled(终态判定)· abort() 中断 · compact() 压缩</text>

			<!-- 会话树(左下) -->
			<line x1="440" y1="312" x2="440" y2="350" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="448" y="334" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">session jsonl</text>
			<rect x="24" y="352" width="494" height="106" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="271" y="376" text-anchor="middle" font-size="12.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">SessionManager — 会话树持久化</text>
			<g font-size="11" class="fill-gray-600 dark:fill-gray-400">
				<text x="40" y="400">每会话一个 JSONL 文件(sessions/ 目录)</text>
				<text x="40" y="420">全分支 DAG:branch · fork(抽新文件) · switch(同文件移叶)</text>
				<text x="40" y="440">旧分支永不删;fork/switch 后下一次 /run 自动在新叶继续</text>
			</g>

			<!-- 事件流(右下) -->
			<line x1="640" y1="312" x2="640" y2="350" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="648" y="334" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">subscribe()</text>
			<rect x="562" y="352" width="494" height="106" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="809" y="376" text-anchor="middle" font-size="12.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">AgentSessionEvent — 事件流</text>
			<g font-size="11" class="fill-gray-600 dark:fill-gray-400">
				<text x="578" y="400">subscribe() 全集:文本 / 思考 / 工具增量 · 每条带 usage</text>
				<text x="578" y="420">终态信号 = agent_settled(不是 agent_end)</text>
				<text x="578" y="440">环形缓冲 10 万行(纯内存,since 游标重放)</text>
			</g>

			<!-- 两个虚线小能力 -->
			<rect x="24" y="478" width="494" height="42" rx="8" class="fill-transparent stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
			<text x="271" y="504" text-anchor="middle" font-size="11" class="fill-gray-500 dark:fill-gray-400">core/compaction — 超长会话自动「摘要 + 尾窗」截断</text>
			<rect x="562" y="478" width="494" height="42" rx="8" class="fill-transparent stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
			<text x="809" y="504" text-anchor="middle" font-size="11" class="fill-gray-500 dark:fill-gray-400">资源发现(技能/模板/主题)——banyan 运行时全部关闭</text>

			<text x="540" y="556" text-anchor="middle" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">锁版:pi-coding-agent pin 1.2.0(含 pi-ai 1.2.0)· in-process SDK(不走 RPC 子进程)· node:http 零框架</text>
		</svg>
	</div>

	<!-- ═══ 图二:与 banyan 引擎的对接(谁调谁、数据怎么流)═══ -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
		<div class="text-sm font-medium text-black dark:text-white mb-2">
			图二 · 对接到 banyan 引擎——三列泳道:谁调谁、什么数据过线
		</div>
		<svg viewBox="0 0 1080 640" class="w-full h-auto" role="img" aria-label="banyan 与 pi 对接图">
			<!-- 泳道表头 -->
			<rect x="24" y="14" width="300" height="44" rx="8" class="fill-blue-100/70 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" />
			<text x="174" y="41" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">引擎 :8000 — Python(编排 · 正本)</text>
			<rect x="390" y="14" width="300" height="44" rx="8" class="fill-amber-100/70 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-700" />
			<text x="540" y="41" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">pi-sidecar :8100 — TS(pi 封装)</text>
			<rect x="756" y="14" width="300" height="44" rx="8" class="fill-green-100/70 dark:fill-gray-900 stroke-green-400/60 dark:stroke-gray-700" />
			<text x="906" y="41" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">GLM · BigModel coding 端点</text>

			<!-- ① 装配 → /run -->
			<rect x="24" y="78" width="300" height="76" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="174" y="100" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">装配来源(角色正本在引擎)</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-600 dark:fill-gray-400">
				<text x="174" y="118">agents/*.md 提示词全文 · tools 白名单</text>
				<text x="174" y="134">model_map:heavy→glm-5.3 · daily→flash</text>
				<text x="174" y="150">拿档位名盲发会被拒;未知回调工具即 400</text>
			</g>
			<rect x="390" y="78" width="300" height="60" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="540" y="100" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">POST /run — 载荷即规格</text>
			<text x="540" y="120" text-anchor="middle" font-size="10" class="fill-gray-500 dark:fill-gray-400">逐字生效 · 缺项即 400 · 同会话并发 409</text>
			<line x1="324" y1="108" x2="388" y2="108" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="356" y="100" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">①</text>

			<!-- 建会话 -->
			<rect x="390" y="162" width="300" height="70" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="540" y="184" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">createAgentSession</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="540" y="202">system_prompt 逐字 · 磁盘零追加</text>
				<text x="540" y="218">资源发现全关 · jail 就位 · bash 覆写</text>
			</g>
			<line x1="540" y1="138" x2="540" y2="160" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />

			<!-- ② ReAct -->
			<rect x="390" y="256" width="300" height="70" rx="8" class="fill-amber-50/60 dark:fill-gray-950 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
			<text x="540" y="278" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-900 dark:fill-gray-100">② ReAct 循环(pi 内核)</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="540" y="296">LLM ⇄ 工具 · 规格漂移 = 按 JSONL 重建</text>
				<text x="540" y="312">终态 = agent_settled</text>
			</g>
			<line x1="540" y1="232" x2="540" y2="254" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />

			<!-- ③ GLM -->
			<rect x="772" y="252" width="268" height="34" rx="6" class="fill-green-50 dark:fill-gray-900 stroke-green-400/50 dark:stroke-gray-700" />
			<text x="906" y="274" text-anchor="middle" font-size="10.5" class="fill-gray-700 dark:fill-gray-300">glm-5.3 — heavy 档(goal 高阶/verify)</text>
			<rect x="772" y="294" width="268" height="34" rx="6" class="fill-green-50 dark:fill-gray-900 stroke-green-400/50 dark:stroke-gray-700" />
			<text x="906" y="316" text-anchor="middle" font-size="10.5" class="fill-gray-700 dark:fill-gray-300">glm-5.3-flash — fast/daily 档(全部预设)</text>
			<line x1="690" y1="288" x2="770" y2="288" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="730" y="280" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">③ 流式</text>
			<rect x="756" y="360" width="300" height="60" rx="8" class="fill-transparent stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="906" y="382">$GLM_API_KEY 环境插值 · sidecar 不落盘凭据</text>
				<text x="906" y="400">用哪档由每次 /run 的 payload.model 决定</text>
			</g>

			<!-- ⑤ 工具回调 -->
			<rect x="24" y="256" width="300" height="70" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="174" y="278" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">agent-tools 回调端点</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="174" y="296">引擎 store 直读:信箱/任务/台账/知识</text>
				<text x="174" y="312">失败以 isError 呈现,不炸 run</text>
			</g>
			<line x1="390" y1="291" x2="326" y2="291" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="358" y="283" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑤ 回调</text>

			<!-- ④ 事件镜像 -->
			<rect x="390" y="372" width="300" height="64" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="540" y="394" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">events 事件出口</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="540" y="412">JSON 行 · seq 单调 · since 游标重放</text>
				<text x="540" y="428">环形缓冲 10 万行(纯内存)</text>
			</g>
			<rect x="24" y="364" width="300" height="80" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
			<text x="174" y="386" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-900 dark:fill-gray-100">K1 事件账 — 唯一正本</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-600 dark:fill-gray-400">
				<text x="174" y="404">逐行镜像 pi_event · 水位对账 eventsLastSeq</text>
				<text x="174" y="420">断档 → pi_mirror_gap(P0 可见)</text>
				<text x="174" y="436">失败路径也落,绝不静默</text>
			</g>
			<line x1="390" y1="404" x2="326" y2="404" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="358" y="396" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">④ 镜像</text>

			<!-- ⑥ 结果 / 控制面 -->
			<rect x="390" y="484" width="300" height="84" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="540" y="506" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">控制面(会话树)</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="540" y="524">tree · fork(抽新文件) · switch(移叶)</text>
				<text x="540" y="540">inject(steer/followUp) · abort</text>
				<text x="540" y="556">GET /runs/:run_id 轮询(wait=false)</text>
			</g>
			<rect x="24" y="484" width="300" height="84" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
			<text x="174" y="506" text-anchor="middle" font-size="11.5" font-weight="600" class="fill-gray-800 dark:fill-gray-100">⑥ RunResult 回收</text>
			<g font-size="10" text-anchor="middle" class="fill-gray-500 dark:fill-gray-400">
				<text x="174" y="524">text · usage · stopReason · eventsLastSeq</text>
				<text x="174" y="540">wait=true 阻塞到终态</text>
				<text x="174" y="556">wait=false 立返 run_id,轮询收取</text>
			</g>
			<line x1="390" y1="512" x2="326" y2="512" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="358" y="504" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑥</text>
			<line x1="326" y1="540" x2="388" y2="540" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#ar)" />
			<text x="357" y="532" text-anchor="middle" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">inject / abort</text>

			<text x="540" y="610" text-anchor="middle" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">正本纪律:K1 是唯一正本,Pi JSONL 只是对账副本 · jail 防文件工具越界,bash 硬隔离由容器化承担</text>
		</svg>
	</div>

	<!-- ═══ 图三:一次 /run 的生命周期 ═══ -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
		<div class="text-sm font-medium text-black dark:text-white mb-2">
			图三 · 一次 /run 的生命周期(对应图二编号)
		</div>
		<div class="flex flex-wrap items-stretch gap-1 text-[11px]">
			{#each steps as s, i}
				{#if i > 0}
					<div class="self-center px-1 text-gray-400 dark:text-gray-600">→</div>
				{/if}
				<div class="flex-1 min-w-[9rem] rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-2">
					<div class="font-semibold text-gray-800 dark:text-gray-200">{s.n} {s.t}</div>
					<div class="text-gray-500 dark:text-gray-400 mt-0.5">{s.d}</div>
				</div>
			{/each}
		</div>
			<div class="text-[10.5px] text-gray-400 dark:text-gray-500 mt-2">
				终态 = agent_settled · 载荷规格漂移 → 弃置 live agent 按新规格重建 · fork/switch 后下一轮自动在新叶继续
			</div>
		</div>

		<!-- ═══ 图四:调度 subagent 怎么对接 pi ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图四 · 调度 subagent 怎么对接 pi——引擎调度面 → sidecar 原语的完整映射
			</div>
			<svg viewBox="0 0 1080 560" class="w-full h-auto" role="img" aria-label="subagent 调度对接图">
				<defs>
					<marker id="p4-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
						<path d="M0,0 L10,5 L0,10 z" class="fill-gray-400 dark:fill-gray-600" />
					</marker>
				</defs>
				<!-- 左列:引擎调度面 -->
				<rect x="24" y="14" width="330" height="40" rx="8" class="fill-blue-100/70 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" />
				<text x="189" y="39" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">引擎调度面(谁在发起)</text>
				<g font-size="10" text-anchor="middle">
					<rect x="24" y="70" width="330" height="86" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="189" y="92" font-size="11" font-weight="600" class="fill-gray-900 dark:fill-gray-100">subagent 工具(pi-goal 原生 · 管理者/秘书直接调)</text>
					<text x="189" y="110" class="fill-gray-600 dark:fill-gray-400">秘书(goal 管理者)的 LLM 工具</text>
					<text x="189" y="126" class="fill-gray-600 dark:fill-gray-400">spawn&#123;name, role, message&#125; · role 经引擎 Roles 目录解析</text>
					<text x="189" y="142" class="fill-gray-600 dark:fill-gray-400">_pending 登记 run_id → 会话</text>

					<rect x="24" y="172" width="330" height="86" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="189" y="194" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">波次调度器(orchestration/scheduler.py)</text>
					<text x="189" y="212" class="fill-gray-600 dark:fill-gray-400">波次执行者工人:HttpWorker.run</text>
					<text x="189" y="228" class="fill-gray-600 dark:fill-gray-400">engine.py:280 唯一实例 · :544 调用</text>
					<text x="189" y="244" class="fill-gray-600 dark:fill-gray-400">波内 TaskGroup,并发帽 4</text>

					<rect x="24" y="274" width="330" height="86" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="189" y="296" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">值班秘书 DutyOnGoal(runners/duty_goal.py)</text>
					<text x="189" y="314" class="fill-gray-600 dark:fill-gray-400">对话面:每轮一发,wait=true</text>
					<text x="189" y="330" class="fill-gray-600 dark:fill-gray-400">LRU tier:conv · 历史拼进 task_text</text>
					<text x="189" y="346" class="fill-gray-600 dark:fill-gray-400">text_delta 回调 → ConvHub → WebUI</text>

					<rect x="24" y="376" width="330" height="70" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="189" y="398" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">探索者 / 审查者 AgentRunner</text>
					<text x="189" y="416" class="fill-gray-600 dark:fill-gray-400">交叉分析 / 攻击复核 / 回归验证</text>
					<text x="189" y="432" class="fill-gray-600 dark:fill-gray-400">同款 /run + pi_event 镜像</text>
				</g>

				<!-- 右列:sidecar 原语 -->
				<rect x="726" y="14" width="330" height="40" rx="8" class="fill-green-100/70 dark:fill-gray-900 stroke-green-400/60 dark:stroke-gray-700" />
				<text x="891" y="39" text-anchor="middle" font-size="12" font-weight="600" class="fill-gray-800 dark:fill-gray-100">sidecar 原语(pi 原生能力)</text>
				<g font-size="10" text-anchor="middle">
					<rect x="726" y="70" width="330" height="72" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="891" y="92" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">A · POST /run wait=false</text>
					<text x="891" y="110" class="fill-gray-600 dark:fill-gray-400">立即返回 run_id,后台继续跑</text>
					<text x="891" y="126" class="fill-gray-600 dark:fill-gray-400">RunService.launch · registry ≤ 1000</text>

					<rect x="726" y="158" width="330" height="56" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="891" y="180" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">B · GET /runs/:run_id</text>
					<text x="891" y="198" class="fill-gray-600 dark:fill-gray-400">&#123;status, result&#125; · 终态可取 RunResult</text>

					<rect x="726" y="230" width="330" height="72" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="891" y="252" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">C · POST /sessions/:id/inject</text>
					<text x="891" y="270" class="fill-gray-600 dark:fill-gray-400">mode: steer(打断当前转向)</text>
					<text x="891" y="286" class="fill-gray-600 dark:fill-gray-400">followUp(本轮结束接续)——pi 原生</text>

					<rect x="726" y="318" width="330" height="72" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="891" y="340" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">D · POST /run wait=true</text>
					<text x="891" y="358" class="fill-gray-600 dark:fill-gray-400">阻塞至 agent_settled</text>
					<text x="891" y="374" class="fill-gray-600 dark:fill-gray-400">RunResult&#123;text, usage, stopReason&#125;</text>

					<rect x="726" y="406" width="330" height="56" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="891" y="428" font-size="11" font-weight="600" class="fill-gray-800 dark:fill-gray-100">E · POST /sessions/:id/abort</text>
					<text x="891" y="446" class="fill-gray-600 dark:fill-gray-400">中止活跃 run(取消/兜底)</text>
				</g>

				<!-- 箭头 -->
				<line x1="354" y1="92" x2="724" y2="92" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="84" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">① spawn_agent → 异步发起</text>
				<line x1="354" y1="126" x2="724" y2="172" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="146" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">② send 同名续话(steer 缺省/followUp 排队)</text>
				<line x1="354" y1="140" x2="724" y2="252" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="216" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">③ stop / status 中止与查在手</text>
				<line x1="354" y1="150" x2="724" y2="330" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="284" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">④ 答案由 reporter 自动回流(零轮询 · durable)</text>
				<line x1="354" y1="205" x2="724" y2="352" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="356" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑤ 波次工人:每任务一发,阻塞</text>
				<line x1="354" y1="307" x2="724" y2="366" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="404" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑥ 秘书:每轮一发</text>
				<line x1="354" y1="404" x2="724" y2="380" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="446" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑦ 同款 /run + 事件镜像</text>
				<line x1="354" y1="430" x2="724" y2="440" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#p4-ar)" />
				<text x="540" y="480" text-anchor="middle" font-size="10" font-weight="600" class="fill-gray-500 dark:fill-gray-400">⑧ 取消链:webui /work/&#123;id&#125;/cancel → 引擎 → abort</text>

				<text x="540" y="520" text-anchor="middle" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">v3:老 spawn 四件套已拆除——subagent 是常驻 durable 会话(崩溃续跑),子代理工具面=沙箱四件+一层封顶;秘书=pi-goal durable 会话(/conv 面),记忆在会话内</text>
			</svg>
		</div>

		<!-- ═══ 触点总览:pi × banyan 全部接触面 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				触点总览 · banyan 里每一个和 pi 有关的部分(全部对上号)
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-left text-[11px]">
					<thead>
						<tr class="text-gray-400 dark:text-gray-500">
							<th class="py-1 pr-3 font-medium">sidecar 面</th>
							<th class="py-1 pr-3 font-medium">banyan 消费方(代码)</th>
							<th class="py-1 font-medium">语义</th>
						</tr>
					</thead>
					<tbody>
						{#each touchpoints as t}
							<tr class="border-t border-gray-100 dark:border-gray-850">
								<td class="py-1 pr-3 font-mono text-[10px] whitespace-nowrap">{t.a}</td>
								<td class="py-1 pr-3 text-gray-700 dark:text-gray-300">{t.b}</td>
								<td class="py-1 text-gray-500 dark:text-gray-400">{t.c}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="text-[10.5px] text-gray-400 dark:text-gray-500 mt-2">
				不经 pi 的路径:X-Banyan-Task 元数据单发(v1_api.py:180,ChatPort 直连,不建会话不写行)· BANYAN_SIDECAR_URL 未设时引擎本地 ConversationRunner 兜底。除此之外,一切 Agent 执行都在 pi 内核。
			</p>
		</div>
	</div>
</div>

<script context="module">
	const steps = [
		{ n: '①②', t: '装配 → 建会话', d: '执行者.md 全文 + model_map[档位] + 白名单;逐字生效 · jail · 资源发现全关' },
		{ n: '②③', t: 'ReAct 循环', d: 'LLM⇄工具;http_tools 回调引擎 store;流式调 GLM(档位随载荷)' },
		{ n: '④', t: '镜像 K1', d: 'events 逐行镜像 pi_event;水位对账,断档落 pi_mirror_gap' },
		{ n: '⑤⑥', t: '回收 / 转向', d: 'RunResult{text,usage};inject steer/followUp;abort;tree/fork/switch' }
	];

	const touchpoints = [
		{ a: 'POST /run wait=true', b: '波次调度器 HttpWorker(scheduler:544 · engine.py:280)', c: '波次执行者工人,阻塞至 agent_settled' },
		{ a: '/conv(全表面 v3)', b: '引擎 DutyOnGoal(runners/duty_goal.py)+GoalClient', c: '秘书=durable 会话:记忆在会话内,事件环逐 delta 流式' },
		{ a: 'subagent 工具(pi-goal 原生)', b: '管理者/秘书直接调用(role=经引擎 Roles 目录)', c: '常驻子代理:spawn/send/stop/status,答案自动回流,崩溃安全——老 spawn 四件套已拆除' },
		{ a: 'POST /sessions/:id/abort', b: '失败兜底(worker.py:359)+ 取消链', c: '客户端炸裂补一发防空转;webui /work/{id}/cancel 接这里' },
		{ a: 'GET /sessions/:id/events', b: 'HttpWorker(worker.py)+ /conv/:key/events(duty_goal.py 轮询)', c: '逐行镜像 K1 pi_event;水位/epoch 对账落 pi_mirror_gap' },
		{ a: 'agent-tools 回调 POST', b: 'duty_tools + agent_tools 回调注册表', c: '信箱/任务/台账/知识/日历直读;失败=isError 不炸 run' },
		{ a: '/sessions/:id/tree · fork · switch', b: 'PiSessions 卡(webui 只读)+ 引擎树投影', c: '会话树 DAG 展示;fork/switch 引擎侧预留' },
		{ a: '/health', b: 'BanyanEngineStatus(webui 走 /banyan/api/health)', c: 'sidecar 健康红绿点' },
		{ a: 'models.json(启动物化)', b: '引擎 cfg.tiers → model_map(engine.py:268)', c: '档位→具体模型 id,由每次 /run 载荷直带' },
		{ a: 'Pi 会话 JSONL', b: 'K1 的对账副本', c: '可清理;事实正本永远在 K1 事件账' },
		{ a: 'pi-goal /goals·/cards(v3 新)', b: '引擎 GoalClient+触发器(runners/goal_client.py;BANYAN_GOAL_URL)', c: 'goal 内核(pi-durable):六相任务·常驻 subagent·人卡·预算·证据' }
	];
</script>
