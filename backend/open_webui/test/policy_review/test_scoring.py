import json
from pathlib import Path

import pytest

from open_webui.utils.policy_review.scoring import compute_scores

FIXTURES = json.loads((Path(__file__).parent / 'policy_scoring_fixtures.json').read_text())


@pytest.mark.parametrize('case', FIXTURES, ids=[c['name'] for c in FIXTURES])
def test_scoring_fixture(case):
    result = compute_scores(case['definition'], case['results'])
    exp = case['expected']
    assert result['overall'] == exp['overall']
    assert result['gatesPass'] == exp['gatesPass']
    assert result['humanItemsRemain'] == exp['humanItemsRemain']
    assert result['verdict']['key'] == exp['verdictKey']
