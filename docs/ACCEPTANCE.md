# 验收范围

本版完成独立实现与隔离验证，不声明生产可用。2026-10-25（Asia/Shanghai）对当前源码重新运行 T0、原始 Runner T1、原生 Host T2 及迁移 CLI；精确计数、源码指纹和机器摘要见 [acceptance.json](acceptance.json)。固定 Host/SDK 文件锁位于 tests/fixtures/source-lock.json；其中 MaiVita 提交是历史契约参考，不是当前联合测试的运行版本。

打包现在必须校验报告中的 candidate_files 与实际源码一致，且 T0/T1/T2/迁移均通过；CI 在打包前重新生成这些证据，不能把旧 acceptance.json 随新代码直接发布。仓库外联合收口证据单独记录三个核心插件实际源码与发送链结果。evidence/ 中旧证据已归档，新结果仍不代表真实平台认证。

| 层级 | 已运行命令 | 验证范围 |
|---|---|---|
| T0 | `.venv/Scripts/python tools/run_tests.py` | 无密钥确定性单元、静态边界、schema、事务、生命周期与迁移故障 |
| T1 | `.integration/host-env/Scripts/python tools/run_runner_smoke.py` | 原始 Runner 子进程、真实 SDK 注册/IPC/跨插件 API 调用与拒绝；配置/库存/消息业务端口为合成值 |
| T2 | `.integration/host-env/Scripts/python tools/run_host_smoke.py --isolated-root <新的独立目录>` | 原生 Host Supervisor、能力服务、消息库/序列化、分发器、禁用发现/启用/重载/撤销/故障/清理；未替换 Host 模块 |
| CLI | `.venv/Scripts/python tools/rehearse_migration.py` | 真正迁移 CLI 的 dry-run/apply/重跑/激活/回滚快照；仅合成配置 |
| 包 | `.venv/Scripts/python tools/package.py` 和 `tools/verify_package.py <生成包>` | 明确白名单、字节校验、无内部设计文档/数据/密钥/测试环境 |

T2 是基础独立 Host 插件运行时冒烟；未启动完整 bot CLI、WebUI、平台适配器或付费模型。合成消息通过原生 Host 消息库与 Hook 传输，不能称为真实平台认证。没有群发送或模型请求。CI 配置已提供，本地运行不等于 GitHub CI 已执行。

| 矩阵 | 对应自动用例 |
|---|---|
| 账号唯一/命名空间/撤销/挑战 | tests/test_identity.py：strict_qq、namespace_binding、concurrent_binding、bilateral_challenge、challenge_failure |
| 精确 ID/缓存/alias | test_exact_api_cache_conflicts_missing_ids_and_ttl、test_alias_unique_collision_short_original_same_shape_and_history、test_real_alias_hash_collision_and_cross_instance_stream_namespace；T1 缺 API ID 冲突；T2 真实 DB 查询 |
| RBAC/deny/Scope/角色自提权 | tests/test_policy_relations.py：roles_deny_scope_self_escalation_and_revision、nested_roles；test_authorization_evidence_expired_scope_subject_host_denied |
| 委托/并发/预算/未知结果 | delegation_concurrent_single_use、queued_delegation_revalidation、delegation_cannot_expand、unknown_result_with_multiple_remaining_uses |
| actor/subject 与伪造 API | test_sdk_lifecycle_actor_subject_multi_hook_and_cleanup、test_api_forged_caller_context_owner_proof_denied；T1/T2 真实跨插件拒绝 |
| 迁移/回滚/崩溃/源完整性 | tests/test_migration_lifecycle.py、test_activation_faults.py、test_migration_source_and_target_modified_blocked；CLI 演练 |
| 生命周期/存储故障 | test_writer_lease_unknown_schema_and_closed_storage、test_load_failure_old_plugin_and_config_update_cleanup、test_empty_disabled_no_io_storage_failure_load_cleanup；T2 真实加载失败/重载/锁释放 |
| 包与版本/许可 | tests/test_static_package.py、白名单安装包验证 |

关系规范 R01–R15 对应结构断言：

| 编号 | 用例/可证明范围 |
|---|---|
| R01/R02/R03 | relationship_claims_are_labels；风险昵称中性、低信任、Unicode/伪分隔符无法逃出 JSON；不判恶意 |
| R04/R05 | relations_bilateral_privacy_revision_no_permissions 与 current_relations_and_projection；当前确认/撤销记录决定投影，partner 不产生 wake |
| R06 | current_relations_and_projection、projection_budget；无动态评分写权限/关系路径 |
| R07 | alias 碰撞、Planner 无 trigger、typed items 跳过；一般规则不声明 actor |
| R08 | distinct A/B subject、current_relations_and_projection；同名与引用不复制主体/关系 |
| R09 | relations_bilateral_privacy_revision_no_permissions；公开无私密存在性泄漏 |
| R10 | relation_operator_character_and_conflict；可见互斥记录 disputed，不取最新聊天 |
| R11 | 昵称“恋人”保持标签，固定短规则允许正常聊天，不输出普遍告诫 |
| R12 | projection_budget_idempotence、原生双插件 Hook；保留其他块和未知字段，typed items 不修改 |
| R13 | 存储/加载错误、缓存过期、空配置测试；普通 Hook 跳过，公共特权 API 拒绝 |
| R14/R15 | relationship_claims_are_labels、current_relations_and_projection；玩笑/历史快照/记忆声明不写权威库，不改外库 |

上述断言验证来源、结构和确定性权限，不证明自然语言模型在任意提示下不会误认。尚未执行：真实账号双端私有挑战、可信 H03/proof 发行/消费、MaiVita 与统一策略/H01/H02 联调、记忆与社交生态、完整守护进程/WebUI、模型效果和长期观察。相应入口保持关闭或明确 unsupported。

2026-10-27 兼容性修订：当前 T0 为 92 项；原基线独立 T1/T2 与迁移仍绑定当前源码重新记录。Linux Python 3.12.15 / Host 1.3.15 / SDK 2.16.0 的 92 项单元回归及三核心原生 IPC 联合结果单独提供，不把原 1.3.12 的记录当作新版宿主验收。
