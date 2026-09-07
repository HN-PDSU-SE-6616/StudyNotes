"""文件解析任务：parse_document（异步流水线后端）"""
import logging
import os

from app.models.file import FileMetadata, FileStatus
from app.models.note import Note, NoteBlock
from app.models.project import Project
from app.services import parser as parser_service
from app.services.storage import get_storage
from app.tasks.common import run_async
from app.worker import celery_app

logger = logging.getLogger(__name__)

# 文件扩展名 → 笔记图标
FILE_ICON = {
    "md": "📝", "html": "🌐", "txt": "📄", "code": "💻", "pdf": "📕",
    "docx": "📘", "xlsx": "📊", "ppt": "📽️", "xmind": "🧠",
    "image": "🖼️", "unknown": "📎",
}


@celery_app.task(name="app.tasks.parse.parse_document", bind=True, max_retries=2)
def parse_document(self, file_id: str) -> None:
    """解析上传文档 → 创建笔记 → 触发向量索引（worker 入口）"""
    try:
        run_async(lambda session: parse_file_now(file_id, session))
    except Exception as exc:  # noqa: BLE001
        logger.exception("解析文档失败 file=%s", file_id)
        raise self.retry(exc=exc, countdown=30)


async def parse_file_now(file_id: str, session) -> None:
    """解析文档（可被 Celery worker 与 API 降级路径共同调用）"""
    file_meta = await session.get(FileMetadata, file_id)
    if not file_meta:
        logger.warning("file_metadata 不存在: %s", file_id)
        return
    if file_meta.purpose != "document":
        # asset 类文件在接口层已直接完成
        return

    file_meta.status = FileStatus.PARSING.value
    file_meta.parser_type = parser_service.get_file_type(file_meta.original_name)
    await session.commit()

    try:
        storage = get_storage()
        data = await storage.get(file_meta.storage_key)
        content_url = f"/api/v1/files/{file_meta.id}/content"
        blocks = parser_service.parse_document(file_meta.original_name, data, content_url)

        project = await session.get(Project, file_meta.project_id) if file_meta.project_id else None
        if not project:
            raise RuntimeError("文档缺少归属项目（project_id）")

        # 解析源文件名作为笔记标题（去扩展名）
        stem = os.path.splitext(os.path.basename(file_meta.original_name))[0][:200] or "导入文档"
        note = Note(
            project_id=project.id,
            title=stem,
            icon=FILE_ICON.get(file_meta.parser_type or "unknown", "📎"),
            owner_id=file_meta.owner_id,
            creator_id=file_meta.owner_id,
            last_editor_id=file_meta.owner_id,
            source_file_id=file_meta.id,
        )
        session.add(note)
        await session.flush()

        if not blocks:
            blocks = [{"type": "paragraph", "content": {"text": "（空内容）"}}]
        for order, block in enumerate(blocks):
            session.add(NoteBlock(
                note_id=note.id,
                type=block.get("type", "paragraph"),
                content=block.get("content") or {},
                sort_order=order,
            ))

        file_meta.status = FileStatus.COMPLETED.value
        file_meta.chunk_count = len(blocks)
        file_meta.error_message = None
        await session.commit()
        await session.refresh(note)
        logger.info("文档解析完成: file=%s note=%s blocks=%s", file_id, note.id, len(blocks))

        # 触发向量索引（index 队列由独立 worker 消费）
        try:
            from app.tasks.index import index_note

            index_note.delay(note.id)
        except Exception:  # noqa: BLE001
            logger.warning("下发索引任务失败: %s", note.id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("解析文档异常 file=%s", file_id)
        file_meta.status = FileStatus.FAILED.value
        file_meta.error_message = str(exc)[:500]
        await session.commit()
        raise
