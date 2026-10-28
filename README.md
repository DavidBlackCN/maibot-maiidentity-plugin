# MaiIdentity 3.2.2

为 MaiBot 提供身份绑定、本地权限规则、双方确认的公开关系和有界模型上下文。昵称、自称主人、好感度和关系不产生执行权限。

默认启用，实例 ID 与写锁自动管理；默认空 route_scope 精确匹配 Snowluma 的 scope=None。使用 `/maiidentity help` 查看本人登记、关系提议/确认/撤销命令。

在本地 `[management] vita_admin_accounts` 填入允许管理 Vita 的真实 QQ 号即可启用有限生活管理规则。默认名单为空，没有预置管理员；Hush 权限仍独立配置。通用跨插件特权、任意账号合并、代确认及原子远端特权消费关闭。

本版新增 `get_public_social_context@1`：只返回当前群公开关系的有界计数和中性/友好风格，不暴露账号、主体、私密关系或执行令牌。Planner schema 1 可追加公开上下文，仍不伪造 Planner actor。

支持精确组合 Host 1.3.12 / SDK 2.15.0、Host 1.3.15 / SDK 2.16.0。配置版本 3、SQLite schema 1、API major 1 不变。无需私有 Host 补丁。

使用与升级见 [产品指南](docs/PRODUCT_GUIDE.md)，旧版配置迁移见 [MIGRATION](docs/MIGRATION.md)，接口边界见 [API](docs/API.md)。验收记录见 [ACCEPTANCE](docs/ACCEPTANCE.md)，不能用旧源码的测试记录替代本版或真实 QQ 验收。

保留原项目 [khiqwq/owner_auth_plugin](https://github.com/khiqwq/owner_auth_plugin)、风花叶与 DavidBlackCN 的署名及 [GPL-3.0-or-later](LICENSE)。运行实现独立重构，未复制 MaiVita 生活引擎。


### 2026-10-28 WebUI 配置兼容修复

修复空字符串枚举导致的 Select.Item 崩溃，以及必填账户条目无法生成编辑 Schema。历史确认字段不再显示为空选项；固定关闭的特权字段只读显示。运行时模型和权限校验不变。高级嵌套角色/旧引擎表请使用原始 TOML 编辑，避免 Host 表单把对象转成字符串。

若 Identity 页面提示缺少 plugin.config_version，在现有 [plugin] 内补入 config_version = "3" 后保存并重载，保留原有其他配置。Vita 使用 "3"，Coordinator 使用 "1"。这些是配置格式版本，不是插件发布版本；不能填写 3.2.2 或 0.5.2。不要删除数据或只保留 enabled。当前源码真实模型 I1 和 QQ 验收仍待进行，不沿用旧版本通过记录。
