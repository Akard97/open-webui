import json
from pathlib import Path

from open_webui.utils.policy_review.scoring import compute_scores

FIXTURES = json.loads((Path(__file__).parent / 'policy_scoring_fixtures.json').read_text())


def test_scoring_fixtures():
    for case in FIXTURES:
        result = compute_scores(case['definition'], case['results'])
        exp = case['expected']
        assert result['overall'] == exp['overall'], case['name']
        assert result['gatesPass'] == exp['gatesPass'], case['name']
        assert result['humanItemsRemain'] == exp['humanItemsRemain'], case['name']
        assert result['verdict']['key'] == exp['verdictKey'], case['name']
