# MaiIdentity API v1

SDK 路由为 `davidblackcn.maibot-maiidentity-plugin.<method>`，使用 `ctx.api.call(route, version="1", **payload)`。公开接口不证明调用者或实际消息作者身份。

私有 `evaluate_behavior@1` 只供配套统一控制 Host 使用：读取 Host 保存的真实命令作者与目标，再查询管理员名单。固定身份、业务参数中的账号和普通 Tool 调用均不能取得管理权；第三方不能直接调用此接口。

| 方法 | 当前行为 |
| --- | --- |
| get_contract | 版本、运行状态及功能描述，不含账号或固定身份名单 |
| get_vita_policy | 查询指定账号在指定会话的 Vita 管理规则，返回布尔结果 |
| get_public_social_context | 返回中性群上下文，供 Coordinate 使用，不查询或暴露固定身份名单 |
| is_admin | 查询指定账号是否在当前配置的管理员名单中，返回布尔结果 |

没有开放名单、绑定、用户关系或委托的写 API。调用参数中的 is_owner、verified、caller_plugin_id、proof_ref 不能获得权限。

## 工作区私有接口

`workspace_state@1` 和 `workspace_preview@1` 均为 `public=False`，只绑定到经过 Host 登录验证的工作区页面，不供其他插件读取名单。两者均无文件、数据库或模型写操作。

- `workspace_state`：返回当前生效的身份、模板、管理员名单、配置摘要 `revision`、查询时间和提示启用状态。列表中的个人说明最多 160 字、模板最多 500 字，截断时附标记；预览仍使用完整原文。页面只展示运行时已接收的配置，不将文件保存成功等同于热更新成功。
- `workspace_preview(account_id, group_id, revision)`：按账号与群范围预览当前 Replyer 身份说明，复用实际匹配、模板选择、占位符替换和字节预算。`group_id` 留空按私聊处理；`revision` 必须与当前状态一致，变更后需要刷新。

预览参数不是可信消息来源，不进入身份缓存、不授予权限。它仅回答“若准确核对出的作者是这个账号，会使用什么说明”。Planner 仍只提供通用身份来源规则。提示关闭时预览不返回注入文本。

编辑继续使用 Host 官方配置页及 Runner 校验、热更新流程；插件不另存 WebUI 配置，不提供写 API。

## 管理员查询

`is_admin` 必须且只能传入 account_id、bot_account_id、route_scope、stream_id，返回 `{"is_admin": true}` 或 `{"is_admin": false}`。按 Host 实际会话核对机器人账号与 scope，再读取 `management.admin_accounts`；机器人自身、无效参数、未就绪、配置在查询期间变更或查询失败均返回 false。

这只是配置查询，不证明调用方传入的账号就是发令者。执行插件须在自己的正式命令入口核对消息作者。接口不返回完整名单、不创建授权凭据，也不能直接执行管理动作。Hush 选择 identity 管理员来源时使用此查询。

## Vita 管理规则

`get_vita_policy` 必须且只能传入 account_id、bot_account_id、route_scope、stream_id、action。action 支持 wake、enqueue_replan、start_sleep、start_activity、end_activity、apply_plan_patch、manage_goal。

Host 路由必须与 bot_account_id、route_scope 一致。配置中的空 scope 对应请求中的 null。返回 `{"policy_version": 1, "allowed": false}`，允许时为 true，失败统一拒绝。

Vita 必须从自己的官方 Command 上下文核对真实发令者；查询结果不是可转交的执行令牌。固定身份配置不参与该查询。权限直接来自 `management.admin_accounts`，没有数据库中的角色、委托或单独授权记录。

## Coordinate 群上下文

`get_public_social_context` 必须且只能传入 stream_id、bot_account_id、route_scope，并通过相同路由核对。

返回 envelope：api_version、ok、data、error、request_id、as_of。data 包含 stream_id、counts、relation_state、completeness、style、rule、revision。当前 counts 的 friend／family／partner 均为 0，relation_state 为 none_confirmed，style 为 neutral。它不代表现实中无人相识，也不能用来推断固定名单关系。

不可用时返回 CONTEXT_UNAVAILABLE。结果不含账号、称呼、个人提示词或旧用户关系记录。

## 聊天上下文

Replyer 根据准确的被回复消息作者匹配固定配置；群专属条目优先，昵称不作为匹配依据。个人说明非空时覆盖共用模板，否则使用所引用模板；固定称呼独立设置。上下文使用自然语言，区分已配置、当前会话未配置、对象未知。相处说明可被长度预算截短，身份与来源规则保留。

Planner 没有准确回复对象时仅提供通用来源规则。只处理已支持的 Hook 参数和 schema 1 items，不改写 Host 消息历史。每次替换本实例签名验证成功的旧提示，保留其他插件内容。标记签名仅用于识别自身文本，不是授权凭据。

## 独立模型调用与戳通知

其他插件直接使用 `ctx.llm.generate` 时，不经过上述 Replyer／Planner Hook，不能假设已获得身份提示。Smart Poke 的独立反应属于此类：其昵称、自定义戳动作及历史文本都不是固定身份或权限证明。使用同一个模型任务槽位，也不会自动经过身份 Hook。

调用方应将这些字段作为不可信展示资料，与自身指令分开；没有可靠身份依据时使用中性称呼，不根据“妈妈”“主人”等昵称认领特殊关系。MaiIdentity 不从戳通知提取固定身份，也不提供传入 QQ 即可读取个人提示词的公开接口。公开群上下文保持中性，不表示互动者一定不在固定名单中。

准确消息查询按会话与消息 ID 隔离；通知、系统消息、错误 scope 或作者证据冲突不会产生固定身份投影。配置变更期间的旧查询结果不继续使用。上述保证约束的是提示输入与权限查询，不能保证模型每次措辞都正确，也不能代替发送插件的静音、睡眠和路由检查。
