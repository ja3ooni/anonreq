"""YAML-backed compliance preset engine."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import structlog
import yaml

from anonreq.compliance.merge import PresetMergeResult, merge_presets
from anonreq.compliance.preset import CompliancePreset
from anonreq.compliance.validation import ComplianceViolation, validate_effective_config

logger = structlog.get_logger("anonreq.compliance.engine")


class PresetEngine:
    """Loads, merges, and validates compliance presets."""

    def __init__(self, presets_dir: str = "config/compliance") -> None:
        self._presets_dir = Path(presets_dir)
        self._presets: dict[str, CompliancePreset] = {}
        self._load_presets()

    def _load_presets(self) -> None:
        if not self._presets_dir.exists():
            logger.warning("compliance.presets_dir_missing", path=str(self._presets_dir))
            return
        for path in sorted(self._presets_dir.glob("*.yaml")):
            try:
                with open(path) as f:
                    preset = CompliancePreset.from_dict(yaml.safe_load(f) or {})
                self._presets[preset.id] = preset
            except Exception as exc:
                logger.warning(
                    "compliance.preset_skipped",
                    path=str(path),
                    error=type(exc).__name__,
                )

    def get_preset(self, preset_id: str) -> CompliancePreset | None:
        return self._presets.get(preset_id)

    def list_presets(self) -> dict[str, CompliancePreset]:
        return dict(sorted(self._presets.items()))

    def merge(
        self,
        active_preset_ids: list[str],
        base_config: dict[str, Any],
        overrides: dict[str, Any] | None = None,
    ) -> PresetMergeResult:
        presets = [
            preset
            for preset_id in active_preset_ids
            if (preset := self.get_preset(preset_id)) is not None
        ]
        return merge_presets(base_config, presets, overrides)

    def validate_startup(
        self,
        active_preset_ids: list[str],
        base_config: dict[str, Any],
        overrides: dict[str, Any] | None = None,
    ) -> list[ComplianceViolation]:
        presets = [
            preset
            for preset_id in active_preset_ids
            if (preset := self.get_preset(preset_id)) is not None
        ]
        effective = self.merge(active_preset_ids, base_config, overrides)
        return validate_effective_config(presets, effective)

    def assert_startup_checks(
        self,
        active_preset_ids: list[str],
        base_config: dict[str, Any],
        overrides: dict[str, Any] | None = None,
    ) -> None:
        violations = self.validate_startup(active_preset_ids, base_config, overrides)
        if not violations:
            return
        for violation in violations:
            print(violation.message, file=sys.stderr)
        sys.exit(1)
