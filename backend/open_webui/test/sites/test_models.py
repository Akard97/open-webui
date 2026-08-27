import pytest

from open_webui.models.access_grants import AccessGrants
from open_webui.models.sites import Sites


@pytest.fixture(autouse=True)
def _monotonic_now(monkeypatch):
    import open_webui.models.sites as sites_model

    counter = iter(range(1_700_000_000_000, 1_700_000_100_000))
    monkeypatch.setattr(sites_model, '_now', lambda: next(counter))


def _files():
    return [{'name': 'index.html', 'size': 120, 'content_type': 'text/html'}]


@pytest.mark.asyncio
async def test_insert_and_get():
    site = await Sites.insert_new_site(
        'u1', name='My Page', slug='my-page', public=False, files=_files(), entry_file='index.html'
    )
    assert site is not None
    assert site.slug == 'my-page'
    assert site.public is False
    assert site.files[0]['name'] == 'index.html'
    assert site.created_at > 10**12  # ms epoch, not seconds

    by_id = await Sites.get_site_by_id(site.id)
    by_slug = await Sites.get_site_by_slug('my-page')
    assert by_id.id == site.id and by_slug.id == site.id


@pytest.mark.asyncio
async def test_duplicate_slug_returns_none():
    a = await Sites.insert_new_site('u1', name='A', slug='taken', public=False, files=_files(), entry_file='index.html')
    b = await Sites.insert_new_site('u2', name='B', slug='taken', public=False, files=_files(), entry_file='index.html')
    assert a is not None
    assert b is None


@pytest.mark.asyncio
async def test_update_and_slug_conflict():
    a = await Sites.insert_new_site('u1', name='A', slug='site-a', public=False, files=_files(), entry_file='index.html')
    b = await Sites.insert_new_site('u1', name='B', slug='site-b', public=False, files=_files(), entry_file='index.html')

    updated = await Sites.update_site_by_id(a.id, {'name': 'A2', 'public': True})
    assert updated.name == 'A2' and updated.public is True
    assert updated.updated_at >= a.updated_at

    conflict = await Sites.update_site_by_id(a.id, {'slug': 'site-b'})
    assert conflict is None
    assert (await Sites.get_site_by_id(a.id)).slug == 'site-a'
    assert b is not None


@pytest.mark.asyncio
async def test_list_and_delete():
    await Sites.insert_new_site('u1', name='A', slug='aaa', public=False, files=_files(), entry_file='index.html')
    s2 = await Sites.insert_new_site('u1', name='B', slug='bbb', public=False, files=_files(), entry_file='index.html')
    await Sites.insert_new_site('u2', name='C', slug='ccc', public=False, files=_files(), entry_file='index.html')

    mine = await Sites.get_sites_by_user_id('u1')
    assert [s.slug for s in mine] == ['bbb', 'aaa']  # newest first
    assert len(await Sites.get_all_sites()) == 3

    assert await Sites.delete_site_by_id(s2.id) is True
    assert await Sites.get_site_by_id(s2.id) is None
    assert await Sites.delete_site_by_id('nope') is False


@pytest.mark.asyncio
async def test_update_site_access_replaces_grants_and_flag_together():
    site = await Sites.insert_new_site(
        'u1', name='A', slug='site-a', public=False, files=_files(), entry_file='index.html'
    )

    updated = await Sites.update_site_access(
        site.id,
        public=True,
        access_grants=[{'principal_type': 'user', 'principal_id': 'u9', 'permission': 'read'}],
    )
    assert updated.public is True
    grants = await AccessGrants.get_grants_by_resource('site', site.id)
    assert [(g.principal_type, g.principal_id, g.permission) for g in grants] == [('user', 'u9', 'read')]

    updated = await Sites.update_site_access(site.id, public=False, access_grants=[])
    assert updated.public is False
    assert await AccessGrants.get_grants_by_resource('site', site.id) == []


@pytest.mark.asyncio
async def test_update_site_access_missing_site_writes_nothing():
    assert (
        await Sites.update_site_access(
            'nope',
            public=True,
            access_grants=[{'principal_type': 'user', 'principal_id': 'u9', 'permission': 'read'}],
        )
        is None
    )
    assert await AccessGrants.get_grants_by_resource('site', 'nope') == []
