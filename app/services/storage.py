"""对象存储抽象层：StorageProvider 接口 + LocalFS 实现（预留 S3/MinIO）

对象路径规则（新文件，按 用户→类型 分类存储）：
    storage_root/{owner_id}/{category}/{yyyy}/{mm}/{file_id}{ext}
存量文件仍按旧 storage_key 读取（organization/{yyyy}/{mm}/...），不做物理迁移。
访问一律通过 /api/v1/files/{file_id}/content 带权限校验，不暴露物理路径。
"""
import abc
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class StorageProvider(abc.ABC):
    """存储提供者接口（与 S3/MinIO 语义对齐）"""

    @abc.abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """写入对象（幂等覆盖）"""

    @abc.abstractmethod
    async def get(self, key: str) -> bytes:
        """读取对象内容"""

    @abc.abstractmethod
    async def open_stream(self, key: str):
        """打开二进制流（FileResponse 等使用），无对象时抛 FileNotFoundError"""

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """删除对象"""

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """对象是否存在"""

    @abc.abstractmethod
    def build_key(self, owner_id: int, category: str, file_id: str, ext: str = "") -> str:
        """构造对象 key：{owner_id}/{category}/{yyyy}/{mm}/{file_id}{ext}"""


class LocalStorageProvider(StorageProvider):
    """本地文件系统实现（首期默认）"""

    def __init__(self, root: str = ""):
        self.root = Path(root or settings.storage_root)

    def _resolve(self, key: str) -> Path:
        # 防路径穿越：仅允许相对 key
        safe = Path(key)
        if safe.is_absolute() or ".." in safe.parts:
            raise ValueError(f"非法存储 key: {key}")
        path = self.root / safe
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        # 异步文件写交给线程池，保持事件循环不被大文件阻塞
        import anyio

        await anyio.to_thread.run_sync(self._write_sync, path, data)

    @staticmethod
    def _write_sync(path: Path, data: bytes) -> None:
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"对象不存在: {key}")
        return path.read_bytes()

    async def open_stream(self, key: str):
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"对象不存在: {key}")
        import anyio

        return await anyio.to_thread.run_sync(open, path, "rb")

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            self._delete_sync(path)

    @staticmethod
    def _delete_sync(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def build_key(self, owner_id: int, category: str, file_id: str, ext: str = "") -> str:
        now = datetime.now()
        return f"{owner_id}/{category}/{now:%Y}/{now:%m}/{file_id}{ext}"


class S3StorageProvider(LocalStorageProvider):
    """预留：MinIO/S3 实现。接入时按 boto3 语义重写四个 IO 方法即可。"""

    def __init__(self, root: str = ""):
        raise NotImplementedError("S3 存储待接入，当前请使用 local 实现")


_storage: StorageProvider | None = None


def get_storage() -> StorageProvider:
    global _storage
    if _storage is None:
        if settings.storage_provider == "local":
            _storage = LocalStorageProvider()
        else:
            _storage = S3StorageProvider()
    return _storage


def reset_storage() -> None:
    """测试用：重置单例"""
    global _storage
    _storage = None
