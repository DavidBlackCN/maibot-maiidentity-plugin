# MaiIdentity 3.1.1：官方 Host 命令，无需补丁

支持精确组合 Host 1.3.12 / SDK 2.15.0、Host 1.3.15 / SDK 2.16.0。安装即可启用；沿用现有实例、数据库与配置，不需要确认串或手填锁路径。

- `/maiidentity status`：公开状态。
- `/maiidentity register`：仅登记实际发言者当前 QQ 账号，不授予角色、管理员权限，也不合并账号。撤销的绑定不能自行恢复。
- `/maiidentity relation propose 对方QQ friend`：双方均先登记；也支持 `family`、`partner`。只建立本群公开的用户声明关系。
- 对方在 24 小时内发送 `/maiidentity relation confirm 关系ID`；确认后持续有效，第三人及发起人不能代确认。
- 任一参与者可以 `/maiidentity relation revoke 关系ID`；`/maiidentity relations` 查看本群公开关系。跨群确认或撤销拒绝，关系不产生执行权限。

需要 Vita 管理时，仅在 Identity 本地配置已有的这一项：

```toml
[management]
vita_admin_accounts = ["你的QQ号"]
```

默认没有管理员。更改后重载 Identity；移除账号会撤销本配置生成的授权。显式拒绝优先。无需在 Vita 再配置一次，不授予 Hush、身份绑定管理或账号合并权限。

自身管理命令仅由官方 Host Command 分发入口接收，验证实际消息与顶层账号、文本、会话、平台及群号一致，并验证 Bot 账号和路由。API 与 Tool 不提供登记或关系写入口。

`get_vita_policy` 是面向已安装插件的只读查询，只返回 `policy_version` 与 `allowed`。输入不视为身份凭据，结果不含角色、关系、主体 ID、管理员名单或令牌；查询不会登记账号、写审计记录或执行命令。它会暴露给已安装插件“某账号在指定范围是否满足有限规则”这一布尔信息。Vita 必须独立从自己的 Command 入口取得实际发言者；查询结果不可转交给公开写 API 使用。

旧 `authorize_vita_command` 接口始终拒绝，旧 Host 引用无效。`security.resolve_command` 已从 Manifest 和运行时移除。信任边界是官方 Host/Runner 与本地配置，不承诺隔离同进程恶意 Python 插件。

通用跨插件特权 H03、原子远端消费、H01 回执豁免、H02 频率所有权覆盖继续未实现。真实 QQ、生产部署与模型 I1 验收另行记录，不能用合成测试替代。
