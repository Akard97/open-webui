import io

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
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
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
