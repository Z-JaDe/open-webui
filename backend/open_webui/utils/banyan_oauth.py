"""banyan 内置 GitHub OAuth 凭据（编译期常量，非运行时配置）。

用户裁决：GitHub OAuth 需要作为 banyan 的内置登录能力，但 Client ID/Secret 由
用户自行申请、自持保管——**不进设置页、不靠 env 手配**。唯一填写处就是本文件
的两个常量；填好后重启后端即生效（设置页 Authentication 已改为说明文字，
不再提供任何 OAuth 表单）。

┌─ 申请步骤 ────────────────────────────────────────────────────────────┐
│ 1. GitHub → 右上角头像 → Settings → Developer settings                │
│    → OAuth Apps → New OAuth App                                        │
│ 2. Application name   ：随意（如 banyan）                               │
│    Homepage URL       ：https://<你的部署域名>/                         │
│    Authorization callback URL（关键）：                                │
│        https://<你的部署域名>/oauth/github/login/callback              │
│    （即后端路由 GET /oauth/{provider}/login/callback；register 时      │
│      REDIRECT_URI 留空会按请求自动推导出该地址，二者一致即可。           │
│      若反代/内外网域名不一致，须显式填 BANYAN_GITHUB_REDIRECT_URI，     │
│      且与 GitHub App 登记的 callback 完全一致。）                       │
│ 3. 创建后复制 Client ID，点 "Generate a new client secret" 复制 Secret │
│    （Secret 只显示一次），填入下方两个常量。                            │
└──────────────────────────────────────────────────────────────────────┘

逃生门（测试用）：环境变量 GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET /
GITHUB_CLIENT_REDIRECT_URI / GITHUB_CLIENT_SCOPE 优先于本模块常量
（见 config.py 的 GITHUB_* 装配）。其余 provider（google/microsoft/oidc）
保持上游 env 行为，默认不启用。

本模块刻意不 import 任何 open_webui 模块（config.py 会 import 本模块，
引入依赖会造成循环导入）。
"""

# ===== 唯一填写处：把你申请到的 GitHub OAuth App 凭据填在这里 =====

BANYAN_GITHUB_CLIENT_ID = ''  # ← 填 Client ID

BANYAN_GITHUB_CLIENT_SECRET = ''  # ← 填 Client Secret（Generate 后只显示一次）

# 回调地址。留空 = 按请求自动推导 https://<请求域名>/oauth/github/login/callback；
# 反代/域名不一致时才需要显式填写，且必须与 GitHub App 登记的 callback 一致。
BANYAN_GITHUB_REDIRECT_URI = ''

# 一般无需改动；GitHub 取用户信息所需的 scope。
BANYAN_GITHUB_SCOPE = 'user:email'

# ==================================================================
