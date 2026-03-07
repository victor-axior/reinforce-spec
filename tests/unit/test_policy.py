"""Unit tests for PPOPolicy, PolicyMetadata, PolicyManager."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from reinforce_spec._internal._policy import PolicyManager, PolicyMetadata
from reinforce_spec.types import PolicyStage

if TYPE_CHECKING:
    from pathlib import Path

# ── PolicyMetadata ───────────────────────────────────────────────────────────


class TestPolicyMetadata:
    """Test the metadata dataclass round-trip."""

    def _make_meta(self, **overrides) -> PolicyMetadata:
        defaults = {
            "policy_id": "v001",
            "version": 1,
            "stage": PolicyStage.CANDIDATE,
            "created_at": datetime(2024, 1, 1, tzinfo=UTC),
            "train_steps": 0,
            "metrics": {},
            "checksum": "abc123",
            "parent_id": None,
        }
        defaults.update(overrides)
        return PolicyMetadata(**defaults)

    def test_to_dict_basic(self) -> None:
        meta = self._make_meta()
        d = meta.to_dict()
        assert d["policy_id"] == "v001"
        assert d["stage"] == "candidate"
        assert d["promoted_at"] is None
        assert d["archived_at"] is None

    def test_round_trip(self) -> None:
        meta = self._make_meta(
            promoted_at=datetime(2024, 2, 1, tzinfo=UTC),
            metrics={"loss": 0.1},
        )
        d = meta.to_dict()
        restored = PolicyMetadata.from_dict(d)
        assert restored.policy_id == meta.policy_id
        assert restored.version == meta.version
        assert restored.stage == meta.stage
        assert restored.promoted_at == meta.promoted_at
        assert restored.metrics == meta.metrics

    def test_from_dict_missing_optional_fields(self) -> None:
        d = {
            "policy_id": "v002",
            "version": 2,
            "stage": "shadow",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        meta = PolicyMetadata.from_dict(d)
        assert meta.train_steps == 0
        assert meta.checksum == ""
        assert meta.parent_id is None


# ── PolicyManager (without SB3 — mock PPOPolicy) ────────────────────────────


class TestPolicyManager:
    """Test PolicyManager lifecycle without real SB3."""

    @pytest.fixture()
    def storage_dir(self, tmp_path: Path) -> Path:
        return tmp_path / "policies"

    def test_init_creates_dir(self, storage_dir: Path) -> None:
        PolicyManager(storage_dir=storage_dir)
        assert storage_dir.exists()

    def test_empty_registry(self, storage_dir: Path) -> None:
        mgr = PolicyManager(storage_dir=storage_dir)
        assert mgr.list_policies() == []
        assert mgr.get_production_policy() is None

    def test_load_registry_from_disk(self, storage_dir: Path) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        registry = {
            "v001": {
                "policy_id": "v001",
                "version": 1,
                "stage": "candidate",
                "created_at": "2024-01-01T00:00:00+00:00",
                "train_steps": 100,
                "metrics": {},
                "checksum": "abc",
            },
        }
        (storage_dir / "registry.json").write_text(json.dumps(registry))
        mgr = PolicyManager(storage_dir=storage_dir)
        assert len(mgr.list_policies()) == 1
        assert mgr.list_policies()[0].policy_id == "v001"

    def test_list_policies_filtered_by_stage(self, storage_dir: Path) -> None:
        storage_dir.mkdir(parents=True, exist_ok=True)
        registry = {
            "v001": {
                "policy_id": "v001",
                "version": 1,
                "stage": "candidate",
                "created_at": "2024-01-01T00:00:00+00:00",
            },
            "v002": {
                "policy_id": "v002",
                "version": 2,
                "stage": "production",
                "created_at": "2024-02-01T00:00:00+00:00",
            },
        }
        (storage_dir / "registry.json").write_text(json.dumps(registry))
        mgr = PolicyManager(storage_dir=storage_dir)

        prods = mgr.list_policies(stage=PolicyStage.PRODUCTION)
        assert len(prods) == 1
        assert prods[0].policy_id == "v002"

    def test_promote_unknown_policy_raises(self, storage_dir: Path) -> None:
        from reinforce_spec._exceptions import PolicyNotFoundError

        mgr = PolicyManager(storage_dir=storage_dir)
        with pytest.raises(PolicyNotFoundError):
            mgr.promote("nonexistent")

    def test_rollback_unknown_policy_raises(self, storage_dir: Path) -> None:
        from reinforce_spec._exceptions import PolicyNotFoundError

        mgr = PolicyManager(storage_dir=storage_dir)
        with pytest.raises(PolicyNotFoundError):
            mgr.rollback("nonexistent")

    def test_save_checkpoint_unknown_raises(self, storage_dir: Path) -> None:
        from reinforce_spec._exceptions import PolicyNotFoundError

        mgr = PolicyManager(storage_dir=storage_dir)
        with pytest.raises(PolicyNotFoundError):
            mgr.save_checkpoint("nonexistent", MagicMock())

    def test_compute_checksum_missing_file(self, storage_dir: Path) -> None:
        result = PolicyManager._compute_checksum(storage_dir / "no_such_file")
        assert result == ""

    def test_promotion_order(self) -> None:
        assert [
            PolicyStage.CANDIDATE,
            PolicyStage.SHADOW,
            PolicyStage.CANARY,
            PolicyStage.PRODUCTION,
        ] == PolicyManager.PROMOTION_ORDER
