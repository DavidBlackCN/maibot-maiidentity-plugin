# MaiIdentity 3.1.0 联动使用说明

正确名称是 **maiidentity / MaiIdentity**。默认启用，自动生成部署实例 ID 和数据锁；默认 `route_scope = ""` 精确对应 Host 的 `scope=None`，不是任意范围。

官方 Host 1.3.12 / SDK 2.15.0、Host 1.3.15 / SDK 2.16.0 上可直接使用 `/maiidentity status` 和既有回复上下文投影。关系或身份上下文不等于执行许可。

以下命令仅在单独验证的 Host command-context v1 扩展中可执行。插件会通过 Host 能力 RPC 验证真实命令及发言者，官方 Host 缺少此能力时拒绝写入。

- `/maiidentity register`：仅登记发言者自己的当前 QQ 账号，不合并账号、不授予角色或权限。被撤销的绑定需要本地复核，不能自行恢复。
- `/maiidentity relation propose 对方QQ friend`：双方均须登记；也支持 `family`、`partner`。这是本群的公开用户声明关系。
- 对方在 24 小时内发送 `/maiidentity relation confirm 关系ID`：双方确认后持续有效；发起人或第三人不能代确认。
- 任一参与者使用 `/maiidentity relation revoke 关系ID` 撤销；`/maiidentity relations` 查看本群公开关系。跨群确认或撤销拒绝。

可选 Vita 命令授权只需在本地插件配置填写：

```toml
[management]
vita_admin_accounts = ["你的QQ号"]
```

默认空列表不授予任何人权限。此配置只授予 Vita 唤醒、重新规划，保留显式拒绝优先，不授予 Hush 管理、身份绑定管理或账号合并。更改后重载插件；删除账号会撤销本配置生成的授权。命令的来源、真实账号、Bot 账号、scope 和会话必须匹配；原始命令以外的 API 参数无效。

旧的通用特权 API、跨账号绑定挑战、Hush H03、H01/H02、通用原子远端消费继续关闭。Host 扩展不是官方功能，也不会随插件安装自动修改 Host；生产部署和真实 QQ 验收另行记录。
