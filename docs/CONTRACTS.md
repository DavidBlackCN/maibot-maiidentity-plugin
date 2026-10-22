# MaiVita 契约桥 1.0.0

固定参考 MaiVita `7ec8fa99b6a2745844913465142e86764167e427`（插件 0.3.1，契约 1.0.0）。本插件未修改 MaiVita 仓库，未实现它的生活引擎。

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
