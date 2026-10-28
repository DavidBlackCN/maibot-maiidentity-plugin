> 当前联动版本 3.1.0（2026-10-28）：默认安装与可选可信命令以[本版说明](JOINT_RELEASE.md)为准。下文原有通用特权 API 限制仍适用；可选有限命令需要独立 Host 扩展。

# MaiVita 契约桥 1.0.0

历史契约形状参考 MaiVita `7ec8fa99b6a2745844913465142e86764167e427`（插件 0.3.1，契约 1.0.0）。本插件未修改 MaiVita 仓库，未实现它的生活引擎。

| 类型 | 严格字段 |
|---|---|
| IdentityRequest | contract_version、request_id、context_ref、action、character_id、stream_id |
| IdentityDecision | contract_version、request_id、verified、subject_ref、issuer、stream_id、issued_at、expires_at、proof_ref |
| PolicyRequest | IdentityRequest 加 identity_proof_ref、state_version、config_revision |
| PolicyDecision | contract_version、request_id、allowed、reason_code、state_version、config_revision、expires_at |

contract_version 固定 "1.0.0"；character_id 固定 default。action 为 read_private/wake/interrupt_sleep/replan/configure。未知字段、字符串布尔值、无时区时间和超过 30 秒的身份生命周期都拒绝。verified=true 还必须有主体/proof 引用；类型校验本身不认证发行方。

独立桥接层将 v1 请求转为严格否定响应：身份 verified=false，策略 allowed=false/POLICY_UNAVAILABLE。当前没有绑定真实传输，不能通过修改 payload 变成允许，也没有把通用 envelope 塞入严格模型。

H03：固定 Host 的 api.call 确认了调用方 SDK capability，但仅把 api_args 转给目标处理器，没有可信终端 actor/caller/context_ref 发行与验证服务。H03 disabled。Owner 身份通过不能覆盖统一策略拒绝；私密读取、唤醒、打断、重规划和配置权都未联通。

H01：可信发送回执的用途、attempt、stream 和一次性消费独立验收，当前 unsupported。H02：插件归属化调频/撤销也独立验收，当前 unsupported。MaiIdentity 不声明或调用 frequency.set_adjust，不发送管理例外消息。

后续联合验收必须验证发行方/caller、真实上下文、请求/动作/资源/流绑定、epoch/revision、过期/撤销/重放、跨进程原子消费，以及身份允许但策略拒绝。JSON Schema、单元端口、原生拒绝路径与生态互通是不同证据层级。

## 2026-10-24 联合审查修复候选补充

固定支持 Host 1.3.12 / SDK 2.15.0，manifest 与加载检查一致。新增能力目录 maihush.mute / maihush.renew / maihush.unmute / maihush.configure，均不可委托，均无内置角色自动授予。执行目标必须是 QQ 的 stream scope、group resource，仍要求独立 external_policy=True。静态目录由本地代码控制，未开放任意插件注册或重定义命名空间的接口。

上述目录只供后续受审计的 H03 适配；当前受保护 API 继续 UNTRUSTED_CONTEXT。Hush 本地命令的授权源未迁移，不采用“本地 owner 或 Identity allow”的双重放行。身份资格、业务规则与实际执行各自独立；关系和预约结果不能冒充远端执行授权。

当前 get_contract 的 host/sdk 字段报告实际运行版本；支持 1.3.12/2.15.0 和 1.3.15/2.16.0 配对。此兼容性修订没有开放 H03、委托传输或跨插件写权限。


2026-10-27 默认安装修订：Vita 的空 allowed_streams 表示所有 Host 接入会话，非空仍精确限制；Identity 的空 route_scope 仅匹配消息 scope=None。自动实例标识、自动锁和默认启用均不建立可信调用者身份，不开放 H01/H02/H03 或跨插件特权。
