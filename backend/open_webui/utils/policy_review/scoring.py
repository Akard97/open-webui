"""Authoritative server-side port of src/lib/components/policy-review/lib/scoring.ts.

Per-theme score = compliant / (compliant + non-compliant). `human` and missing/
`pending` items are held aside (not scored, but they block a final verdict).
Gate themes must clear their threshold. Overall = weight-weighted average of theme
scores. Kept identical to the TypeScript implementation (see scoring.parity.test.ts).
"""

import math
from typing import Any


def _js_round(value: float) -> int:
    # Mirror JavaScript Math.round (half rounds up), not Python banker's rounding.
    return math.floor(value + 0.5)


def compute_scores(version: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    themes = version.get('themes', [])
    sections = version.get('sections', [])
    verdict_bands = version.get('verdictBands', {})

    by_theme: dict[str, dict[str, int]] = {}
    for t in themes:
        by_theme[t['id']] = {'total': 0, 'yes': 0, 'no': 0, 'human': 0, 'pending': 0, 'items': 0}

    for sec in sections:
        bucket = by_theme.get(sec['theme'])
        if bucket is None:
            continue
        for item in sec.get('items', []):
            bucket['items'] += 1
            result = (results.get(item['id']) or {}).get('result', 'pending')
            if result == 'compliant':
                bucket['yes'] += 1
                bucket['total'] += 1
            elif result == 'non-compliant':
                bucket['no'] += 1
                bucket['total'] += 1
            elif result == 'human':
                bucket['human'] += 1
            else:
                bucket['pending'] += 1

    theme_rows = []
    for t in themes:
        s = by_theme[t['id']]
        pct = _js_round((s['yes'] / s['total']) * 100) if s['total'] > 0 else 0
        theme_rows.append({**t, **s, 'pct': pct})

    weighted = 0.0
    weight_total = 0.0
    for t in theme_rows:
        if t['total'] > 0:
            weighted += t['pct'] * t['weight']
            weight_total += t['weight']
    overall = _js_round(weighted / weight_total) if weight_total > 0 else 0

    gate_rows = [t for t in theme_rows if t.get('gate')]
    gates_pass = all(t['pct'] >= t['threshold'] for t in gate_rows)
    human_items_remain = any(t['human'] > 0 or t['pending'] > 0 for t in theme_rows)

    approved_band = verdict_bands.get('approved', 85)
    conditional_band = verdict_bands.get('conditional', 70)

    if human_items_remain:
        verdict = {'key': 'draft', 'label': 'Pending review', 'reason': 'Awaiting unresolved items'}
    elif overall >= approved_band and gates_pass:
        verdict = {'key': 'approved', 'label': 'Approved', 'reason': 'Meets all requirements'}
    elif overall >= conditional_band and gates_pass:
        verdict = {'key': 'conditional', 'label': 'Conditionally Approved', 'reason': 'Minimum threshold met — CAP required'}
    else:
        verdict = {
            'key': 'rejected',
            'label': 'Rejected',
            'reason': 'Below minimum overall threshold' if gates_pass else 'Mandatory gate failed',
        }

    return {
        'themeRows': theme_rows,
        'overall': overall,
        'gatesPass': gates_pass,
        'verdict': verdict,
        'humanItemsRemain': human_items_remain,
    }
