import io
import os

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


class _FakeStorage:
    store = {}

    @staticmethod
    def upload_file(file_obj, filename, tags):
        data = file_obj.read()
        key = f'wos/{filename}'
        _FakeStorage.store[key] = data
        return data, key

    @staticmethod
    def get_file(key):
        # Return a real temp path with the bytes (download streams from disk).
        import tempfile
        path = tempfile.mktemp()
        with open(path, 'wb') as f:
            f.write(_FakeStorage.store.get(key, b''))
        return path

    @staticmethod
    def delete_file(key):
        _FakeStorage.store.pop(key, None)


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_attachment_upload_list_download_delete(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 200, r.text
        att = r.json()
        assert att['name'] == 'notes.txt' and att['size'] == 11
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/attachments")).json()
        assert [x['id'] for x in listed] == [att['id']]
        dl = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert dl.status_code == 200 and dl.content == b'hello bytes'
        assert (await c.delete(f"/api/v1/workos/attachments/{att['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_attachment_upload_real_local_storage_creates_subdir(monkeypatch, tmp_path):
    # Reproduces the production bug: the router stores attachments under a
    # 'workos/<uuid>_<name>' key, but LocalStorageProvider.upload_file did not
    # create the parent directory, so the real (non-mocked) filesystem write
    # raised FileNotFoundError -> 500. The fake-storage tests above masked it by
    # never touching disk; this one exercises the real local provider.
    from open_webui.storage import provider as sp

    upload_dir = tmp_path / 'uploads'
    upload_dir.mkdir()
    monkeypatch.setattr(sp, 'UPLOAD_DIR', str(upload_dir))
    monkeypatch.setattr(wr, 'Storage', sp.LocalStorageProvider())
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 200, r.text
        # The file must land under the workos/ subdirectory the provider creates.
        workos_dir = upload_dir / 'workos'
        assert workos_dir.is_dir(), 'provider must create the nested storage dir'
        written = list(workos_dir.iterdir())
        assert len(written) == 1 and written[0].read_bytes() == b'hello bytes'


@pytest.mark.asyncio
async def test_attachment_delete_removes_real_local_file(monkeypatch, tmp_path):
    # Deleting an attachment must also remove the file from the upload folder.
    # The real local provider stores under 'workos/<id>_name'; delete_file used to
    # strip the subdirectory (basename) and so left the file orphaned on disk.
    from open_webui.storage import provider as sp

    upload_dir = tmp_path / 'uploads'
    upload_dir.mkdir()
    monkeypatch.setattr(sp, 'UPLOAD_DIR', str(upload_dir))
    monkeypatch.setattr(wr, 'Storage', sp.LocalStorageProvider())
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
        workos_dir = upload_dir / 'workos'
        written = list(workos_dir.iterdir())
        assert len(written) == 1
        on_disk = written[0]
        assert on_disk.exists()

        r = await c.delete(f"/api/v1/workos/attachments/{att['id']}")
        assert r.status_code == 200 and r.json()['deleted'] is True
        assert not on_disk.exists(), 'delete must remove the file from the upload folder'
        assert list(workos_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_attachment_download_denied_for_non_member(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('a.txt', io.BytesIO(b'x'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_attachment_rejects_oversize(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    # Force a tiny cap via monkeypatching the helper directly — more robust than
    # relying on httpx ASGITransport exposing .app (attribute path varies by version).
    monkeypatch.setattr(wr, '_max_attachment_bytes', lambda request: 0)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('big.bin', io.BytesIO(b'0123456789'), 'application/octet-stream')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 400


class _RecordingStorage:
    """Like _FakeStorage but every get_file hands out a fresh temp path (as the
    cloud providers do) and records it so a test can assert whether the download
    endpoint unlinked it afterwards."""

    def __init__(self):
        self.store = {}
        self.handed_out = []

    def upload_file(self, file_obj, filename, tags):
        data = file_obj.read()
        key = f'wos/{filename}'
        self.store[key] = data
        return data, key

    def get_file(self, key):
        import tempfile
        path = tempfile.mktemp()
        with open(path, 'wb') as f:
            f.write(self.store.get(key, b''))
        self.handed_out.append(path)
        return path

    def delete_file(self, key):
        self.store.pop(key, None)


@pytest.mark.asyncio
async def test_download_keeps_local_provider_real_file(monkeypatch):
    # Local provider: get_file returns the real on-disk file — never delete it.
    storage = _RecordingStorage()
    monkeypatch.setattr(wr, 'Storage', storage)
    monkeypatch.setattr(wr, 'STORAGE_PROVIDER', 'local', raising=False)
    monkeypatch.setattr(wr, 'STORAGE_LOCAL_CACHE', False, raising=False)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
        dl = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert dl.status_code == 200 and dl.content == b'hello bytes'
    temp_path = storage.handed_out[-1]
    assert os.path.exists(temp_path), 'local provider real file must not be deleted'
    os.remove(temp_path)


@pytest.mark.asyncio
async def test_download_keeps_cached_copy_when_local_cache_enabled(monkeypatch):
    # Cloud provider but STORAGE_LOCAL_CACHE on: the downloaded copy is kept as a
    # cache (mirrors files.py _cleanup_local_cache), so it must survive download.
    storage = _RecordingStorage()
    monkeypatch.setattr(wr, 'Storage', storage)
    monkeypatch.setattr(wr, 'STORAGE_PROVIDER', 's3', raising=False)
    monkeypatch.setattr(wr, 'STORAGE_LOCAL_CACHE', True, raising=False)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
        dl = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert dl.status_code == 200 and dl.content == b'hello bytes'
    temp_path = storage.handed_out[-1]
    assert os.path.exists(temp_path), 'cached copy must be retained when STORAGE_LOCAL_CACHE is on'
    os.remove(temp_path)


class _SharedPathStorage:
    """Mimics the real S3/GCS/Azure providers: get_file returns a DETERMINISTIC
    path per storage key (derived from the key, under one shared dir) and
    re-materialises the bytes there on every call. Unlike tempfile.mktemp(), two
    downloads of the SAME attachment collide on ONE on-disk path — which is
    exactly why deleting that path after a response is unsafe."""

    def __init__(self):
        import tempfile
        self.store = {}
        self.dir = tempfile.mkdtemp()
        self.handed_out = []

    def upload_file(self, file_obj, filename, tags):
        data = file_obj.read()
        key = f'wos/{filename}'
        self.store[key] = data
        return data, key

    def get_file(self, key):
        path = os.path.join(self.dir, os.path.basename(key))
        with open(path, 'wb') as f:
            f.write(self.store.get(key, b''))
        self.handed_out.append(path)
        return path

    def delete_file(self, key):
        self.store.pop(key, None)


@pytest.mark.asyncio
async def test_download_does_not_delete_shared_provider_path(monkeypatch):
    # Cloud provider, cache disabled. get_file hands back a deterministic path
    # that concurrent downloads of the same attachment share, so the endpoint
    # must NOT delete it after the response (mirrors files.py downloads, which
    # never do). Deleting it would race a concurrent reader of the same file.
    storage = _SharedPathStorage()
    monkeypatch.setattr(wr, 'Storage', storage)
    monkeypatch.setattr(wr, 'STORAGE_PROVIDER', 's3', raising=False)
    monkeypatch.setattr(wr, 'STORAGE_LOCAL_CACHE', False, raising=False)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
        dl = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert dl.status_code == 200 and dl.content == b'hello bytes'
    served = storage.handed_out[-1]
    assert os.path.exists(served), (
        'served provider file must survive the response — the path is shared '
        'across concurrent downloads of the same attachment, so deleting it races'
    )


@pytest.mark.asyncio
async def test_concurrent_downloads_same_attachment_both_succeed(monkeypatch):
    # Two overlapping downloads of the same attachment resolve to the same shared
    # on-disk path. Both must return the correct bytes and neither may be pulled
    # out from under the other by a sibling's cleanup.
    import asyncio as _asyncio

    storage = _SharedPathStorage()
    monkeypatch.setattr(wr, 'Storage', storage)
    monkeypatch.setattr(wr, 'STORAGE_PROVIDER', 's3', raising=False)
    monkeypatch.setattr(wr, 'STORAGE_LOCAL_CACHE', False, raising=False)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
        url = f"/api/v1/workos/attachments/{att['id']}/content"
        r1, r2 = await _asyncio.gather(c.get(url), c.get(url))
    assert r1.status_code == 200 and r1.content == b'hello bytes', r1.text
    assert r2.status_code == 200 and r2.content == b'hello bytes', r2.text
    assert os.path.exists(storage.handed_out[-1]), 'shared provider file must survive concurrent downloads'
