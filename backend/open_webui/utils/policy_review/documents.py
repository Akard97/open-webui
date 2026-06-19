"""Phase 2 document helpers for Policy Review: validation, storage, and text
extraction. These are the monkeypatchable seams the router imports — router
tests stub `store_upload` / `extract_text` / `delete_stored` / `copy_stored`
so they never touch the filesystem or a real parser.
"""
import io
import os
import uuid
from typing import Optional

from open_webui.storage.provider import Storage

MAX_UPLOAD_MB = int(os.getenv('POLICY_REVIEW_MAX_UPLOAD_MB', '25'))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'md', 'txt'}


def _ext(filename: str) -> str:
    return (os.path.splitext(filename or '')[1][1:] or '').lower()


def validate_upload(filename: str, size: int) -> None:
    """Raise ValueError (-> HTTP 400 in the router) for a disallowed or bad upload."""
    ext = _ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f'File type .{ext or "?"} is not supported. Upload a PDF, DOCX, MD, or TXT file.'
        )
    if size <= 0:
        raise ValueError('The file is empty.')
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f'File exceeds the {MAX_UPLOAD_MB} MB limit.')


def store_upload(contents: bytes, filename: str) -> str:
    """Persist bytes via the configured Storage provider; return the storage path."""
    unique = f'policy_{uuid.uuid4()}_{os.path.basename(filename)}'
    _, path = Storage.upload_file(io.BytesIO(contents), unique, {'OpenWebUI-Policy': 'document'})
    return path


def read_stored(storage_path: str) -> bytes:
    """Read the stored binary back (used by downloads and copy)."""
    with open(Storage.get_file(storage_path), 'rb') as f:
        return f.read()


def copy_stored(storage_path: str, filename: str) -> str:
    """Duplicate a stored binary to a fresh path (gives the Library its own copy)."""
    return store_upload(read_stored(storage_path), filename)


def delete_stored(storage_path: Optional[str]) -> None:
    """Best-effort delete of a stored binary; never raises."""
    if not storage_path:
        return
    try:
        Storage.delete_file(storage_path)
    except Exception:
        pass


async def extract_text(filename: str, content_type: Optional[str], storage_path: str) -> str:
    """Extract plain text from a stored document using the app's default Loader.

    The default loaders cover pdf/docx/md/txt with no external services, so this
    needs no request/config. Raises ValueError if no text could be extracted.
    """
    from open_webui.retrieval.loaders.main import Loader

    local_path = Storage.get_file(storage_path)
    documents = await Loader().aload(filename, content_type or '', local_path)
    text = '\n\n'.join((d.page_content or '') for d in documents).strip()
    if not text:
        raise ValueError('Could not extract any text from this document.')
    return text
