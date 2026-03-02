"""Unit tests for customer-type weight presets."""

from __future__ import annotations

from reinforce_spec.scoring.presets import get_preset, list_presets


class TestPresets:
    """Test customer-type weight presets."""

    def test_all_presets_exist(self) -> None:
        presets = list_presets()
        assert "default" in presets
        assert "bank" in presets
        assert "si" in presets
        assert "bpo" in presets
        assert "saas" in presets

    def test_bank_preset_emphasizes_compliance(self) -> None:
        bank = get_preset("bank")
        default = get_preset("default")
        assert bank.compliance_regulatory >= default.compliance_regulatory

    def test_saas_preset_emphasizes_scalability(self) -> None:
        saas = get_preset("saas")
        default = get_preset("default")
        assert saas.scalability_performance >= default.scalability_performance

    def test_all_presets_sum_to_one(self) -> None:
        for name in list_presets():
            preset = get_preset(name)
            total = sum(preset.as_dict().values())
            assert abs(total - 1.0) < 0.01, f"Preset {name} sums to {total}"

    def test_unknown_preset_returns_default(self) -> None:
        preset = get_preset("unknown")
        default = get_preset("default")
        assert preset.compliance_regulatory == default.compliance_regulatory
