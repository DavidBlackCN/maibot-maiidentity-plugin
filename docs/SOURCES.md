# 来源与固定版本

本仓库已由 maibot-owner-auth-plugin 更名为 [maibot-maiIdentity-plugin](https://github.com/DavidBlackCN/maibot-maiIdentity-plugin)，origin 使用新地址并保留原历史。起始源码为 `155df1ae0dbde4a8690efb2a082ed9c9c6ede40d`；保留 [GPL-3.0-or-later](../LICENSE)、原项目 [khiqwq/owner_auth_plugin](https://github.com/khiqwq/owner_auth_plugin)、风花叶与 DavidBlackCN 的署名。LICENSE 字节保持不变。

通过已连接 GitHub 核对 [MaiVita](https://github.com/DavidBlackCN/maibot-maivita-plugin/tree/7ec8fa99b6a2745844913465142e86764167e427)：README、SOURCE_LAYOUT、CONTRACTS、LIMITATIONS、integrations/authorization.py、contracts.py 和 host/plugin.py。本次 main 与准备参考 SHA 相同。借鉴包内分层、公开接口、隔离验证和迁移边界；领域、桥和测试独立实现，未复制其 AGPL 生活引擎或修改它的仓库。

真实 Host 为 [MaiBot 1.3.12](https://github.com/Mai-with-u/MaiBot/tree/5c7637e6913c84d1c3d5e742fa9e95a7e70d3501)，公开归档 SHA256 `5c60746188d9050d972dee03a83a793a049f68f38be476393019ff824e0d70d7`。测试锁包含 1882 个普通文件摘要，SDK 2.15.0 Python 源文件也逐一锁定，见 tests/fixtures/source-lock.json。Host/SDK 源码与依赖只在被忽略的测试环境，不进入安装包。

核对了真实 SDK MessageCapability.get_by_id、APICapability.call、PluginContext.paths、插件配置/装饰器，以及 Host runner/plugin_loader、plugin_paths、runner_main、capabilities/components/data、message_utils、HookDispatcher、Planner payload 和 message_id_alias。SDK 返回 message.get_by_id 的业务值已解包，不能按旧版 envelope 再取 message。Host api.call 没有给目标端可信 caller/actor 上下文，不能据路由 public 推断授权。

本地无全局 Python/SDK 更新；T0 使用独立 .venv，T1/T2 使用独立 .integration/host-env，依赖从已有隔离环境只读复制。可复现依赖分别为 requirements-dev.txt 和 requirements-host.txt；新环境可用 tools/setup_host_fixture.py 从固定公开归档准备源。历史机器记录保留在 acceptance.json 与 evidence/；版本变化见 [UPDATE_NOTES](../UPDATE_NOTES.md)。
