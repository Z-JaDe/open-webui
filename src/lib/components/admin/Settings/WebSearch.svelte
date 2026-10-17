<script lang="ts">
	// banyan F6（完整方案 §10 / 设置页方案 §2.3）：Web 搜索 tab 裁到单引擎。
	// 原组件（上游 31 引擎 + loader 全家）已在前轮退役删除；本组件按最小面重建：
	// 保留 开关 + 引擎下拉（searxng/bocha/tavily/ddgs 四选）+ key + 结果数 + 域名过滤；
	// 其余引擎配置块、loader 配置、bypass/trust 开关全部不渲染。
	import { getRAGConfig, updateRAGConfig } from '$lib/apis/retrieval';
	import Switch from '$lib/components/common/Switch.svelte';

	import { config } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';

	const i18n: any = getContext('i18n');

	export let saveHandler: Function;

	// banyan：单引擎裁剪后的四选（完整方案 backlog：bocha key 接入登记在案）
	let webSearchEngines = ['searxng', 'bocha', 'tavily', 'duckduckgo'];

	let webConfig: any = null;

	const inputClass =
		'w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	const submitHandler = async () => {
		// Convert domain filter string to array before sending
		if (
			typeof webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST === 'string' &&
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST
		) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.split(',')
				.map((domain: string) => domain.trim())
				.filter((domain: string) => domain.length > 0);
		} else if (!Array.isArray(webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = [];
		}

		await updateRAGConfig(localStorage.token, {
			web: { ...webConfig }
		});

		// Convert arrays back to strings for display
		if (Array.isArray(webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
			webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.join(',');
		}
	};

	onMount(async () => {
		const res = await getRAGConfig(localStorage.token);

		if (res) {
			webConfig = res.web;

			// Convert array back to comma-separated string for display
			if (Array.isArray(webConfig?.WEB_SEARCH_DOMAIN_FILTER_LIST)) {
				webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST.join(',');
			} else if (!webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST) {
				webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST = '';
			}
		}
	});
</script>

<form
	class="flex h-full flex-col justify-between text-sm"
	on:submit|preventDefault={async () => {
		await submitHandler();
		saveHandler();
	}}
>
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
		{$i18n.t('settings.admin.web.title')}
	</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if webConfig}
			<AdminSettingSection first title={$i18n.t('settings.admin.web.sections.search.title')}>
				<div class="mb-1 text-[0.6875rem] text-gray-400 dark:text-gray-600">
					<!-- banyan F6 单引擎裁剪说明：其余 27 家引擎配置已按完整方案 §10 摘除 -->
					banyan：仅保留 Searxng / Bocha / Tavily / DDGS 四个引擎，其余引擎配置已裁剪
					（only Searxng / Bocha / Tavily / DDGS are kept）。
				</div>

				<AdminSettingRow
					label={$i18n.t('settings.admin.web.webSearch.label')}
					description={$i18n.t('settings.admin.web.webSearch.description')}
					let:labelId
				>
					<Switch bind:state={webConfig.ENABLE_WEB_SEARCH} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				<AdminSettingRow
					label={$i18n.t('settings.admin.web.webSearchEngine.label')}
					description={$i18n.t('settings.admin.web.webSearchEngine.description')}
				>
					<SettingsSelect
						bind:value={webConfig.WEB_SEARCH_ENGINE}
						placeholder={$i18n.t('Select a engine')}
						required
					>
						<option disabled selected value="">{$i18n.t('Select a engine')}</option>
						{#each webSearchEngines as engine}
							{#if engine === 'duckduckgo'}
								<option value={engine} disabled={$config?.features?.slim}>DDGS</option>
							{:else if engine === 'searxng'}
								<option value={engine}>Searxng</option>
							{:else if engine === 'bocha'}
								<option value={engine}>Bocha</option>
							{:else if engine === 'tavily'}
								<option value={engine}>Tavily</option>
							{:else}
								<option value={engine}>{engine}</option>
							{/if}
						{/each}
					</SettingsSelect>
				</AdminSettingRow>

				{#if webConfig.WEB_SEARCH_ENGINE === 'searxng'}
					<AdminSettingField
						label={$i18n.t('settings.admin.web.searxngQueryUrl.label')}
					>
						<input
							class={inputClass}
							type="text"
							placeholder={$i18n.t('Enter Searxng Query URL')}
							bind:value={webConfig.SEARXNG_QUERY_URL}
							autocomplete="off"
							required
						/>
					</AdminSettingField>

					<AdminSettingField
						label={$i18n.t(
							'settings.admin.web.searxngSearchLanguageAllEnEsDeFrEtc.label'
						)}
					>
						<input
							class={inputClass}
							type="text"
							placeholder={$i18n.t('Enter Searxng search language')}
							bind:value={webConfig.SEARXNG_LANGUAGE}
							autocomplete="off"
							required
						/>
					</AdminSettingField>
				{:else if webConfig.WEB_SEARCH_ENGINE === 'bocha'}
					<AdminSettingField label={$i18n.t('settings.admin.web.bochaSearchApiKey.label')}>
						<SensitiveInput
							variant="settings"
							placeholder={$i18n.t('Enter Bocha Search API Key')}
							bind:value={webConfig.BOCHA_SEARCH_API_KEY}
						/>
					</AdminSettingField>
				{:else if webConfig.WEB_SEARCH_ENGINE === 'tavily'}
					<AdminSettingField label={$i18n.t('settings.admin.web.tavilyApiKey.label')}>
						<SensitiveInput
							variant="settings"
							placeholder={$i18n.t('Enter Tavily API Key')}
							bind:value={webConfig.TAVILY_API_KEY}
						/>
					</AdminSettingField>

					<AdminSettingField label={$i18n.t('settings.admin.web.tavilySearchDepth.label')}>
						<SettingsSelect bind:value={webConfig.TAVILY_SEARCH_DEPTH} className="w-full">
							<option value="ultra-fast">{$i18n.t('Ultra-fast')}</option>
							<option value="fast">{$i18n.t('Fast')}</option>
							<option value="basic">{$i18n.t('Basic')}</option>
							<option value="advanced">{$i18n.t('Advanced')}</option>
						</SettingsSelect>
					</AdminSettingField>
				{:else if webConfig.WEB_SEARCH_ENGINE === 'duckduckgo'}
					{#if $config?.features?.slim}
						<div class="mb-2.5 text-xs text-gray-500 dark:text-gray-400">
							DDGS is not available on slim build.
						</div>
					{/if}
				{/if}

				{#if webConfig.ENABLE_WEB_SEARCH}
					<AdminSettingField
						label={$i18n.t('settings.admin.web.searchLimits.label')}
						description={$i18n.t('settings.admin.web.searchLimits.description')}
					>
						<div class="flex gap-2">
							<div class="w-full">
								<div class=" self-center text-xs text-gray-600 dark:text-gray-400 mb-1">
									{$i18n.t('settings.admin.web.searchResultCount.label')}
								</div>

								<input
									class="w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
									placeholder={$i18n.t('settings.admin.web.searchResultCount.label')}
									bind:value={webConfig.WEB_SEARCH_RESULT_COUNT}
									required
								/>
							</div>

							<div class="w-full">
								<div class=" self-center text-xs text-gray-600 dark:text-gray-400 mb-1">
									<Tooltip
										content={$i18n.t('settings.admin.web.searchResultCount.description')}
										placement="top-start"
									>
										{$i18n.t('settings.admin.web.concurrentRequests.label')}
									</Tooltip>
								</div>

								<input
									class="w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:focus:border-blue-500"
									placeholder={$i18n.t('settings.admin.web.concurrentRequests.label')}
									bind:value={webConfig.WEB_SEARCH_CONCURRENT_REQUESTS}
									type="number"
									min="0"
								/>
							</div>
						</div>
					</AdminSettingField>

					<AdminSettingField
						label={$i18n.t('settings.admin.web.domainFilterList.label')}
						description={$i18n.t('settings.admin.web.domainFilterList.description')}
					>
						<input
							class={inputClass}
							placeholder={$i18n.t(
								'Enter domains separated by commas (e.g., example.com,site.org,!excludedsite.com)'
							)}
							bind:value={webConfig.WEB_SEARCH_DOMAIN_FILTER_LIST}
						/>
					</AdminSettingField>
				{/if}
			</AdminSettingSection>
		{:else}
			<div class="flex h-full w-full items-center justify-center">
				<Spinner className="size-5" />
			</div>
		{/if}
	</div>
	<div class="flex justify-end pt-6 text-sm font-normal">
		<button
			class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs font-normal text-white transition hover:bg-black disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
			type="submit"
			disabled={!webConfig}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
