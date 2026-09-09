"""add file category & source_path & org nullable

Revision ID: a9c0d3e1f2b4
Revises: fd5fced6db3a
Create Date: 2026-09-09 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = 'a9c0d3e1f2b4'
down_revision = 'fd5fced6db3a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增分类与原始路径字段（存量行 category 走应用层按 purpose/parser_type 回填脚本或保持空）
    op.add_column('file_metadata', sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True))
    op.add_column('file_metadata', sa.Column('source_path', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True))
    op.create_index(op.f('ix_file_metadata_category'), 'file_metadata', ['category'], unique=False)

    # 用户级文件（头像/小助手图标背景等）不归属组织：允许 organization_id 为空
    op.alter_column('file_metadata', 'organization_id',
                    existing_type=sqlmodel.sql.sqltypes.AutoString(),
                    nullable=True)

    # 存量数据回填：document → document；asset 图片 → note_image，其余 → note_asset
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        conn.exec_driver_sql(
            "UPDATE file_metadata SET category = 'document' WHERE purpose = 'document' AND category IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE file_metadata SET category = 'note_image' WHERE purpose = 'asset' AND category IS NULL "
            "AND original_name ~* '\\.(png|jpe?g|gif|webp|svg|bmp|ico)$'"
        )
        conn.exec_driver_sql(
            "UPDATE file_metadata SET category = 'note_asset' WHERE purpose = 'asset' AND category IS NULL"
        )
    else:
        # 非 PostgreSQL（如测试 SQLite）：走 Python 行级回填，保证语义一致
        table = sa.table(
            'file_metadata',
            sa.column('id', sqlmodel.sql.sqltypes.AutoString()),
            sa.column('purpose', sa.String()),
            sa.column('parser_type', sqlmodel.sql.sqltypes.AutoString()),
            sa.column('original_name', sqlmodel.sql.sqltypes.AutoString()),
            sa.column('category', sqlmodel.sql.sqltypes.AutoString()),
        )
        rows = conn.execute(sa.select(table.c.id, table.c.purpose, table.c.original_name)).fetchall()
        import re
        img_re = re.compile(r"\.(png|jpe?g|gif|webp|svg|bmp|ico)$", re.I)
        for rid, purpose, original_name in rows:
            if purpose == 'document':
                cat = 'document'
            elif img_re.search(original_name or ''):
                cat = 'note_image'
            else:
                cat = 'note_asset'
            conn.execute(
                sa.update(table).where(table.c.id == rid).values(category=cat)
            )


def downgrade() -> None:
    op.drop_index(op.f('ix_file_metadata_category'), table_name='file_metadata')
    op.alter_column('file_metadata', 'organization_id',
                    existing_type=sqlmodel.sql.sqltypes.AutoString(),
                    nullable=False)
    op.drop_column('file_metadata', 'source_path')
    op.drop_column('file_metadata', 'category')
