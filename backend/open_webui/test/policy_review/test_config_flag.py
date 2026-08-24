def test_policy_review_flag_defaults_off():
    from open_webui.config import ENABLE_POLICY_REVIEW

    assert ENABLE_POLICY_REVIEW.value is False
