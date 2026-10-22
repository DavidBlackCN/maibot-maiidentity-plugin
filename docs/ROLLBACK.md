# 回滚

先停用 MaiIdentity 与所有依赖它的特权消费者，取得部署写锁。完整保存新数据根、activation.json、config.toml、迁移清单与审计；撤销记录不能因为回滚而丢弃。不要把 schema 1 identity.db 交给旧 Owner Auth，也不要让新旧插件双启。

从已校验迁移备份恢复旧配置到一个新的独立目录：

```powershell
python tools/migrate_config.py --rollback-snapshot --target D:/test/maiidentity-stage --restore-to D:/test/owner-auth-restored
```

目标已存在则拒绝；源备份 SHA256 必须匹配清单。新库与撤销审计仍保留。旧代码需要使用操作者保存的 2.1.0 代码快照（本次起始提交 `155df1ae0dbde4a8690efb2a082ed9c9c6ede40d` 可作为来源证据），不要在有未保存修改的工作区运行 reset/clean 来回退。

验证旧代码、旧 ID 与旧配置的配对后，才能在单独实例恢复旧插件。旧插件没有 MaiIdentity 的新鉴权和关系隔离语义；依赖新能力的消费者保持关闭。工具不启动旧服务、不重放绑定确认、委托、延迟任务或任何外部副作用。未知执行结果仍需对账，回滚数据库不能撤销已发生的外部动作。
