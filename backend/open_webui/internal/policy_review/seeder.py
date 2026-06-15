import json
import logging
from pathlib import Path

from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
)

log = logging.getLogger(__name__)

_SEED_FILE = Path(__file__).parent / 'seed_data.json'


async def seed_policy_review_data() -> None:
    """Idempotently seed the canonical checklist, demo library, and demo reviews.

    Runs only when no checklist version exists yet (first run).
    """
    existing = await PolicyChecklistVersions.list_versions()
    if existing:
        return

    if not _SEED_FILE.exists():
        log.warning('Policy Review seed_data.json missing; skipping seed.')
        return

    payload = json.loads(_SEED_FILE.read_text(encoding='utf-8'))
    active_raw = payload['activeVersion']

    # 1) Active checklist version. The frontend stores themes/sections/standards/
    #    verdictBands/changeSummary; lift them into `data`.
    data = {
        'changeSummary': active_raw.get('changeSummary', ''),
        'themes': active_raw.get('themes', []),
        'sections': active_raw.get('sections', []),
        'verdictBands': active_raw.get('verdictBands', {'approved': 85, 'conditional': 70}),
        'standards': active_raw.get('standards', []),
    }
    active = await PolicyChecklistVersions.insert_version(
        label=active_raw.get('label', 'v2.0'),
        status='active',
        data=data,
        published_by_id=None,
        published_by_name=active_raw.get('publishedBy') or 'Organizational Excellence',
    )

    # 2) Library canon.
    for entry in payload.get('library', []):
        await PolicyLibrary.upsert(code=entry['code'], data=entry, source_review_id=None)

    # 3) Demo reviews (fictional owners → created_by_id None).
    for r in payload.get('reviews', []):
        await PolicyReviews.insert_review(
            created_by_id=None,
            created_by_name=r.get('createdBy', 'Unknown'),
            policy_meta=r.get('policyMeta', {}),
            active_version=active,
            results=r.get('results', {}),
            status=r.get('status', 'draft'),
            approval=r.get('approval'),
            strengths=r.get('strengths', []),
        )

    log.info('Policy Review seed data loaded.')
