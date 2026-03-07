"""Tests for PPOPolicy (with mocked SB3) and PolicyManager lifecycle.

Covers reinforce_spec/_internal/_policy.py — the biggest uncovered module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from reinforce_spec._exceptions import PolicyNotFoundError, PolicyTrainingError
from reinforce_spec._internal._config import RLConfig
from reinforce_spec._internal._policy import PolicyManager
from reinforce_spec.types import PolicyStage

# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_sb3_module() -> MagicMock:
    """Return a mock stable_baselines3 module with a mock PPO class."""
    mock_ppo_cls = MagicMock()
    mock_model_instance = MagicMock()
    mock_ppo_cls.return_value = mock_model_instance

    # predict returns (action_array, states)
    mock_model_instance.predict.return_value = (np.array(0), None)

    # policy.obs_to_tensor returns (tensor,)
    mock_obs_tensor = MagicMock()
    mock_model_instance.policy.obs_to_tensor.return_value = (mock_obs_tensor,)

    # get_distribution returns distribution with probs
    mock_dist = MagicMock()
    mock_dist.distribution.probs.detach.return_value.cpu.return_value.numpy.return_value.flatten.return_value = np.array(
        [0.6, 0.3, 0.1]
    )
    mock_model_instance.policy.get_distribution.return_value = mock_dist

    # learn returns None
    mock_model_instance.learn.return_value = None

    # save returns None
    mock_model_instance.save.return_value = None

    # PPO.load class method
    mock_ppo_cls.load.return_value = mock_model_instance

    mock_sb3 = MagicMock()
    mock_sb3.PPO = mock_ppo_cls
    return mock_sb3


def _create_ppo_policy(config: RLConfig | None = None):
    """Create a PPOPolicy with mocked SB3."""
    from reinforce_spec._internal._policy import PPOPolicy

    mock_sb3 = _mock_sb3_module()

    with (
        patch("reinforce_spec._internal._policy.require_dependency"),
        patch.dict("sys.modules", {"stable_baselines3": mock_sb3}),
    ):
        mock_env = MagicMock()
        policy = PPOPolicy(config=config or RLConfig(), env=mock_env)

    return policy, mock_sb3


# ── PPOPolicy Tests ───────────────────────────────────────────────────────────


class TestPPOPolicy:
    """Tests for PPOPolicy with mocked SB3."""

    def test_init_creates_model(self) -> None:
        policy, mock_sb3 = _create_ppo_policy()
        mock_sb3.PPO.assert_called_once()
        assert policy.train_steps == 0

    def test_train_steps_property(self) -> None:
        policy, _ = _create_ppo_policy()
        assert policy.train_steps == 0

    def test_predict_deterministic(self) -> None:
        policy, _ = _create_ppo_policy()
        action, confidence = policy.predict(np.zeros(10), deterministic=True)
        assert action == 0
        assert confidence == pytest.approx(0.6)

    def test_predict_action_out_of_range(self) -> None:
        policy, mock_sb3 = _create_ppo_policy()
        # Model returns action 5, but probs array has only 3 elements
        policy._model.predict.return_value = (np.array(5), None)
        action, confidence = policy.predict(np.zeros(10))
        assert action == 5
        assert confidence == 0.0

    def test_get_action_probabilities(self) -> None:
        policy, _ = _create_ppo_policy()
        probs = policy.get_action_probabilities(np.zeros(10))
        assert len(probs) == 3
        assert probs[0] == pytest.approx(0.6)

    def test_train_on_batch_empty(self) -> None:
        policy, _ = _create_ppo_policy()
        result = policy.train_on_batch([])
        assert result == {"loss": 0.0, "n_transitions": 0}

    def test_train_on_batch_success(self) -> None:
        policy, _ = _create_ppo_policy()
        from reinforce_spec._internal._replay_buffer import Transition

        transitions = [
            Transition(
                observation=np.zeros(10),
                action=0,
                reward=1.0,
                next_observation=np.zeros(10),
                done=False,
            )
            for _ in range(5)
        ]
        result = policy.train_on_batch(transitions, total_timesteps=100)
        assert result["n_transitions"] == 5
        assert result["total_steps"] == 100
        assert policy.train_steps == 100

    def test_train_on_batch_accumulates_steps(self) -> None:
        policy, _ = _create_ppo_policy()
        from reinforce_spec._internal._replay_buffer import Transition

        t = Transition(
            observation=np.zeros(10),
            action=0,
            reward=1.0,
            next_observation=np.zeros(10),
            done=False,
        )
        policy.train_on_batch([t], total_timesteps=50)
        policy.train_on_batch([t], total_timesteps=50)
        assert policy.train_steps == 100

    def test_train_on_batch_failure_raises(self) -> None:
        policy, _ = _create_ppo_policy()
        policy._model.learn.side_effect = RuntimeError("boom")
        from reinforce_spec._internal._replay_buffer import Transition

        t = Transition(
            observation=np.zeros(10),
            action=0,
            reward=1.0,
            next_observation=np.zeros(10),
            done=False,
        )
        with pytest.raises(PolicyTrainingError, match="PPO training failed"):
            policy.train_on_batch([t], total_timesteps=10)

    def test_save(self, tmp_path: Path) -> None:
        policy, _ = _create_ppo_policy()
        result = policy.save(tmp_path / "model")
        assert result == tmp_path / "model"
        policy._model.save.assert_called_once()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        policy, _ = _create_ppo_policy()
        deep = tmp_path / "a" / "b" / "c" / "model"
        policy.save(deep)
        assert deep.parent.exists()

    def test_load(self, tmp_path: Path) -> None:
        policy, mock_sb3 = _create_ppo_policy()
        model_path = tmp_path / "model.zip"
        model_path.touch()

        with (
            patch("reinforce_spec._internal._policy.require_dependency"),
            patch.dict("sys.modules", {"stable_baselines3": mock_sb3}),
        ):
            policy.load(model_path)

        mock_sb3.PPO.load.assert_called_once()

    def test_train_on_batch_uses_config_batch_size(self) -> None:
        config = RLConfig()
        policy, _ = _create_ppo_policy(config=config)
        from reinforce_spec._internal._replay_buffer import Transition

        transitions = [
            Transition(
                observation=np.zeros(10),
                action=0,
                reward=1.0,
                next_observation=np.zeros(10),
                done=False,
            )
        ]
        # When total_timesteps is None, uses max(len(transitions), ppo_batch_size)
        result = policy.train_on_batch(transitions)
        expected_steps = max(1, config.ppo_batch_size)
        assert result["total_steps"] == expected_steps


# ── PolicyManager Tests ───────────────────────────────────────────────────────


class TestPolicyManagerLifecycle:
    """Tests for PolicyManager full lifecycle."""

    @pytest.fixture()
    def manager(self, tmp_path: Path) -> PolicyManager:
        """Create a PolicyManager with a temp storage dir."""
        with patch("reinforce_spec._internal._policy.PPOPolicy"):
            return PolicyManager(storage_dir=tmp_path)

    def test_init_creates_storage_dir(self, tmp_path: Path) -> None:
        storage = tmp_path / "policies"
        with patch("reinforce_spec._internal._policy.PPOPolicy"):
            PolicyManager(storage_dir=storage)
        assert storage.exists()

    def test_empty_registry(self, manager: PolicyManager) -> None:
        assert manager.list_policies() == []
        assert manager.active_policy is None

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_create_policy(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"fake model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        policy, meta = mgr.create_policy()

        assert meta.policy_id == "v001"
        assert meta.version == 1
        assert meta.stage == PolicyStage.CANDIDATE
        assert meta.created_at is not None
        assert meta.parent_id is None
        assert policy is mock_policy

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_create_policy_with_parent(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        mock_policy.save.return_value = tmp_path / "v001" / "model.zip"
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy(parent_id="v000")
        assert meta.parent_id == "v000"

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_promote_candidate_to_shadow(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        mock_policy.save.return_value = tmp_path / "v001" / "model.zip"
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy()
        updated = mgr.promote(meta.policy_id)

        assert updated.stage == PolicyStage.SHADOW
        assert updated.promoted_at is not None

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_full_promotion_pipeline(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy()

        # candidate → shadow → canary → production
        meta = mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.SHADOW

        meta = mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.CANARY

        meta = mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.PRODUCTION

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_promote_already_at_production(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy()
        for _ in range(3):
            meta = mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.PRODUCTION

        # Promote again — should stay at PRODUCTION
        meta = mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.PRODUCTION

    def test_promote_unknown_policy(self, manager: PolicyManager) -> None:
        with pytest.raises(PolicyNotFoundError, match="not found"):
            manager.promote("nonexistent")

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_rollback(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)

        # Create first policy (v001) and promote to production
        _, meta1 = mgr.create_policy()
        for _ in range(3):
            mgr.promote(meta1.policy_id)

        # Create second policy (v002) and promote to production
        model_path2 = tmp_path / "v002" / "model.zip"
        model_path2.parent.mkdir(parents=True, exist_ok=True)
        model_path2.write_bytes(b"model data 2")
        mock_policy.save.return_value = model_path2
        _, meta2 = mgr.create_policy()
        for _ in range(3):
            mgr.promote(meta2.policy_id)

        # v001 should now be archived
        policies = mgr.list_policies()
        v001 = next(p for p in policies if p.policy_id == "v001")
        assert v001.stage == PolicyStage.ARCHIVED

        # Rollback to v001
        restored = mgr.rollback("v001")
        assert restored.stage == PolicyStage.PRODUCTION

    def test_rollback_unknown_policy(self, manager: PolicyManager) -> None:
        with pytest.raises(PolicyNotFoundError, match="not found"):
            manager.rollback("nonexistent")

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_get_production_policy(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy()
        for _ in range(3):
            mgr.promote(meta.policy_id)

        prod = mgr.get_production_policy()
        assert prod is not None

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_get_production_policy_none(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mgr = PolicyManager(storage_dir=tmp_path)
        assert mgr.get_production_policy() is None

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_list_policies_by_stage(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        mock_policy.save.return_value = tmp_path / "model.zip"
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        mgr.create_policy()
        mgr.create_policy()

        all_policies = mgr.list_policies()
        assert len(all_policies) == 2

        candidates = mgr.list_policies(stage=PolicyStage.CANDIDATE)
        assert len(candidates) == 2

        shadows = mgr.list_policies(stage=PolicyStage.SHADOW)
        assert len(shadows) == 0

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_save_checkpoint(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 42
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        policy, meta = mgr.create_policy()

        mgr.save_checkpoint(meta.policy_id, policy)
        updated = mgr._registry[meta.policy_id]
        assert updated.train_steps == 42
        assert updated.checksum != ""

    def test_save_checkpoint_unknown(self, manager: PolicyManager) -> None:
        with pytest.raises(PolicyNotFoundError):
            manager.save_checkpoint("nonexistent", MagicMock())

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_load_registry_from_disk(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        mock_policy.save.return_value = tmp_path / "v001" / "model.zip"
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr1 = PolicyManager(storage_dir=tmp_path)
        mgr1.create_policy()
        assert len(mgr1.list_policies()) == 1

        # Create new manager from same dir — should load registry
        mgr2 = PolicyManager(storage_dir=tmp_path)
        assert len(mgr2.list_policies()) == 1

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_archive_current_production(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        _, meta = mgr.create_policy()
        for _ in range(3):
            mgr.promote(meta.policy_id)
        assert meta.stage == PolicyStage.PRODUCTION

        mgr._archive_current_production()
        assert meta.stage == PolicyStage.ARCHIVED
        assert meta.archived_at is not None

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_update_production_link_symlink(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        """Production link is a symlink when supported."""
        mock_policy = MagicMock()
        model_path = tmp_path / "v001" / "model.zip"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"model data")
        mock_policy.save.return_value = model_path
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        mgr._update_production_link("v001")

        link = tmp_path / "production"
        assert link.exists()

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_update_production_link_fallback_copy(self, MockPPO: MagicMock, tmp_path: Path) -> None:
        """Falls back to copy when symlinks are not supported."""
        mock_policy = MagicMock()
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)

        # Create the target dir
        target = tmp_path / "v001"
        target.mkdir()
        (target / "model.zip").write_bytes(b"model data")

        # Force symlink to fail
        with patch.object(Path, "symlink_to", side_effect=OSError("not supported")):
            mgr._update_production_link("v001")

        link = tmp_path / "production"
        assert link.exists()
        assert (link / "model.zip").exists()

    def test_compute_checksum_existing_file(self, tmp_path: Path) -> None:
        f = tmp_path / "model.zip"
        f.write_bytes(b"test data")

        checksum = PolicyManager._compute_checksum(f)
        assert len(checksum) == 16
        # SHA-256 of "test data" truncated to 16
        expected = hashlib.sha256(b"test data").hexdigest()[:16]
        assert checksum == expected

    def test_compute_checksum_zip_suffix(self, tmp_path: Path) -> None:
        """When path doesn't exist, tries .zip suffix."""
        f = tmp_path / "model"
        # Create model.zip
        (tmp_path / "model.zip").write_bytes(b"zip data")

        checksum = PolicyManager._compute_checksum(f)
        assert len(checksum) == 16

    def test_compute_checksum_missing(self, tmp_path: Path) -> None:
        checksum = PolicyManager._compute_checksum(tmp_path / "nonexistent")
        assert checksum == ""

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_update_production_link_replaces_existing(
        self, MockPPO: MagicMock, tmp_path: Path
    ) -> None:
        MockPPO.return_value = MagicMock()
        mgr = PolicyManager(storage_dir=tmp_path)

        # Create two target dirs
        (tmp_path / "v001").mkdir()
        (tmp_path / "v001" / "model.zip").write_bytes(b"v1")
        (tmp_path / "v002").mkdir()
        (tmp_path / "v002" / "model.zip").write_bytes(b"v2")

        mgr._update_production_link("v001")
        link = tmp_path / "production"
        assert link.exists()

        # Replace with v002
        mgr._update_production_link("v002")
        assert link.exists()

    @patch("reinforce_spec._internal._policy.PPOPolicy")
    def test_list_policies_sorted_by_version_descending(
        self,
        MockPPO: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_policy = MagicMock()
        mock_policy.save.return_value = tmp_path / "model.zip"
        mock_policy.train_steps = 0
        MockPPO.return_value = mock_policy

        mgr = PolicyManager(storage_dir=tmp_path)
        mgr.create_policy()
        mgr.create_policy()
        mgr.create_policy()

        policies = mgr.list_policies()
        versions = [p.version for p in policies]
        assert versions == [3, 2, 1]
