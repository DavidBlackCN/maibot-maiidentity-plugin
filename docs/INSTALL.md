# 安装

MaiIdentity 3.0.0 修复构建接受两组精确配对：原 Windows / Python 3.13、Host 1.3.12（`5c7637e6913c84d1c3d5e742fa9e95a7e70d3501`）/ SDK 2.15.0；以及 Linux / Python 3.12.15、Host 1.3.15（`062d45cf8bd4272ac57d7ec03fcf405e5a458211`）/ SDK 2.16.0。Manifest 上下限并不授权中间版本或混搭，运行时仍检查精确配对。使用 Bot 自己的虚拟环境。安装不等于真实 QQ 或生产验收。

先停机并移走旧 `com.khiqwq.owner-auth-plugin` 的可扫描目录，备份旧代码、config.toml 和数据根。不要把旧配置复制到新插件后仅修改版本号；按 [迁移](MIGRATION.md) 离线转换。同一 Host 只放一个 MaiIdentity 目录。加载检查旧 ID 的已加载注册表，失败则拒绝启动；Host 没有原子锁定两个不同插件 ID 的接口，因此停用旧目录是安装前提。

根 plugin.py 是唯一入口；复制安装包内容到一个插件目录。保留 LICENSE。配置仍位于该目录的 config.toml；SDK 数据根按新 ID 分配为实例目录下 `data/plugins/davidblackcn.maibot-maiidentity-plugin/`，不能沿用旧 ID 猜测路径。源码导入不会创建数据库。全新默认配置禁用、无账号、无管理员。已有旧格式会明确校验失败，不自动清空。

全新安装不需要填写部署字段。Host 自动生成默认配置，直接启动后发送 `/maiidentity_status`：

```toml
[plugin]
enabled = true
config_version = "3"
instance_id = ""
writer_lock = ""
migration_id = ""

[identity]
adapter_namespace = "host-qq"
route_scope = ""
accounts = []
```

空 instance_id 在 SDK 数据目录首次启动时生成并持久保存；空 writer_lock 使用该目录中的部署锁和数据库锁，防止重复写入者。旧 acknowledgement 字段保留兼容，但不再要求确认字符串。已有显式 instance_id 和命名空间可以保留，尤其不要改变已配置角色的身份命名空间。

空 route_scope 精确匹配 Host 消息的 scope=None（已观察到的 Snowluma 默认路由），不是通配符。使用非空 scope 的部署可填写实际 scope，跨 scope 仍被拒绝。adapter_namespace 默认为稳定的本地 host-qq 名称，不声称证明远端适配器身份。消息必须匹配 Host bot.qq_account、qq 平台，且不能是机器人自身消息。accounts 为空可正常加载和提供上下文，不会自动赋予管理员身份。

可选：若要配置明确账号和本地角色，使用相同 instance_id/adapter_namespace。例如下面全部是合成值，应替换为你自己明确配置的标识：

```toml
[[identity.accounts]]
platform = "qq"
adapter_namespace = "synthetic-qq-adapter"
account_id = "10001"
enabled = true
```

管理员必须单独、显式配置。以下片段追加到上述合成配置，只给明确 context 资源内的实例管理角色，不给 MaiVita 能力：

```toml
[[roles.entries]]
role = "operator_admin"
account = { platform = "qq", adapter_namespace = "synthetic-qq-adapter", account_id = "10001", enabled = true }
scope = { kind = "instance", instance_id = "synthetic-instance", character_id = "default", platform = "qq", adapter_namespace = "synthetic-qq-adapter", resource_type = "context", resource_id = "default" }
```

配置数组有固定 schema，不按 user_count 动态生成槽位。复杂条目建议离线编辑；未承诺任意 Host WebUI 数组编辑控件。角色/账号配置改变要求重载：旧服务先关闭，下一次加载在单事务内调和配置来源记录并增加 revision。相同配置重载不会恢复已撤销绑定。最后一个管理员的恢复或移除只走本机配置/离线管理，聊天没有恢复入口。

迁移数据的配置与 activation.json 绑定；不要在线直接修改已激活迁移配置，修改后会因摘要不匹配拒绝启动。当前工具只支持首次离线激活，后续成对配置更新需要独立运维流程；不要删除 migration_id 或标记绕过校验。

writer_lock 可留空自动使用 SDK 数据目录；显式覆盖时必须是同一部署共用的绝对路径，不能按进程各建一份。另有 SDK 数据根内的 writer.lock 防止同一数据根因误配部署锁而出现两个写者，两把锁均在失败/卸载时释放。运行数据只使用 SDK 授予的数据根；不要放入源码目录。`/owner_auth_status` 与 `/maiidentity_status` 仅显示公开就绪状态，走普通 send.text，没有静默豁免、账号名单或全局最近操作。
