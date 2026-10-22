# MaiIdentity

MaiIdentity 为 MaiBot 提供命名空间账号与内部主体、确定性本地策略、独立确认关系及有界模型上下文。它从 Owner Auth 2.1.0 重构而来；“主人/恋人”、昵称、聊天声明和动态好感度都不产生权限。

当前插件 **3.0.0**；配置 **"3"**；SQLite schema **1**；API major **"1"**。插件 ID 为 `davidblackcn.maibot-maiidentity-plugin`。仓库已更名为 [maibot-maiIdentity-plugin](https://github.com/DavidBlackCN/maibot-maiIdentity-plugin)，保留原 Owner Auth 仓库历史。

已验证 Windows / Python 3.13、固定 Host 1.3.12 与 SDK 2.15.0。默认禁用且没有任何账号或管理员。先停止旧插件，按 [安装](docs/INSTALL.md) 或 [离线迁移](docs/MIGRATION.md) 准备配置与独立数据；不要只修改旧配置版本号，不要双启新旧 ID。

实现包括：

- 严格账号 ID、绑定唯一性与撤销 epoch，双端挑战领域状态机。
- RBAC、无环角色继承、能力、显式 deny 和结构化 Scope，角色管理防自提权。
- 有用途/参数/范围/时间/次数/预算约束的委托预留、回执及未知结果对账。
- 有来源、可见性与 revision 的确认关系；私密关系不进入模型投影。
- 精确消息与缓存冲突拒绝，Replyer subject 与 actor 分离；风险昵称中性化，自有上下文块幂等且保留其他插件文本。
- 全格式旧配置预览、独立目标、备份/校验、成对激活及回滚快照。

跨插件特权、聊天绑定、Planner actor、alias 真实传输、旧模板和原始 prompt 日志关闭。`get_contract@1` 公开实际状态；其余受保护 API 返回 UNTRUSTED_CONTEXT。MaiVita 桥保持 v1.0.0 严格字段，H01/H02/H03 与统一策略传输尚未联通。身份历史和模型输出不能构成执行许可。

`/owner_auth_status` 与 `/maiidentity_status` 是脱敏只读状态别名，通过普通发送权限响应，不泄露账号名单或全局最近事件。

验证命令：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python tools/run_tests.py
.venv/Scripts/python tools/setup_host_fixture.py
python -m venv .integration/host-env
.integration/host-env/Scripts/python -m pip install -r requirements-host.txt
.integration/host-env/Scripts/python tools/run_runner_smoke.py
.integration/host-env/Scripts/python tools/run_host_smoke.py --isolated-root D:/test/new-maiidentity-host
.venv/Scripts/python tools/package.py
```

基础 Host 冒烟使用原生独立插件运行时、合成消息与临时数据库，不连接真实平台、不发群消息、不调用付费模型。它不等于完整 bot CLI、模型效果、生态联合验收或生产批准。详细结果与指纹见 [验收](docs/ACCEPTANCE.md)；边界见 [限制](docs/LIMITATIONS.md)。

其他说明：[API](docs/API.md)、[MaiVita 契约](docs/CONTRACTS.md)、[源码导航](docs/SOURCE_LAYOUT.md)、[回滚](docs/ROLLBACK.md)、[来源](docs/SOURCES.md)。

保留原项目 [khiqwq/owner_auth_plugin](https://github.com/khiqwq/owner_auth_plugin)、风花叶与 DavidBlackCN 的署名及 [GPL-3.0-or-later](LICENSE)。运行实现独立重构，未复制 MaiVita 的生活引擎。内部设计集不随仓库或安装包分发。
