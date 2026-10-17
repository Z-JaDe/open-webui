<script lang="ts">
	import { getBackendConfig } from '$lib/apis';
	import {
		getAdminConfig,
		getLdapConfig,
		getLdapServer,
		updateLdapConfig,
		updateLdapServer,
		updateAdminConfig
	} from '$lib/apis/auths';
	import { getGroups } from '$lib/apis/groups';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { config } from '$lib/stores';
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import AdminSettingField from './AdminSettingField.svelte';
	import AdminSettingRow from './AdminSettingRow.svelte';
	import AdminSettingSection from './AdminSettingSection.svelte';
	import SettingsSelect from '$lib/components/common/SettingsSelect.svelte';

	const i18n: any = getContext('i18n');

	let adminConfig: any = null;
	let groups: any[] = [];

	let ENABLE_LDAP = false;
	let LDAP_SERVER = {
		label: '',
		host: '',
		port: null,
		attribute_for_mail: 'mail',
		attribute_for_username: 'uid',
		app_dn: '',
		app_dn_password: '',
		search_base: '',
		search_filters: '',
		use_tls: false,
		validate_cert: false,
		certificate_path: '',
		ciphers: '',
		enable_group_management: false,
		enable_group_creation: false,
		attribute_for_groups: 'memberOf'
	};

	const inputClass =
		'w-full h-7 rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';
	const textareaClass =
		'w-full rounded-lg border border-gray-100/50 bg-gray-50/40 px-2 py-1.5 text-xs text-gray-700 outline-hidden transition-colors placeholder:text-gray-300 focus:border-blue-400 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-300 dark:placeholder:text-gray-700 dark:focus:border-blue-500';

	const updateLdapServerHandler = async () => {
		await updateLdapConfig(localStorage.token, ENABLE_LDAP);
		if (!ENABLE_LDAP) return true;

		// Honor the "Default to memberOf" hint: fall back to the default group
		// attribute when it is left blank while group management is enabled, so
		// the save isn't rejected by the backend's required-field check.
		if (LDAP_SERVER.enable_group_management && !LDAP_SERVER.attribute_for_groups?.trim()) {
			LDAP_SERVER.attribute_for_groups = 'memberOf';
		}

		const res = await updateLdapServer(localStorage.token, LDAP_SERVER).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		return !!res;
	};

	const updateAdminHandler = async () => {
		if (!adminConfig) return true;
		const res = await updateAdminConfig(localStorage.token, adminConfig).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (res?.sessions_revoked) {
			localStorage.removeItem('token');
			window.location.href = '/auth?state=logout&form=signin';
			return false;
		}
		if (res) {
			adminConfig = res;
		}
		return !!res;
	};

	const submitHandler = async () => {
		const ldapSaved = await updateLdapServerHandler();
		if (!ldapSaved) return;

		// Save MFA policy last because changing it revokes the current session.
		const adminSaved = await updateAdminHandler();
		if (adminSaved) {
			toast.success($i18n.t('Settings saved successfully!'));
			await config.set(await getBackendConfig());
		}
	};

	onMount(async () => {
		await Promise.all([
			(async () => {
				adminConfig = await getAdminConfig(localStorage.token);
			})(),
			(async () => {
				groups = await getGroups(localStorage.token);
			})(),
			(async () => {
				// Merge into the defaults so any key the backend omits (e.g. an
				// older backend without the group settings) keeps its default.
				LDAP_SERVER = { ...LDAP_SERVER, ...(await getLdapServer(localStorage.token)) };
			})()
		]);

		const ldapConfig = await getLdapConfig(localStorage.token);
		ENABLE_LDAP = ldapConfig.ENABLE_LDAP;
	});
</script>

<form class="flex h-full flex-col justify-between text-sm" on:submit|preventDefault={submitHandler}>
	<h2 class="text-sm font-medium text-gray-900 dark:text-white mb-4">
		{$i18n.t('settings.admin.authentication.title')}
	</h2>

	<div class="flex-1 min-h-0 overflow-y-auto scrollbar-hover pr-1.5">
		{#if adminConfig !== null}
			<AdminSettingSection
				title={$i18n.t('settings.admin.authentication.sections.userAccess.title')}
				first
			>
				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.defaultUserRole.label')}
					description={$i18n.t('settings.admin.authentication.defaultUserRole.description')}
				>
					<SettingsSelect
						bind:value={adminConfig.DEFAULT_USER_ROLE}
						placeholder={$i18n.t('Select a role')}
					>
						<option value="pending">{$i18n.t('pending')}</option>
						<option value="user">{$i18n.t('user')}</option>
						<option value="admin">{$i18n.t('admin')}</option>
					</SettingsSelect>
				</AdminSettingRow>

				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.defaultGroup.label')}
					description={$i18n.t('settings.admin.authentication.defaultGroup.description')}
				>
					<SettingsSelect
						bind:value={adminConfig.DEFAULT_GROUP_ID}
						placeholder={$i18n.t('Select a group')}
					>
						<option value={''}>{$i18n.t('None')}</option>
						{#each groups as group}
							<option value={group.id}>{group.name}</option>
						{/each}
					</SettingsSelect>
				</AdminSettingRow>

				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.loginForm.label')}
					description={$i18n.t('settings.admin.authentication.loginForm.description')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_LOGIN_FORM} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.newSignUps.label')}
					description={$i18n.t('settings.admin.authentication.newSignUps.description')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_SIGNUP} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.apiKeys.label')}
					description={$i18n.t('settings.admin.authentication.apiKeys.description')}
					let:labelId
				>
					<Switch bind:state={adminConfig.ENABLE_API_KEYS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				{#if adminConfig?.ENABLE_API_KEYS}
					<AdminSettingRow
						label={$i18n.t('settings.admin.authentication.apiKeyEndpointRestrictions.label')}
						description={$i18n.t(
							'settings.admin.authentication.apiKeyEndpointRestrictions.description'
						)}
						let:labelId
					>
						<Switch
							bind:state={adminConfig.ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS}
							ariaLabelledbyId={labelId}
						/>
					</AdminSettingRow>

					{#if adminConfig?.ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS}
						<AdminSettingField
							label={$i18n.t('settings.admin.authentication.allowedEndpoints.label')}
							description={$i18n.t('settings.admin.authentication.allowedEndpoints.description')}
						>
							<input
								class={inputClass}
								type="text"
								placeholder={`e.g.) /api/v1/messages, /api/v1/channels`}
								bind:value={adminConfig.API_KEYS_ALLOWED_ENDPOINTS}
							/>
							<a
								href="https://docs.openwebui.com/reference/api-endpoints"
								target="_blank"
								class="mt-1 block text-[0.6875rem] text-gray-400 underline hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300"
							>
								{$i18n.t('To learn more about available endpoints, visit our documentation.')}
							</a>
						</AdminSettingField>
					{/if}
				{/if}

				<AdminSettingField
					label={$i18n.t('settings.admin.authentication.jwtExpiration.label')}
					description={$i18n.t('settings.admin.authentication.jwtExpiration.description')}
				>
					<input
						class={inputClass}
						type="text"
						placeholder={`e.g.) "30m","1h", "10d". `}
						bind:value={adminConfig.JWT_EXPIRES_IN}
					/>

					{#if adminConfig.JWT_EXPIRES_IN === '-1'}
						<a
							href="https://docs.openwebui.com/reference/env-configuration#jwt_expires_in"
							target="_blank"
							class="mt-1 block rounded-lg bg-yellow-500/10 px-2 py-1.5 text-[0.6875rem] text-yellow-700 underline dark:text-yellow-200"
						>
							{$i18n.t('No expiration can pose security risks.')}
						</a>
					{/if}
				</AdminSettingField>
			</AdminSettingSection>

			<AdminSettingSection title={$i18n.t('Multi-factor authentication')}>
				<AdminSettingRow label={$i18n.t('Require an authenticator for all users')}>
					<Switch
						bind:state={adminConfig.ENABLE_MFA}
						ariaLabel={$i18n.t('Require an authenticator for all users')}
					/>
				</AdminSettingRow>
				<p class="-mt-1 text-[0.6875rem] leading-4 text-gray-400 dark:text-gray-600">
					{$i18n.t('Changes sign out all devices. Users enroll on their next sign-in.')}
				</p>
				{#if adminConfig.ENABLE_MFA}
					<AdminSettingRow label={$i18n.t('Allow OAuth sign-in without an authenticator')}
						><Switch
							bind:state={adminConfig.MFA_ALLOW_OAUTH_BYPASS}
							ariaLabel={$i18n.t('Allow OAuth sign-in without an authenticator')}
						/></AdminSettingRow
					>
					<AdminSettingRow label={$i18n.t('Allow trusted-header sign-in without an authenticator')}
						><Switch
							bind:state={adminConfig.MFA_ALLOW_TRUSTED_HEADER_BYPASS}
							ariaLabel={$i18n.t('Allow trusted-header sign-in without an authenticator')}
						/></AdminSettingRow
					>
				{/if}
			</AdminSettingSection>

			<AdminSettingSection
				title={$i18n.t('settings.admin.authentication.sections.pendingAccounts.title')}
			>
				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.adminDetails.label')}
					description={$i18n.t('settings.admin.authentication.adminDetails.description')}
					let:labelId
				>
					<Switch bind:state={adminConfig.SHOW_ADMIN_DETAILS} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				{#if adminConfig.SHOW_ADMIN_DETAILS}
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.adminContactEmail.label')}
						description={$i18n.t('settings.admin.authentication.adminContactEmail.description')}
					>
						<input
							class={inputClass}
							type="email"
							placeholder={$i18n.t('Leave empty to use first admin user')}
							bind:value={adminConfig.ADMIN_EMAIL}
						/>
					</AdminSettingField>
				{/if}

				<AdminSettingField
					label={$i18n.t('settings.admin.authentication.pendingUserOverlayTitle.label')}
					description={$i18n.t('settings.admin.authentication.pendingUserOverlayTitle.description')}
				>
					<Textarea
						className={textareaClass}
						placeholder={$i18n.t(
							'Enter a title for the pending user info overlay. Leave empty for default.'
						)}
						bind:value={adminConfig.PENDING_USER_OVERLAY_TITLE}
					/>
				</AdminSettingField>

				<AdminSettingField
					label={$i18n.t('settings.admin.authentication.pendingUserOverlayContent.label')}
					description={$i18n.t(
						'settings.admin.authentication.pendingUserOverlayContent.description'
					)}
				>
					<Textarea
						className={textareaClass}
						placeholder={$i18n.t(
							'Enter content for the pending user info overlay. Leave empty for default.'
						)}
						bind:value={adminConfig.PENDING_USER_OVERLAY_CONTENT}
					/>
				</AdminSettingField>
			</AdminSettingSection>
		{/if}

		<AdminSettingSection title={$i18n.t('settings.admin.authentication.sections.ldap.title')}>
			<AdminSettingRow
				label={$i18n.t('settings.admin.authentication.ldap.label')}
				description={$i18n.t('settings.admin.authentication.ldap.description')}
				let:labelId
			>
				<Switch bind:state={ENABLE_LDAP} ariaLabelledbyId={labelId} />
			</AdminSettingRow>

			{#if ENABLE_LDAP}
				<div class="grid grid-cols-1 gap-x-3 gap-y-2.5 sm:grid-cols-2">
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.label.label')}
						description={$i18n.t('settings.admin.authentication.label.description')}
					>
						<input
							class={inputClass}
							required
							placeholder={$i18n.t('Enter server label')}
							bind:value={LDAP_SERVER.label}
						/>
					</AdminSettingField>
				</div>

				<div class="grid grid-cols-1 gap-x-3 gap-y-2.5 sm:grid-cols-2">
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.host.label')}
						description={$i18n.t('settings.admin.authentication.host.description')}
					>
						<input
							class={inputClass}
							required
							placeholder={$i18n.t('Enter server host')}
							bind:value={LDAP_SERVER.host}
						/>
					</AdminSettingField>

					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.port.label')}
						description={$i18n.t('settings.admin.authentication.port.description')}
					>
						<Tooltip
							placement="top-start"
							content={$i18n.t('Default to 389 or 636 if TLS is enabled')}
							className="w-full"
						>
							<input
								class={inputClass}
								type="number"
								placeholder={$i18n.t('Enter server port')}
								bind:value={LDAP_SERVER.port}
							/>
						</Tooltip>
					</AdminSettingField>
				</div>

				<div class="grid grid-cols-1 gap-x-3 gap-y-2.5 sm:grid-cols-2">
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.applicationDn.label')}
						description={$i18n.t('settings.admin.authentication.applicationDn.description')}
					>
						<Tooltip
							content={$i18n.t('The Application Account DN you bind with for search')}
							placement="top-start"
						>
							<input
								class={inputClass}
								placeholder={$i18n.t('Enter Application DN')}
								bind:value={LDAP_SERVER.app_dn}
							/>
						</Tooltip>
					</AdminSettingField>

					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.applicationDnPassword.label')}
						description={$i18n.t('settings.admin.authentication.applicationDnPassword.description')}
					>
						<SensitiveInput
							variant="settings"
							placeholder={$i18n.t('Enter Application DN Password')}
							required={false}
							bind:value={LDAP_SERVER.app_dn_password}
						/>
					</AdminSettingField>
				</div>

				<div class="grid grid-cols-1 gap-x-3 gap-y-2.5 sm:grid-cols-2">
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.attributeForMail.label')}
						description={$i18n.t('settings.admin.authentication.attributeForMail.description')}
					>
						<Tooltip
							content={$i18n.t(
								'The LDAP attribute that maps to the mail that users use to sign in.'
							)}
							placement="top-start"
						>
							<input
								class={inputClass}
								required
								placeholder={$i18n.t('Example: mail')}
								bind:value={LDAP_SERVER.attribute_for_mail}
							/>
						</Tooltip>
					</AdminSettingField>

					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.attributeForUsername.label')}
						description={$i18n.t('settings.admin.authentication.attributeForUsername.description')}
					>
						<Tooltip
							content={$i18n.t(
								'The LDAP attribute that maps to the username that users use to sign in.'
							)}
							placement="top-start"
						>
							<input
								class={inputClass}
								required
								placeholder={$i18n.t('Example: sAMAccountName or uid or userPrincipalName')}
								bind:value={LDAP_SERVER.attribute_for_username}
							/>
						</Tooltip>
					</AdminSettingField>
				</div>

				<AdminSettingField
					label={$i18n.t('settings.admin.authentication.searchBase.label')}
					description={$i18n.t('settings.admin.authentication.searchBase.description')}
				>
					<Tooltip content={$i18n.t('The base to search for users')} placement="top-start">
						<input
							class={inputClass}
							required
							placeholder={$i18n.t('Example: ou=users,dc=foo,dc=example')}
							bind:value={LDAP_SERVER.search_base}
						/>
					</Tooltip>
				</AdminSettingField>

				<AdminSettingField
					label={$i18n.t('settings.admin.authentication.searchFilters.label')}
					description={$i18n.t('settings.admin.authentication.searchFilters.description')}
				>
					<input
						class={inputClass}
						placeholder={$i18n.t('Example: (&(objectClass=inetOrgPerson)(uid=%s))')}
						bind:value={LDAP_SERVER.search_filters}
					/>
					<a
						class="mt-1 block text-[0.6875rem] text-gray-400 underline hover:text-gray-700 dark:text-gray-600 dark:hover:text-gray-300"
						href="https://ldap.com/ldap-filters/"
						target="_blank"
					>
						{$i18n.t('Click here for filter guides.')}
					</a>
				</AdminSettingField>

				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.tls.label')}
					description={$i18n.t('settings.admin.authentication.tls.description')}
					let:labelId
				>
					<Switch bind:state={LDAP_SERVER.use_tls} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				{#if LDAP_SERVER.use_tls}
					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.certificatePath.label')}
						description={$i18n.t('settings.admin.authentication.certificatePath.description')}
					>
						<input
							class={inputClass}
							placeholder={$i18n.t('Enter certificate path')}
							bind:value={LDAP_SERVER.certificate_path}
						/>
					</AdminSettingField>

					<AdminSettingRow
						label={$i18n.t('settings.admin.authentication.validateCertificate.label')}
						description={$i18n.t('settings.admin.authentication.validateCertificate.description')}
						let:labelId
					>
						<Switch bind:state={LDAP_SERVER.validate_cert} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.ciphers.label')}
						description={$i18n.t('settings.admin.authentication.ciphers.description')}
					>
						<Tooltip content={$i18n.t('Default to ALL')} placement="top-start">
							<input
								class={inputClass}
								placeholder={$i18n.t('Example: ALL')}
								bind:value={LDAP_SERVER.ciphers}
							/>
						</Tooltip>
					</AdminSettingField>
				{/if}

				<!-- LICENSE covers this Open WebUI wordmark.
					Do not alter, remove, obscure, or replace it except as LICENSE permits:
					https://docs.openwebui.com/license. -->
				<AdminSettingRow
					label={$i18n.t('settings.admin.authentication.enableGroupManagement.label')}
					description={$i18n.t('settings.admin.authentication.enableGroupManagement.description')}
					let:labelId
				>
					<Switch bind:state={LDAP_SERVER.enable_group_management} ariaLabelledbyId={labelId} />
				</AdminSettingRow>

				{#if LDAP_SERVER.enable_group_management}
					<AdminSettingRow
						label={$i18n.t('settings.admin.authentication.enableGroupCreation.label')}
						description={$i18n.t('settings.admin.authentication.enableGroupCreation.description')}
						let:labelId
					>
						<Switch bind:state={LDAP_SERVER.enable_group_creation} ariaLabelledbyId={labelId} />
					</AdminSettingRow>

					<AdminSettingField
						label={$i18n.t('settings.admin.authentication.groupAttribute.label')}
						description={$i18n.t('settings.admin.authentication.groupAttribute.description')}
					>
						<Tooltip content={$i18n.t('Default to memberOf')} placement="top-start">
							<input
								class={inputClass}
								placeholder="memberOf"
								bind:value={LDAP_SERVER.attribute_for_groups}
							/>
						</Tooltip>
					</AdminSettingField>
				{/if}
			{/if}
		</AdminSettingSection>

		<!-- banyan FU-3（用户裁决）：GitHub OAuth 为内置登录，凭据编译于
			backend/open_webui/utils/banyan_oauth.py（用户自持申请），不作为运行时
			配置存在——上游的 OAuth/OIDC 配置表单已整体移除，此处只保留说明。 -->
		<AdminSettingSection title={$i18n.t('settings.admin.authentication.sections.oauthOidc.title')}>
			<div
				class="rounded-lg border border-gray-100/50 bg-gray-50/40 px-3 py-2.5 text-xs leading-5 text-gray-600 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-400"
			>
				<p class="font-medium text-gray-700 dark:text-gray-300">
					{$i18n.t('GitHub OAuth is built into banyan and requires no configuration here.')}
				</p>
				<p>
					{$i18n(
						'Credentials are compiled into backend/open_webui/utils/banyan_oauth.py (apply for your own GitHub OAuth App, then edit that file and restart). The callback URL to register on GitHub is https://&lt;your-domain&gt;/oauth/github/login/callback'
					)}
				</p>
				<p>
					{$i18n(
						'Leave the credentials empty and the GitHub sign-in button simply stays hidden; all other settings on this page keep working as usual.'
					)}
				</p>
			</div>
		</AdminSettingSection>
	</div>

	<div class="flex justify-end pt-6 text-sm font-normal">
		<button
			class="flex h-7 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-2.5 text-xs font-normal text-white transition hover:bg-black disabled:opacity-60 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-white"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
