> 当前联动版本 3.1.0（2026-10-28）：默认安装与可选可信命令以[本版说明](JOINT_RELEASE.md)为准。下文原有通用特权 API 限制仍适用；可选有限命令需要独立 Host 扩展。

# 公共 API major 1

正式 SDK 路由为 `davidblackcn.maibot-maiidentity-plugin.<method>`，调用使用 `ctx.api.call(route, version="1", **payload)`。该方法已通过真实 Runner 和 Host 调用。`public=True` 仅表示路由可访问。

| 方法 | 当前行为 |
|---|---|
| get_contract | 匿名公开：插件、配置、DB、API 版本及实际启用边界，不含账号 |
| resolve_identity / get_identity | UNTRUSTED_CONTEXT |
| authorize | UNTRUSTED_CONTEXT，不签发 proof 或执行许可 |
| get_confirmed_relations | UNTRUSTED_CONTEXT，不泄露私密关系存在性 |
| build_context / get_diagnostics | UNTRUSTED_CONTEXT，不接受参数构造 actor |
| 绑定、委托、关系写方法 | 未注册，descriptor 标明 unsupported |

普通响应包含 api_version=1、ok（严格布尔）、data、error、request_id、as_of（UTC 带时区）。尚无可信请求 ID 传输时 request_id=null。错误是稳定 code 和 retryable=false，不回显输入或凭证。调用传入的 is_owner、verified、issuer、caller_plugin_id、user_id、context_ref、proof_ref 都不能认证；真实历史消息也不能证明调用者。

本地领域服务提供账号唯一绑定/撤销、双端挑战、RBAC、角色继承、deny、Scope、委托预留/回执/对账和关系确认。它们是受信进程内领域接口，不是网络 API；不得把任意客户端 JSON 转成 Actor 或直接调用 operator 方法。当前没有模型可写 Tool、聊天绑定命令或远程管理端点。跨进程原子核验和执行尚未实现。

角色、业务 Capability、Scope 与 manifest 的四项 SDK capability 分别维护。operator_admin 没有 maivita.wake/private.read/configure 等默认权限。关系称谓、动态好感度和模型上下文均不发放能力。可用授予先取并集，再限制到请求/资源/Scope；匹配 deny 优先。缺字段、未知能力和过期均拒绝。

委托需要显式目的、精确能力/资源/范围/参数、时限、次数和预算；首版不转委托。任务只保存 grant_ref；预留时重新读取绑定 epoch、授权/策略 revision，并在同一 SQLite 事务消费次数。预留响应明确 `reservation_only=true, external_execution_authorized=false`，不能当外部执行令牌。未知结果不返还次数、不换新键重发；需可信执行者对账后才可继续。首版不提供外部执行器或调度器。

Hook 使用的模型投影 schema_version=1 与 API 响应不同。Replyer 的 subject 来自精确被回复消息；actor 始终不由 subject 推导。Planner 的未知 typed items 不修改；有已核实 extra_prompt 形状时只能给一般来源规则。默认预算 2048 UTF-8 字节，删除非必要字段仍保留来源说明；没有 proof、账号列表、挑战或私密关系。自有块使用实例所有权标记做幂等替换，跨重载仍能替换旧块。内部标记密钥只存自己的 SDK 数据根，此标记不能认证身份、授予权限或被 API 当作 proof。
