"""Regression: an image_url that names a file id must respect ownership.

CVE-2026-54009 (upstream fix in 0.9.6): /api/chat/completions treats an
image_url that is not a data:/http: URL as a file id and reads it. Without an
ownership check any authenticated user can name a victim's file id and have
the vision model read the contents back to them.
"""

import types

import pytest

from open_webui.utils import files as files_utils

VICTIM = types.SimpleNamespace(id='victim', role='user')
ATTACKER = types.SimpleNamespace(id='attacker', role='user')
ADMIN = types.SimpleNamespace(id='root', role='admin')


@pytest.fixture
def victim_file(tmp_path, monkeypatch):
    path = tmp_path / 'secret.png'
    path.write_bytes(b'\x89PNG\r\n\x1a\nsecret')
    row = types.SimpleNamespace(
        id='f1', user_id='victim', path=str(path), filename='secret.png',
        meta={'content_type': 'image/png'})

    class Files:
        @staticmethod
        async def get_file_by_id(file_id, db=None):
            return row if file_id == 'f1' else None

    class Storage:
        @staticmethod
        def get_file(p):
            return p

    async def denied(file_id, access_type, user, db=None):
        return False

    monkeypatch.setattr(files_utils, 'Files', Files)
    monkeypatch.setattr(files_utils, 'Storage', Storage)
    monkeypatch.setattr(files_utils, 'has_access_to_file', denied)
    return row


@pytest.mark.asyncio
async def test_another_users_file_id_is_refused(victim_file):
    assert await files_utils.get_image_base64_from_file_id('f1', user=ATTACKER) is None
    # …including through the image_url path the chat payload actually uses.
    assert await files_utils.get_image_base64_from_url('f1', user=ATTACKER) is None


@pytest.mark.asyncio
async def test_file_id_without_a_user_is_refused(victim_file):
    assert await files_utils.get_image_base64_from_file_id('f1') is None
    assert await files_utils.get_image_base64_from_url('f1') is None


@pytest.mark.asyncio
async def test_owner_and_admin_still_get_the_image(victim_file):
    for user in (VICTIM, ADMIN):
        out = await files_utils.get_image_base64_from_url('f1', user=user)
        assert out.startswith('data:image/png;base64,'), user


@pytest.mark.asyncio
async def test_explicit_read_grant_is_honoured(victim_file, monkeypatch):
    async def granted(file_id, access_type, user, db=None):
        return access_type == 'read' and user.id == 'colleague'

    monkeypatch.setattr(files_utils, 'has_access_to_file', granted)
    colleague = types.SimpleNamespace(id='colleague', role='user')
    out = await files_utils.get_image_base64_from_file_id('f1', user=colleague)
    assert out.startswith('data:image/png;base64,')


@pytest.mark.asyncio
async def test_payload_conversion_drops_the_unowned_image(victim_file):
    from open_webui.utils.middleware import convert_url_images_to_base64

    form_data = {'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'what does this say?'},
        {'type': 'image_url', 'image_url': {'url': 'f1'}}]}]}
    out = await convert_url_images_to_base64(form_data, user=ATTACKER)
    urls = [p['image_url']['url'] for p in out['messages'][0]['content']
            if p['type'] == 'image_url']
    assert urls == ['f1']          # left as the opaque id, never inlined
    assert not any(u.startswith('data:') for u in urls)
