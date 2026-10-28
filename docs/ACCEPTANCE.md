# MaiIdentity 3.2.0 验收证据

本版打包必须重新运行 T0 单元、T1 原版 Runner、T2 原生 Host、迁移 CLI，并生成与当前 candidate_files、validation_files 一致的 acceptance.json。任何旧源码记录都不能替代当前通过记录。

新增验证包括：有限生活管理权限与显式拒绝、撤销绑定后升级/重载不复活、本群公开关系摘要的私密过滤与争议中性化、中文本人登记/双方确认，以及实际 Host Planner schema 1 的追加上下文往返。联合 CI 位于 MaiVita 仓库 ecosystem，peers.json 锁定本插件实际提交。

单仓库 CI 覆盖 Windows / Python 3.13 / SDK 2.15.0 与 Linux / Python 3.12.15 / SDK 2.16.0。完整原版 Host 的联合检查以交付包中的实际源码指纹、测试报告和最新 GitHub Actions 为准，不用本说明中的文字代替运行证据。

T1/T2 使用合成消息，不连接真实 QQ 或付费模型。当前源码的真实模型 I1、真实 QQ、生产部署及长期使用观察均需单独记录。H01/H02/通用 H03 继续关闭；官方命令入口可用不等于通用跨插件特权传输已实现。
