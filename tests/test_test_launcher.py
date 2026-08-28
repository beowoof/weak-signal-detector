from run_unit_tests import marker_expression


def test_default_test_profile_excludes_live_and_model_calls() -> None:
    assert marker_expression(live=False, with_model=False) == "not live and not model"


def test_live_does_not_implicitly_enable_model_calls() -> None:
    assert marker_expression(live=True, with_model=False) == "not model"
