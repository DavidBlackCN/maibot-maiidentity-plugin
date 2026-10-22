# 旧配置离线迁移

支持 plugin/userN/non_owner、owner_auth.users、user（表或数组）、users.entries、owner_auth.User 数量字段、userN.owner_qq。非法 ID、同 scope 冲突、混合格式和未知顶层节会阻止 apply；完整原文始终进入独立备份。先停止旧插件，确认源是离线快照。工具不搜索生产路径，不启动 Host。

在独立虚拟环境安装 requirements-tools.txt；以下路径与账号均为合成示例：

```powershell
python tools/migrate_config.py --dry-run --source D:/test/old.toml --target D:/test/maiidentity-stage --namespace synthetic-adapter --instance synthetic-instance
python tools/migrate_config.py --apply --source D:/test/old.toml --target D:/test/maiidentity-stage --namespace synthetic-adapter --instance synthetic-instance --reviewed-source-sha256 <dry-run给出的SHA256>
```

如果还要备份显式旧数据根，apply 加 `--old-data-root D:/test/old-data`。源配置和数据不覆盖；目标必须是新的独立目录。相同输入重跑返回已校验的 staging 清单；目标改变、来源改变、迁移中断或目标已存在而无匹配清单都拒绝，不清理故障现场。dry-run 仅输出脱敏报告，不写文件。

目标包含 `backup/config.toml`（及可选 old-data）、config.toml、data/identity.db、data/activation.json、report.json、migration.json。配置与 SQLite 不是跨文件事务：先写 preparing 清单，完整生成后写 prepared 清单与文件 SHA256。未完成组合不激活。

每个严格 QQ 账号只创建一个内部主体，全局/群 overlay 分别保留。disabled 和超过 user_count 的数据以 inactive 保存，原 enabled 值也保留。旧昵称和模板全部归档 inactive；不迁成管理员、能力、委托或确认关系。群 overlay 只保留显示偏好，不能突破权限。当前运行时不渲染旧模板，也不承诺继续使用旧“主人”提示。

检查完整报告、原配置备份与所有文件摘要后，显式指定真实 Host 路由 scope 和部署共享锁激活：

```powershell
python tools/migrate_config.py --activate --target D:/test/maiidentity-stage --route-scope default --writer-lock D:/test/locks/maiidentity.lock
```

首次激活可额外传 `--bootstrap-config D:/test/local-bootstrap.toml`。该文件只能包含显式新增的 `[[identity.accounts]]` 和 `[roles]`/`[[roles.entries]]`（角色字段见 [安装](INSTALL.md)）；账号命名空间与实例 scope 必须匹配迁移目标。允许另加本机指定管理员账号，不从旧称谓推断；冲突的已有 disabled 条目不能通过合并暗中启用。未提供文件则没有管理员。文件来源 SHA256 进入激活标记与审计。

该命令使 staging 配置 enabled=true，写本机确认标记、数据库 migration_state 和最后的 activation.json 配置摘要；不启动任何服务。崩溃处于 activating 时启动拒绝，不猜测或自动修复。保留现场后从原快照另建目标重新迁移。此工具只支持首次激活，激活后的配置变更需要另行成对运维方案，不手工删除保护标记。

离线将整个 config.toml 放到新插件目录，将 **data 目录的全部内容** 放到 SDK 为新 ID 授予的空数据根；不能只复制 DB 或换 migration_id。确认旧 ID 目录已停用，单独开启新 ID。启动校验 config 摘要、激活状态与 DB migration_id/schema；缺一项就拒绝。管理员只来自上述本机显式 bootstrap 或全新部署配置，迁移工具不猜测旧“主人”的管理权。

回退见 [ROLLBACK](ROLLBACK.md)。迁移不会修改平台昵称、历史消息、外部记忆或 MaiVita 数据库。
