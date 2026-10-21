<script lang="ts">
	// /arch/banyan:banyan 专属编排子页——方案流·波次·正本·闸门,全图示。
	// 事实全部出自引擎源码:orchestration/{scheduler,attack}.py · human/{inbox,api,chat_store}.py · runners/agent_tools.py。
	import { onMount } from 'svelte';

	onMount(() => {
		// 与 /arch/pi 同款:向父页上报内容高度(被 iframe 嵌入时用)
		const post = () => {
			if (window.parent !== window) {
				const inner = document.querySelector('.max-w-full');
				const height = inner
					? Math.ceil(inner.getBoundingClientRect().height) + 2
					: document.documentElement.scrollHeight;
				window.parent.postMessage(
					{ type: 'banyan-arch-banyan-height', height },
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
	<title>banyan 编排架构</title>
</svelte:head>

<div class="h-screen overflow-y-auto">
	<div class="max-w-full mx-auto w-full px-4 py-6">
		<div class="flex items-baseline justify-between mb-4">
			<h1 class="text-lg font-semibold text-gray-900 dark:text-white">
				banyan 编排与数据:方案流 · 波次 · 正本 · 闸门
			</h1>
			<span class="text-[11px] text-gray-400 dark:text-gray-500">
				引擎 :8000 · Python · 事实出处 orchestration/ + human/ 源码
			</span>
		</div>

		<!-- ═══ 图一:方案流状态机 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图一 · 方案流状态机——人只出现在「批准方案」「处置信箱」两个触点
			</div>
			<svg viewBox="0 0 1080 400" class="w-full h-auto" role="img" aria-label="方案流状态机">
				<defs>
					<marker id="b-ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
						<path d="M0,0 L10,5 L0,10 z" class="fill-gray-400 dark:fill-gray-600" />
					</marker>
				</defs>
				<!-- 主路径 第一行 -->
				<g font-size="10.5" text-anchor="middle">
					<rect x="14" y="30" width="128" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="78" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">人 / 秘书</text>
					<text x="78" y="72" class="fill-gray-500 dark:fill-gray-400">理诉求 · 出方案卡</text>

					<rect x="172" y="30" width="150" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="247" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">级联准入</text>
					<text x="247" y="72" class="fill-gray-500 dark:fill-gray-400">规则→单席→镜头→人</text>

					<rect x="352" y="30" width="104" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="404" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">Ticket</text>
					<text x="404" y="72" class="fill-gray-500 dark:fill-gray-400">立案</text>

					<rect x="486" y="30" width="140" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="556" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">探索(探索者)</text>
					<text x="556" y="72" class="fill-gray-500 dark:fill-gray-400">方案卡 + 沙盘推演</text>

					<rect x="656" y="30" width="128" height="58" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="720" y="54" font-weight="600" class="fill-gray-900 dark:fill-gray-100">人批准(触点①)</text>
					<text x="720" y="72" class="fill-gray-500 dark:fill-gray-400">run_plan(attack_gate)</text>

					<rect x="814" y="30" width="150" height="58" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="889" y="54" font-weight="600" class="fill-gray-900 dark:fill-gray-100">攻击门(开工前)</text>
					<text x="889" y="72" class="fill-gray-500 dark:fill-gray-400">3×审查者三角度</text>
				</g>
				<line x1="142" y1="59" x2="170" y2="59" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="322" y1="59" x2="350" y2="59" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="456" y1="59" x2="484" y2="59" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="626" y1="59" x2="654" y2="59" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="784" y1="59" x2="812" y2="59" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />

				<!-- 拦截分支:攻击门 → 豁免重入 -->
				<line x1="889" y1="88" x2="889" y2="122" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<text x="897" y="110" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">blocked / unreviewed → 方案不开工</text>
				<rect x="744" y="124" width="220" height="40" rx="8" class="fill-transparent stroke-gray-300 dark:stroke-gray-700" stroke-dasharray="4 3" />
				<text x="854" y="148" text-anchor="middle" font-size="10" class="fill-gray-500 dark:fill-gray-400">拦截 → 信箱卡 → 人豁免或驳回(重入)</text>

				<!-- 通过 → 波次执行(第二行,右到左) -->
				<line x1="889" y1="164" x2="889" y2="196" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<text x="897" y="184" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">通过 → 开工</text>
				<g font-size="10.5" text-anchor="middle">
					<rect x="790" y="198" width="174" height="58" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="877" y="222" font-weight="600" class="fill-gray-900 dark:fill-gray-100">波次执行(执行者)</text>
					<text x="877" y="240" class="fill-gray-500 dark:fill-gray-400">波间顺序 · 波内并发(帽 4)</text>

					<rect x="560" y="198" width="170" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="645" y="222" font-weight="600" class="fill-gray-800 dark:fill-gray-100">登记簿断言(红/绿)</text>
					<text x="645" y="240" class="fill-gray-500 dark:fill-gray-400">orch_regs 两轨 · 回归零红</text>

					<rect x="330" y="198" width="170" height="58" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="415" y="222" font-weight="600" class="fill-gray-900 dark:fill-gray-100">完成门(收口)</text>
					<text x="415" y="240" class="fill-gray-500 dark:fill-gray-400">四条件,不过 = blocked+信箱</text>

					<rect x="96" y="198" width="174" height="58" rx="8" class="fill-green-50 dark:fill-gray-900 stroke-green-400/50 dark:stroke-gray-700" />
					<text x="183" y="222" font-weight="600" class="fill-gray-900 dark:fill-gray-100">finished(触点②)</text>
					<text x="183" y="240" class="fill-gray-500 dark:fill-gray-400">信箱完成卡 + K2 知识结算</text>
				</g>
				<line x1="790" y1="227" x2="732" y2="227" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="560" y1="227" x2="502" y2="227" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="330" y1="227" x2="272" y2="227" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />

				<!-- 失败/模糊 分支 -->
				<rect x="330" y="300" width="470" height="58" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
				<g font-size="10.5" text-anchor="middle">
					<text x="565" y="324" font-weight="600" class="fill-gray-800 dark:fill-gray-100">失败 / 模糊 → 任务管理器裁决(glm-5.3)→ 信箱卡 → 人处置 → 恢复</text>
					<text x="565" y="342" class="fill-gray-500 dark:fill-gray-400">机械规则先行(重试/依赖/降档是代码关节),LLM 只做裁量,宁可 note 不可乱 escalate</text>
				</g>
				<line x1="645" y1="256" x2="645" y2="298" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<text x="652" y="282" font-size="9.5" class="fill-gray-400 dark:fill-gray-500">失败 / 模糊</text>
				<text x="14" y="390" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">源码锚点:攻击门 orchestration/attack.py:80-108 · run_plan 装配 human/api.py:998/1194 · 完成门 scheduler._completion_gate:381 · 回滚预案落信箱 scheduler:435-444</text>
			</svg>
		</div>

		<!-- ═══ 图二:波次执行引擎 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-2">
				图二 · 波次执行引擎——谁在跑、失败怎么办(没有 LLM 级重试)
			</div>
			<svg viewBox="0 0 1080 300" class="w-full h-auto" role="img" aria-label="波次执行引擎">
				<g font-size="10.5" text-anchor="middle">
					<rect x="14" y="30" width="200" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="114" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">run_plan(方案)</text>
					<text x="114" y="72" class="fill-gray-500 dark:fill-gray-400">scheduler.py:209 · 逐波循环</text>
					<text x="114" y="88" class="fill-gray-500 dark:fill-gray-400">波间严格顺序</text>

					<rect x="252" y="30" width="220" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="362" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">波内 asyncio.TaskGroup</text>
					<text x="362" y="72" class="fill-gray-500 dark:fill-gray-400">每任务一协程(:339-343)</text>
					<text x="362" y="88" class="fill-gray-500 dark:fill-gray-400">_Gate 信号量并发帽 = 4(:143)</text>

					<rect x="510" y="30" width="230" height="66" rx="8" class="fill-amber-50/60 dark:fill-gray-900 stroke-amber-400/70 dark:stroke-gray-600" stroke-width="1.5" />
					<text x="625" y="54" font-weight="600" class="fill-gray-900 dark:fill-gray-100">HttpWorker.run(每任务)</text>
					<text x="625" y="72" class="fill-gray-500 dark:fill-gray-400">engine.py:280 唯一实例 · :544 调用</text>
					<text x="625" y="88" class="fill-gray-500 dark:fill-gray-400">POST /run wait=true → pi 内核</text>

					<rect x="778" y="30" width="180" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="868" y="54" font-weight="600" class="fill-gray-800 dark:fill-gray-100">RunResult 回收</text>
					<text x="868" y="72" class="fill-gray-500 dark:fill-gray-400">交付物落工作区</text>
					<text x="868" y="88" class="fill-gray-500 dark:fill-gray-400">pi_event 镜像 K1</text>
				</g>
				<line x1="214" y1="63" x2="250" y2="63" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="472" y1="63" x2="508" y2="63" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="740" y1="63" x2="776" y2="63" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />

				<!-- 失败语义 -->
				<g font-size="10.5" text-anchor="middle">
					<rect x="14" y="150" width="330" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="179" y="174" font-weight="600" class="fill-gray-800 dark:fill-gray-100">失败 / 传染 → _propagate_skips(:682)</text>
					<text x="179" y="192" class="fill-gray-500 dark:fill-gray-400">_fail / _skip(:718/721),下游任务跳过</text>
					<text x="179" y="208" class="fill-gray-500 dark:fill-gray-400">没有 LLM 级自动重试</text>

					<rect x="374" y="150" width="330" height="66" rx="8" class="fill-blue-50 dark:fill-gray-900 stroke-blue-300 dark:stroke-gray-700" stroke-width="1.5" />
					<text x="539" y="174" font-weight="600" class="fill-gray-900 dark:fill-gray-100">唯一重跑 = 运行时依赖单回路(:450-467)</text>
					<text x="539" y="192" class="fill-gray-500 dark:fill-gray-400">发现新依赖 → 回炉补单</text>
					<text x="539" y="208" class="fill-gray-500 dark:fill-gray-400">budget.charge_rerun 计费,可预算熔断</text>

					<rect x="734" y="150" width="330" height="66" rx="8" class="fill-gray-50 dark:fill-gray-900 stroke-gray-300 dark:stroke-gray-700" />
					<text x="899" y="174" font-weight="600" class="fill-gray-800 dark:fill-gray-100">失败诚实传播(RFF P0)</text>
					<text x="899" y="192" class="fill-gray-500 dark:fill-gray-400">/run 非 2xx、缺 runId、断档</text>
					<text x="899" y="208" class="fill-gray-500 dark:fill-gray-400">一律落 pi_mirror_gap,绝不静默</text>
				</g>
				<line x1="625" y1="96" x2="625" y2="120" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" />
				<line x1="180" y1="120" x2="898" y2="120" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" />
				<line x1="180" y1="120" x2="180" y2="148" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="539" y1="120" x2="539" y2="148" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<line x1="898" y1="120" x2="898" y2="148" class="stroke-gray-400 dark:stroke-gray-600" stroke-width="1.5" marker-end="url(#b-ar)" />
				<text x="14" y="256" font-size="10.5" class="fill-gray-400 dark:fill-gray-500">模糊决策(执行中发现)→ 波内 spawn_agent 拉交叉分析(审查者/任务管理器),见 /arch/pi 图四</text>
			</svg>
		</div>

		<!-- ═══ 图三:三种黑板与正本 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3 mb-6">
			<div class="text-sm font-medium text-black dark:text-white mb-3">
				图三 · 三种黑板 + 正本纪律——Agent 之间永不直接对话,LLM 间协作由调度代码搬运数据
			</div>
			<div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
				<div class="rounded-lg border border-blue-200/70 dark:border-gray-800 bg-blue-50/50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">① K1 事件账(唯一事实正本)</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">events/ jsonl · append + fsync · 永久可回放。pi_event / inbox.opened / file.stored / task_surface_turn 全是它的行。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">② 工作区文件(交付物)</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">BANYAN_HOME/workspace,jail 根;执行者写、审查者读;附件 .banyan-uploads 随工作区。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">③ 信箱 / 审卡(人的触点)</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">InboxStore.land 先落 K1 inbox.opened 再投卡;mailbox_send(任务管理器);notice 7 天过期;/inbox 四视图+徽标。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">断言登记簿 orch_regs</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">红/绿两轨:修复类开工前红测必须红(防 no-op 自证),交付时红绿双绿;完成门第①条件。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">知识仓(git, K2-K5)</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">cards/records/agents/prompts 正本,版本化;技能/提示词是单向投影缓存,运行时由引擎全文下发进提示词。</div>
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-3">
					<div class="font-semibold text-gray-800 dark:text-gray-200">复核隔离(审查者输入)</div>
					<div class="text-gray-500 dark:text-gray-400 mt-1">证据白名单:diff + 断言留痕;执行者自述被剥离——取证靠真跑命令,不靠读自述。</div>
				</div>
			</div>
		</div>

		<!-- ═══ 纪律闸门一览 ═══ -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-3">
			<div class="text-sm font-medium text-black dark:text-white mb-2">内置机械闸门(代码关节,不是提示词约定)</div>
			<div class="flex flex-wrap gap-2 text-[11px]">
				{#each gates as g}
					<div class="rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 px-3 py-2">
						<span class="font-semibold text-gray-800 dark:text-gray-200">{g.n}</span>
						<span class="text-gray-500 dark:text-gray-400"> — {g.d}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>

<script context="module">
	const gates = [
		{ n: '红绿强制', d: '修复类开工前红测必须红,交付红绿双绿;未红 = skipped(no-op 防自证)' },
		{ n: '攻击门', d: '开工前 3 角度审查;拦截→信箱→豁免重入;全 persona 无效回包 = unreviewed 同拦' },
		{ n: '完成门四条件', d: '断言全过 + 回归零红 + 交付物实存 + 回滚预案落信箱;不过 = blocked + 信箱卡' },
		{ n: '升级判定', d: '机械规则先行,LLM 只做裁量,宁可 note 不可乱 escalate' },
		{ n: '失败诚实传播', d: '漏镜像 = 设计自定 P0;失败路径必落 pi_mirror_gap' }
	];
</script>
