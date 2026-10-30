# MaiIdentity

为 MaiBot 提供账号身份、双方确认的关系与本地权限规则，让角色区分“认识谁”和“谁有权管理”。

- 当前版本：`3.2.3`
- MaiBot 版本范围：`1.3.12–1.3.15`
- Plugin SDK 版本范围：`2.15.0–2.16.0`
- 项目地址：[DavidBlackCN/maibot-maiidentity-plugin](https://github.com/DavidBlackCN/maibot-maiidentity-plugin)

仅支持精确配对 **Host 1.3.12 / SDK 2.15.0**、**Host 1.3.15 / SDK 2.16.0**，不支持中间版本或交叉配对，无需私有 Host 补丁。

## 功能

### 本人登记

通过 `/maiidentity 登记我` 登记当前实际 QQ 账号。消息作者及会话由 Host 路由核对，昵称、自称、引用内容和模型输出不能替代身份；不支持代登记、自动合并账号或通过自称恢复已撤销绑定。

### 双方确认的关系

双方登记后可以提出朋友、家人、伴侣关系，由另一方在 24 小时内确认。确认后持续有效，任一方可撤销。这是用户之间的关系声明，不表示用户与 Bot 的关系，也不产生管理权限。

### 有界身份与社交上下文

向模型提供可见身份与关系信息，私密关系不进入公开社交摘要。当前群的公开摘要仅含有界计数和中性/友好风格，不公开账号名单、主体 ID 或执行令牌。关系有争议时使用中性表达。

### Vita 本地管理名单

通过 `management.vita_admin_accounts` 指定可以执行 MaiVita 有限生活管理命令的真实 QQ 账号。默认空名单，任何人都没有 Vita 管理权。MaiHush 的静音权限独立配置；无需安装可选的 MaiCoordinate。

## 安装

### 1. 放置插件

停机备份旧配置和数据。若使用旧 Owner Auth，先移走其可扫描目录，避免与 MaiIdentity 同时启动。新插件放在：

```text
MaiBot/
└── plugins/
    └── maibot-maiIdentity-plugin/
        ├── _manifest.json
        ├── plugin.py
        └── maiidentity/
```

同一插件 ID 只安装一份，使用 MaiBot 自己的 Python 环境。旧 Owner Auth 配置须按[迁移指南](docs/MIGRATION.md)离线转换，不能只改版本号后直接使用。

### 2. 检查路由与权限

默认 `route_scope = ""` 精确匹配 Host 的 `scope=None`，不是通配符；命名 scope 的部署须填写真实 scope。`adapter_namespace` 是稳定的本地命名空间，默认 `host-qq`。

如需管理 Vita，在本插件 `config.toml` 的 `[management]` 中填写管理员 QQ，保存后重载。群管理头衔、昵称、好感度、关系和配置中的显示角色都不能替代该名单。

### 3. 启动与登记

Host 首次加载生成默认配置；实例 ID 与写锁可留空，自动生成并保存在授权数据目录。发送 `/maiidentity help`，再发送 `/maiidentity register`。回复走正常发送链，Vita 睡眠或 Hush 静音时可能收不到回执。

### 从旧版本更新

停机备份代码、`config.toml` 和完整 SDK 数据目录，再替换代码；保留数据库、撤销记录、实例 ID 和命名空间。配置版本为 `"3"`，不是发布版本 `3.2.3`；缺失时在现有 `[plugin]` 内补齐，保留其他设置。

旧配置迁移产生的 `activation.json` 与配置摘要绑定，不能在线直接改配置或删除 `migration_id` 绕过检查。首次迁移、激活和回退见[迁移](docs/MIGRATION.md)与[回滚](docs/ROLLBACK.md)。

## 命令

| 命令 | 说明 |
| --- | --- |
| `/maiidentity help` | 查看帮助 |
| `/maiidentity register`、`/maiidentity 登记我` | 仅登记当前真实消息作者 |
| `/maiidentity 建立关系 对方QQ 朋友` | 提议关系；双方须已登记，也支持家人、伴侣 |
| `/maiidentity 确认关系 关系ID` | 由对方在 24 小时内确认 |
| `/maiidentity 查看关系` | 查看可见关系 |
| `/maiidentity 撤销关系 关系ID` | 任一方撤销关系 |
| `/maiidentity_status`、`/owner_auth_status` | 查看公开就绪状态，兼容原状态入口 |

将 `对方QQ` 与 `关系ID` 替换成实际值。不支持代确认或从聊天中设置管理员。

## 配置

完整中文字段说明见 [config.example.toml](config.example.toml)。未指定的字段使用默认值；固定关闭的能力不能改为 true。

### 插件与路由

```toml
[plugin]
# 配置格式版本，请勿填插件发布版本
config_version = "3"
enabled = true
# 留空自动生成并持久保存；已有部署不要随意改动
instance_id = ""

[identity]
# 本地稳定命名空间；须与显式账号条目一致
adapter_namespace = "host-qq"
# 空值只匹配 scope=None，不表示任意 scope
route_scope = ""
# 默认不预置账号；本人可通过命令登记
accounts = []
```

`writer_lock` 留空使用数据目录中的锁；显式覆盖必须为同一部署共用的绝对路径。`acknowledgement` 是历史兼容项，可留空。`migration_id` 仅由离线迁移流程维护。

### Vita 管理权限

```toml
[management]
# 最多 16 个不重复真实 QQ 字符串；空数组不授权任何人
vita_admin_accounts = ["你的真实QQ号"]
```

权限用于唤醒、重新规划、活动、计划、目标与睡眠等有限管理命令。更改后重载 MaiIdentity，确认操作时会重新检查权限。

### 显式账号与角色（高级）

普通部署保留 `roles.entries = []` 即可。需要显式条目时，先设置稳定 `plugin.instance_id`，账号命名空间与角色 scope 必须匹配部署。以下为结构示例，不应直接照抄账号：

```toml
[[identity.accounts]]
# 与 identity.adapter_namespace 一致
platform = "qq"
adapter_namespace = "host-qq"
account_id = "10001"
enabled = true

[[roles.entries]]
# 仅对指定 context 资源生效；不代替 Vita 管理员名单
role = "operator_admin"
account = { platform = "qq", adapter_namespace = "host-qq", account_id = "10001", enabled = true }
scope = { kind = "instance", instance_id = "你的稳定实例ID", character_id = "default", platform = "qq", adapter_namespace = "host-qq", resource_type = "context", resource_id = "default" }
```

添加表数组前移除同名 `accounts = []` / `entries = []` 空数组定义。可用角色为 member、trusted_contact、stream_moderator、operator_admin、service_agent。复杂嵌套条目建议编辑原始 TOML；字段约束见 [API](docs/API.md)。

### 模型上下文与能力边界

```toml
[context]
# 开启身份上下文，不是模型调用开关
enabled = true
# 上下文 UTF-8 字节预算，范围 1200–8192
budget_bytes = 2048
# 消息缓存有效期，范围 10–3600 秒
cache_ttl_seconds = 300
```

`planner_actor_enabled`、`alias_enabled`、`security.binding_challenge_enabled`、`security.raw_prompt_logging`、`compatibility.legacy_templates_enabled` 和两个 `integrations` 开关固定为 false；`guard_mode` 固定为 `context_only`。登记和关系管理不需要启用这些开关，不提供通用跨插件特权委托。

版本变化见 [UPDATE_NOTES.md](UPDATE_NOTES.md)。

## 已知限制

QQ 账号作者不等于实名认证或真人证明。关系、显示角色与管理授权分别处理；不自动修复其他插件记忆，不修改外部数据库。未知 Planner schema 跳过上下文注入，公开 API 不授予写权限。详见 [LIMITATIONS](docs/LIMITATIONS.md) 与 [CONTRACTS](docs/CONTRACTS.md)。

## 鸣谢

感谢 MaiBot 与插件 SDK、[khiqwq/owner_auth_plugin](https://github.com/khiqwq/owner_auth_plugin)、风花叶和 DavidBlackCN。来源说明见 [SOURCES](docs/SOURCES.md)。

## 许可

[GPL-3.0-or-later](LICENSE)。
