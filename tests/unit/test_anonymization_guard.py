import pytest

from anonreq.anonymization_guard import assert_anonymization_required, effective_default_action
from anonreq.exceptions import AnonReqError
from anonreq.proxy.modes import ProxyMode


def test_not_required_never_raises() -> None:
    assert_anonymization_required(required=False, default_action="PASS", mode=ProxyMode.PROXY_ONLY)


def test_required_with_anonymize_and_full_passes() -> None:
    assert_anonymization_required(required=True, default_action="ANONYMIZE", mode=ProxyMode.FULL)


def test_required_with_pass_default_refuses() -> None:
    with pytest.raises(AnonReqError, match="CLASSIFICATION_DEFAULT_ACTION"):
        assert_anonymization_required(required=True, default_action="PASS", mode=ProxyMode.FULL)


def test_required_with_proxy_only_refuses() -> None:
    with pytest.raises(AnonReqError, match="proxy-only"):
        assert_anonymization_required(required=True, default_action="ANONYMIZE", mode=ProxyMode.PROXY_ONLY)


def test_env_override_wins_over_yaml(tmp_path) -> None:
    yaml_file = tmp_path / "c.yaml"
    yaml_file.write_text("default_action: PASS\n")
    assert effective_default_action("anonymize", str(yaml_file)) == "ANONYMIZE"
    assert effective_default_action(None, str(yaml_file)) == "PASS"


def test_shipped_config_is_pass_so_the_guard_matters() -> None:
    assert effective_default_action(None, "config/classification.yaml") == "PASS"
