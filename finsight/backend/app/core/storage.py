"""Storage abstraction and hardened local filesystem backend for FinSight (Phase 12.4).

Provides a decoupled storage interface allowing backend and worker components
to read, write, delete, and check files without hardcoded filesystem paths.
"""

from abc import ABC, abstractmethod
from pathlib import Path
import os
import re
import tempfile
import uuid
import aiofiles

from app.core.config import get_settings
from app.core.exceptions import ProcessingError

settings = get_settings()


class StorageBackend(ABC):
    """Abstract interface defining the FinSight document storage layer."""

    @abstractmethod
    def get_document_key(self, document_id: uuid.UUID | str, filename: str) -> str:
        """Generate a canonical, sanitized, collision-resistant storage key."""
        pass

    @abstractmethod
    async def save(self, key: str, content: bytes) -> str:
        """Save bytes under the specified key atomically. Returns the resolved storage key."""
        pass

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Read bytes stored under the specified key. Raises ProcessingError if not found."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete object stored under key. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether an object exists under the specified key."""
        pass

    @abstractmethod
    def get_path(self, key: str) -> Path:
        """
        Return the local Path for local engines / parsers (pypdf, pdfplumber).
        Raises ProcessingError if the storage engine is remote or key is invalid.
        """
        pass


class LocalStorageBackend(StorageBackend):
    """
    Hardened local filesystem storage backend.

    Implements path traversal protection, symlink traversal prevention,
    atomic writes via temporary files, and directory isolation within root_path.
    """

    def __init__(self, root_path: Path | str | None = None):
        if root_path is None:
            self.root_path = settings.DOCUMENTS_PATH.resolve()
        else:
            self.root_path = Path(root_path).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def get_document_key(self, document_id: uuid.UUID | str, filename: str) -> str:
        """
        Derive safe, deterministic document storage key: {document_id}_{sanitized_basename}.
        Enforces UUID formatting and strips directory separators / traversal tokens.
        """
        # Validate or parse document_id as standard UUID
        if isinstance(document_id, str):
            doc_uuid = uuid.UUID(document_id)
        else:
            doc_uuid = document_id

        # Sanitize filename: take only the file basename
        safe_basename = Path(filename).name.strip()
        # Remove any leading dots or illegal characters, fallback if empty
        safe_basename = re.sub(r"[^\w\.\-\_]", "_", safe_basename).lstrip(".")
        if not safe_basename:
            safe_basename = "document"

        return f"{doc_uuid}_{safe_basename}"

    def _resolve_safe_path(self, key: str, must_exist: bool = False) -> Path:
        """
        Resolve storage key to an absolute filesystem Path and strictly enforce that
        it resides within self.root_path. Prevents path traversal and symlink escapes.
        """
        # Reject keys attempting traversal or absolute paths
        if ".." in key or key.startswith("/") or key.startswith("\\"):
            raise ProcessingError(
                message="Path traversal attempt detected in storage key",
                details={"key": key},
            )

        target_path = (self.root_path / key).resolve()

        # Strict containment check: target_path must have root_path as parent/ancestor
        try:
            target_path.relative_to(self.root_path)
        except ValueError as exc:
            raise ProcessingError(
                message="Access denied: path traversal out of storage root",
                details={"key": key, "resolved_path": str(target_path)},
            ) from exc

        # Disallow symlinks pointing outside root_path
        if target_path.is_symlink():
            real_target = target_path.resolve()
            try:
                real_target.relative_to(self.root_path)
            except ValueError as exc:
                raise ProcessingError(
                    message="Symlink traversal escape detected",
                    details={"key": key, "real_target": str(real_target)},
                ) from exc

        if must_exist and not target_path.exists():
            raise ProcessingError(
                message="File not found in storage",
                details={"key": key, "path": str(target_path)},
            )

        return target_path

    async def save(self, key: str, content: bytes) -> str:
        """
        Atomically save bytes under key.
        Writes to a temporary file on the same filesystem, then renames to target key.
        """
        dest_path = self._resolve_safe_path(key, must_exist=False)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary file in the destination directory to ensure same filesystem for atomic rename
        temp_fd, temp_file_path = tempfile.mkstemp(
            dir=dest_path.parent,
            prefix=".tmp_upload_",
            suffix=".tmp",
        )
        os.close(temp_fd)

        try:
            async with aiofiles.open(temp_file_path, "wb") as f:
                await f.write(content)

            # Atomic replace on same filesystem
            os.replace(temp_file_path, dest_path)
        except Exception as exc:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass
            raise ProcessingError(
                message="Failed to write file to local storage",
                details={"key": key, "error": str(exc)},
            ) from exc

        return key

    async def read(self, key: str) -> bytes:
        """Read bytes from storage under key."""
        target_path = self._resolve_safe_path(key, must_exist=True)
        try:
            async with aiofiles.open(target_path, "rb") as f:
                return await f.read()
        except Exception as exc:
            raise ProcessingError(
                message="Failed to read file from storage",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def delete(self, key: str) -> bool:
        """Delete file from storage under key."""
        try:
            target_path = self._resolve_safe_path(key, must_exist=False)
        except ProcessingError:
            return False

        if not target_path.exists():
            return False

        try:
            target_path.unlink()
            return True
        except OSError as exc:
            raise ProcessingError(
                message="Failed to delete file from storage",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def exists(self, key: str) -> bool:
        """Check if file exists under key."""
        try:
            target_path = self._resolve_safe_path(key, must_exist=False)
            return target_path.exists() and target_path.is_file()
        except ProcessingError:
            return False

    def get_path(self, key: str) -> Path:
        """Return the validated local Path for parsers."""
        return self._resolve_safe_path(key, must_exist=True)


_STORAGE_BACKEND_INSTANCE: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """
    Factory function returning the configured StorageBackend instance.
    Uses singleton caching for performance.
    """
    global _STORAGE_BACKEND_INSTANCE
    if _STORAGE_BACKEND_INSTANCE is None:
        backend_type = getattr(settings, "STORAGE_BACKEND", "local").lower()
        if backend_type == "local":
            _STORAGE_BACKEND_INSTANCE = LocalStorageBackend()
        else:
            raise ValueError(f"Unsupported storage backend: '{backend_type}'. Only 'local' is supported.")
    return _STORAGE_BACKEND_INSTANCE
