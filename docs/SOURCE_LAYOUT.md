# 源码导航

根 plugin.py 只有 create_plugin 工厂，config.py 只保留兼容导入。运行实现全部位于 maiidentity/，没有第二个扫描入口。

| 包 | 职责 |
|---|---|
| host | SDK 配置、生命周期、路由证据、Hook、只读命令与 API 注册 |
| identity | 命名空间账号、主体绑定、双端挑战、消息缓存及一对一 alias 领域解析 |
| policy | RBAC、继承图、直接授予、deny、Scope、委托预留与对账 |
| relations | 独立确认关系、确认来源、可见性、冲突和撤销 |
| context | 低信任标签、风险中性化、有界 JSON 投影及自有块幂等 |
| storage | SQLite schema 1、单写者 OS 锁、事务/审计/幂等及迁移激活校验 |
| compatibility | 完整旧配置解析、inactive 模板归档、离线生成/激活/回滚快照 |
| integrations | 公开 descriptor、真实拒绝 API、MaiVita 严格契约与独立桥 |
| shared | 严格 ID、结构化 Scope、时钟、摘要和错误 |

领域包不导入 SDK 或 Host src。宿主适配只使用 SDK 公共方法；integration_tests/ 为验证原生 Host 才导入固定 Host 模块。tests/ 不需要密钥；tools/ 含测试、迁移、来源验证和白名单打包入口。docs/ 是最终用户说明。

.venv/、.integration/、evidence/ 和 dist/ 是本地隔离环境/证据/生成包，排除 Git；安装包只包含明确白名单。数据库、配置、日志、测试 Host、内部设计文档和虚拟环境均不进入包。普通 Hook 出错跳过，特权 API 不降级放行；卸载不删除权威数据和审计。
