def test_workos_permission_flags_present():
    from open_webui.config import DEFAULT_USER_PERMISSIONS

    features = DEFAULT_USER_PERMISSIONS['features']
    assert 'workos' in features
    assert 'workos_admin' in features
    assert isinstance(features['workos'], bool)
    assert isinstance(features['workos_admin'], bool)


def test_workos_rules_default():
    from open_webui.config import WORKOS_RULES

    assert WORKOS_RULES.value['team_creation'] in ('all_users', 'admins_only')
    assert WORKOS_RULES.value['default_workspace_visibility'] in ('team', 'restricted')
