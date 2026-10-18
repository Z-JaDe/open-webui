<script lang="ts">
	// /cal — banyan 日历（v3 W3，V-8 第一包：UTC 绝对时间戳，无 rrule）
	// 复用上游纯展示组件 CalendarView（calendar_id/color 之外的引擎没有的字段一律
	// null/空，动作按钮自然隐藏）；引擎 cal- 事件投影成 CalendarEventModel 形状：
	// start_at/end_at 为 epoch 纳秒（CalendarView 内部 /1e6 转毫秒），引擎给 UTC 秒。
	// 数据源：GET/POST/PATCH/DELETE /banyan/api/calendar/events（代理桥 → 引擎），
	// DELETE 为取消语义（引擎置 cancelled，不物理删）。
	// story 开关：?mock=1 → 内置样例数据（不请求引擎）。
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';

	import type i18nType from '$lib/i18n';
	import {
		getBanyanCalendar,
		createBanyanCalendarEvent,
		deleteBanyanCalendarEvent,
		type BanyanCalendarEvent
	} from '$lib/apis/banyan';
	import type { CalendarEventModel, CalendarModel } from '$lib/apis/calendar';
	import CalendarView from '$lib/components/calendar/CalendarView.svelte';
	import BanyanPageNav from '$lib/components/banyan/BanyanPageNav.svelte';
	import { subscribeBanyanEvents, createBanyanRefresher } from '$lib/stores/banyanEvents';

	const i18n = getContext<Writable<i18nType>>('i18n');

	// 投影目标伪日历（引擎事件统一挂在其下；color 走 CalendarView 默认蓝）
	const BANYAN_CAL_ID = 'banyan';

	let loaded = false;
	let error: string | null = null;
	let events: CalendarEventModel[] = [];
	let currentDate = new Date();
	let view: 'month' | 'week' | 'day' = 'month';

	// 最小表单（title/start/end）；null=关闭。mode: create 新建 / view 查看+删除
	let modalMode: 'create' | 'view' | null = null;
	let formTitle = '';
	let formStart = '';
	let formEnd = '';
	let selectedEvent: BanyanCalendarEvent | null = null;
	let acting = false;

	const banyanLayout: any = getContext('banyanLayout') ?? {};
	banyanLayout.setHeader?.({ itemName: '日历' });

	const isMock = () => new URLSearchParams(window.location.search).has('mock');

	// 引擎事件单一伪日历（CalendarView 只用 id/color 做过滤与着色）
	const banyanCalendar: CalendarModel = {
		id: BANYAN_CAL_ID,
		user_id: '',
		name: 'banyan',
		color: null,
		is_default: true,
		is_system: true,
		data: null,
		meta: null,
		access_grants: [],
		created_at: 0,
		updated_at: 0
	};
	const calendars: CalendarModel[] = [banyanCalendar];
	const visibleCalendarIds = new Set<string>([BANYAN_CAL_ID]);

	// ── 时区换算：引擎 UTC epoch 秒 ↔ 前端本地（datetime-local）──
	const toLocalInput = (tsSec: number) => {
		const d = new Date(tsSec * 1000);
		const pad = (n: number) => String(n).padStart(2, '0');
		return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
	};
	const fromLocalInput = (v: string) => Math.floor(new Date(v).getTime() / 1000);

	// ── 引擎投影 → CalendarEventModel（RSVP/循环字段一律 null，动作按钮自然隐藏）──
	const projectEvent = (e: BanyanCalendarEvent): CalendarEventModel => ({
		id: e.id,
		calendar_id: BANYAN_CAL_ID,
		user_id: '',
		title: e.title,
		description: e.description ?? null,
		start_at: e.start_ts * 1_000_000_000,
		end_at: (e.end_ts ?? e.start_ts) * 1_000_000_000,
		all_day: e.all_day,
		rrule: null,
		color: null,
		location: null,
		data: null,
		meta: null,
		is_cancelled: e.status === 'cancelled',
		attendees: [],
		created_at: 0,
		updated_at: 0
	});

	// 当前月视图 6x7 网格覆盖范围（与 CalendarView 网格一致）→ epoch 秒
	const monthRange = () => {
		const d = new Date(currentDate);
		const start = new Date(d.getFullYear(), d.getMonth(), 1);
		start.setDate(start.getDate() - start.getDay());
		const end = new Date(start);
		end.setDate(end.getDate() + 42);
		return {
			from: Math.floor(start.getTime() / 1000),
			to: Math.floor(end.getTime() / 1000)
		};
	};

	const mockEvents = (): BanyanCalendarEvent[] => {
		const day = (offset: number, hour: number, minute = 0) => {
			const d = new Date();
			d.setDate(d.getDate() + offset);
			d.setHours(hour, minute, 0, 0);
			return Math.floor(d.getTime() / 1000);
		};
		return [
			{
				id: 'cal_mock0001',
				title: '引擎例检',
				description: 'sidecar 健康巡检',
				start_ts: day(0, 15),
				end_ts: day(0, 16),
				all_day: false,
				status: 'open',
				source: 'manual'
			},
			{
				id: 'cal_mock0002',
				title: '知识管线收口评审',
				description: '',
				start_ts: day(1, 10),
				end_ts: day(1, 11, 30),
				all_day: false,
				status: 'open',
				source: 'manual'
			},
			{
				id: 'cal_mock0003',
				title: '季度合并窗口',
				description: '上游合并冲刺',
				start_ts: day(3, 0),
				end_ts: day(3, 23, 59),
				all_day: true,
				status: 'open',
				source: 'manual'
			}
		];
	};

	const load = async () => {
		error = null;
		if (isMock()) {
			events = mockEvents().map(projectEvent);
			loaded = true;
			return;
		}
		try {
			const rows = await getBanyanCalendar(monthRange());
			events = rows.filter((e) => e.status !== 'cancelled').map(projectEvent);
		} catch (e) {
			error = `${e}`;
			events = [];
			toast.error(`日历加载失败: ${e}`);
		}
		loaded = true;
	};

	const refresh = () => load();

	const openCreate = (startTsSec: number) => {
		modalMode = 'create';
		formTitle = '';
		formStart = toLocalInput(startTsSec);
		formEnd = toLocalInput(startTsSec + 3600);
	};

	// CalendarView 点击日期格（start_at 为 epoch 纳秒，本地 9:00）
	const handleCreateEvent = (e: CustomEvent<{ start_at: number }>) => {
		openCreate(Math.floor(e.detail.start_at / 1_000_000_000));
	};

	// 点击事件 chip → 查看 + 删除（取消语义）
	const handleEventClick = (e: CustomEvent<CalendarEventModel>) => {
		const row = events.find((ev) => ev.id === e.detail.id);
		selectedEvent = row
			? {
					id: row.id,
					title: row.title,
					description: row.description ?? undefined,
					start_ts: row.start_at / 1_000_000_000,
					end_ts: (row.end_at ?? row.start_at) / 1_000_000_000,
					all_day: row.all_day,
					status: row.is_cancelled ? 'cancelled' : 'open'
				}
			: null;
		modalMode = selectedEvent ? 'view' : null;
	};

	const submitCreate = async () => {
		if (!formTitle.trim()) {
			toast.error('标题不能为空');
			return;
		}
		let startTs = fromLocalInput(formStart);
		let endTs = fromLocalInput(formEnd);
		if (!startTs) {
			toast.error('开始时间无效');
			return;
		}
		if (!endTs || endTs <= startTs) endTs = startTs + 3600;
		acting = true;
		try {
			if (!isMock()) {
				await createBanyanCalendarEvent({ title: formTitle.trim(), start_ts: startTs, end_ts: endTs });
			}
			modalMode = null;
			toast.success('日程已创建');
			await refresh();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			acting = false;
		}
	};

	const deleteEvent = async () => {
		if (!selectedEvent) return;
		acting = true;
		try {
			if (!isMock()) {
				await deleteBanyanCalendarEvent(selectedEvent.id); // DELETE = 取消语义
			}
			modalMode = null;
			selectedEvent = null;
			toast.success('日程已取消');
			await refresh();
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			acting = false;
		}
	};

	const fmtRange = (startTs: number, endTs?: number) => {
		const fmt = (ts: number) => new Date(ts * 1000).toLocaleString();
		return endTs && endTs > startTs ? `${fmt(startTs)} — ${fmt(endTs)}` : fmt(startTs);
	};

	const MONTH_NAMES = [
		'1月',
		'2月',
		'3月',
		'4月',
		'5月',
		'6月',
		'7月',
		'8月',
		'9月',
		'10月',
		'11月',
		'12月'
	];
	$: headerText = `${currentDate.getFullYear()} 年 ${MONTH_NAMES[currentDate.getMonth()]}`;

	const navigateMonth = (delta: number) => {
		const d = new Date(currentDate);
		d.setDate(1);
		d.setMonth(d.getMonth() + delta);
		currentDate = d;
		view = 'month'; // 月视图固定（CalendarView"更多"链接会切日视图，这里兜底回月视图）
		refresh();
	};

	const goToToday = () => {
		currentDate = new Date();
		view = 'month';
		refresh();
	};

	onMount(load);

	// F8/D15:K1 事件驱动重取——calendar.* 帧(日程开启/增改/取消/提醒)到达即刷新;
	// 页面在后台只记待办、回前台补取(防后台风暴),3s 节流。
	onMount(() => {
		const refresher = createBanyanRefresher(load);
		const unsubscribe = subscribeBanyanEvents(['calendar.'], refresher.trigger);
		return () => {
			unsubscribe();
			refresher.dispose();
		};
	});
</script>

<svelte:head><title>日历 · banyan</title></svelte:head>

<BanyanPageNav />

<div class="px-8 lg:px-28 xl:px-40 pb-10 pt-3">
	{#if error}
		<div
			class="mb-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-xs text-red-600 dark:text-red-400"
		>
			经 /banyan/api 无法连通引擎——请先启动引擎，或追加 ?mock=1 用内置样例数据预览。
			<br />
			{error}
		</div>
	{/if}

	<!-- 月导航（月视图固定；引擎第一包无周/日语义） -->
	<div class="mb-2 flex items-center gap-1">
		<span class="min-w-fit px-1 text-sm font-medium select-none text-black dark:text-white">
			{headerText}
		</span>
		<button
			type="button"
			class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
			on:click={() => navigateMonth(-1)}
			aria-label="上个月"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke="currentColor"
				class="size-3.5 text-gray-400"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
			</svg>
		</button>
		<button
			type="button"
			class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
			on:click={() => navigateMonth(1)}
			aria-label="下个月"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
				stroke-width="1.5"
				stroke="currentColor"
				class="size-3.5 text-gray-400"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
			</svg>
		</button>
		<button
			type="button"
			class="text-xs px-2 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition text-gray-500 dark:text-gray-400"
			on:click={goToToday}
		>
			今天
		</button>
		<button
			type="button"
			class="ml-auto rounded-lg bg-gray-50 px-2.5 py-1 text-xs text-gray-900 transition ring-1 ring-gray-200 hover:bg-gray-100 dark:bg-gray-850 dark:text-gray-100 dark:ring-gray-800 dark:hover:bg-gray-800"
			on:click={() => openCreate(Math.floor(Date.now() / 1000))}
		>
			新建
		</button>
	</div>

	<div class="h-[calc(100vh-18rem)] min-h-[30rem]">
		<CalendarView
			{events}
			{calendars}
			{visibleCalendarIds}
			bind:view
			bind:currentDate
			onNavigate={refresh}
			on:createEvent={handleCreateEvent}
			on:eventClick={handleEventClick}
		/>
	</div>
</div>

{#if modalMode}
	<!-- 最小表单/查看弹层（固定居中遮罩） -->
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
		<div class="w-80 rounded-xl bg-white dark:bg-gray-900 p-4 shadow-xl space-y-3">
			{#if modalMode === 'create'}
				<div class="text-sm font-medium text-black dark:text-white">新日程</div>
				<input
					class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 outline-none"
					placeholder="标题"
					bind:value={formTitle}
				/>
				<label class="block text-[11px] text-gray-500 dark:text-gray-400">
					开始
					<input type="datetime-local" class="mt-1 w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 outline-none" bind:value={formStart} />
				</label>
				<label class="block text-[11px] text-gray-500 dark:text-gray-400">
					结束
					<input type="datetime-local" class="mt-1 w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 outline-none" bind:value={formEnd} />
				</label>
				<div class="flex items-center justify-end gap-2 pt-1">
					<button
						type="button"
						class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
						on:click={() => (modalMode = null)}
					>
						取消
					</button>
					<button
						type="button"
						class="px-3 py-1.5 text-xs font-medium rounded-lg bg-black text-white hover:bg-gray-800 dark:bg-white dark:text-black dark:hover:bg-gray-200 disabled:opacity-50 transition"
						disabled={acting}
						on:click={submitCreate}
					>
						新建
					</button>
				</div>
			{:else if selectedEvent}
				<div class="text-sm font-medium text-black dark:text-white">{selectedEvent.title}</div>
				<div class="text-xs text-gray-500 dark:text-gray-400">
					{fmtRange(selectedEvent.start_ts, selectedEvent.end_ts)}
				</div>
				{#if selectedEvent.description}
					<div class="text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
						{selectedEvent.description}
					</div>
				{/if}
				<div class="flex items-center justify-end gap-2 pt-1">
					<button
						type="button"
						class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
						on:click={() => (modalMode = null)}
					>
						关闭
					</button>
					<button
						type="button"
						class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition"
						disabled={acting}
						on:click={deleteEvent}
					>
						删除
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
