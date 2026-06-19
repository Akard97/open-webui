import os
import tempfile

import pytest

from open_webui.utils.policy_review import documents as docs


def test_validate_upload_accepts_allowed_types():
    docs.validate_upload('policy.pdf', 1000)
    docs.validate_upload('policy.DOCX', 1000)  # case-insensitive
    docs.validate_upload('notes.md', 1000)
    docs.validate_upload('plain.txt', 1000)


def test_validate_upload_rejects_unknown_type():
    with pytest.raises(ValueError):
        docs.validate_upload('image.png', 1000)


def test_validate_upload_rejects_empty():
    with pytest.raises(ValueError):
        docs.validate_upload('policy.pdf', 0)


def test_validate_upload_rejects_oversize():
    with pytest.raises(ValueError):
        docs.validate_upload('policy.pdf', docs.MAX_UPLOAD_BYTES + 1)


@pytest.mark.asyncio
async def test_extract_text_reads_txt(tmp_path, monkeypatch):
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.txt'
    f.write_text('Hello policy world.', encoding='utf-8')
    text = await docs.extract_text('doc.txt', 'text/plain', str(f))
    assert 'Hello policy world.' in text


@pytest.mark.asyncio
async def test_extract_text_reads_md(tmp_path, monkeypatch):
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.md'
    f.write_text('# Title\n\nBody paragraph.', encoding='utf-8')
    text = await docs.extract_text('doc.md', 'text/markdown', str(f))
    assert 'Body paragraph.' in text


@pytest.mark.asyncio
async def test_extract_text_reads_docx(tmp_path, monkeypatch):
    pytest.importorskip('docx')        # python-docx generates the fixture
    pytest.importorskip('docx2txt')    # docx2txt is what Docx2txtLoader uses to read it
    from docx import Document as Docx

    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.docx'
    d = Docx()
    d.add_paragraph('Confidentiality clause text.')
    d.save(str(f))
    text = await docs.extract_text(
        'doc.docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        str(f),
    )
    assert 'Confidentiality clause text.' in text


@pytest.mark.asyncio
async def test_extract_text_empty_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'empty.txt'
    f.write_text('   \n  ', encoding='utf-8')  # whitespace only
    with pytest.raises(ValueError):
        await docs.extract_text('empty.txt', 'text/plain', str(f))


def test_store_get_delete_roundtrip_local(tmp_path, monkeypatch):
    import open_webui.storage.provider as provider
    monkeypatch.setattr(provider, 'UPLOAD_DIR', str(tmp_path))

    path = docs.store_upload(b'binary-bytes', 'orig.pdf')
    assert os.path.isfile(docs.Storage.get_file(path))
    assert docs.read_stored(path) == b'binary-bytes'

    copy_path = docs.copy_stored(path, 'orig.pdf')
    assert copy_path != path
    assert docs.read_stored(copy_path) == b'binary-bytes'

    docs.delete_stored(path)
    assert not os.path.isfile(os.path.join(str(tmp_path), os.path.basename(path)))
