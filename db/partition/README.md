# 表分区启用指引（预留方案）

首期 `notes` / `file_metadata` 以普通表落地，主键为单列 `id`（UUID 字符串）。
当单表行数达到 **5000 万** 或文件元数据超 **2000 万** 时，建议启用 PostgreSQL
原生 Range 分区（按 `created_at` 月度），步骤如下：

## 迁移方案（pg_partman 推荐）

1. 安装扩展并初始化：

```sql
CREATE EXTENSION IF NOT EXISTS pg_partman;
CREATE SCHEMA partman;
```

2. 新建分区父表（结构与现有表一致，主键含分区列）：

```sql
CREATE TABLE note_part (
    id            VARCHAR(36),
    created_at    TIMESTAMP NOT NULL,
    ...其余字段同 note...,
    PRIMARY KEY (created_at, id)
) PARTITION BY RANGE (created_at);
```

3. 用 pg_partman 建立月度分区模板并批量创建：

```sql
SELECT partman.create_parent(
    p_parent_table => 'public.note_part',
    p_control      => 'created_at',
    p_type         => 'native',
    p_interval     => '1 month',
    p_premake      => 3
);
```

4. 数据回填后原子切换应用（应用写入切换至新表前先完成存量迁移），
   期间在应用侧维护 `note_part` 上的查询与外键一致性。

## 应用侧注意点

- 分区列进入主键后，所有 `REFERENCES note(id)` 的外键需改为
  `(created_at, id)` 组合外键 —— 这是**延迟到数据量达标再做**的主因。
- Qdrant payload 中的 `note_id` 与数据库解耦，不受分区迁移影响。
- 迁移窗口内建议停写只读切换，或使用 `pg_partman` 的 `run_maintenance_proc`
  定期自动创建/清理分区。
