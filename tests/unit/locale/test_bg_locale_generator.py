"""config/locales/bg-BG.yaml must match scripts/bg_locale/generate.py output."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "bg_locale" / "generate.py"


def test_bg_locale_yaml_is_up_to_date() -> None:
    spec = importlib.util.spec_from_file_location("bg_locale_generate", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0, "run python scripts/bg_locale/generate.py"
