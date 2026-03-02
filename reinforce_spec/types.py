"""Public type definitions for reinforce-spec.

These types form the public API contract. Internal types live in _internal/.

The framework accepts user-provided specifications in any format (text, JSON,
YAML, Markdown, etc.), scores them against 12 enterprise-readiness dimensions,
and uses PPO reinforcement learning to select the best candidate.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


class SpecFormat(str, enum.Enum):
    """Auto-detected or user-specified format of a specification."""

    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"
    OTHER = "other"


class SelectionMethod(str, enum.Enum):
    """How the best spec is selected."""

    HYBRID = "hybrid"  # Blended RL + scoring
    SCORING_ONLY = "scoring_only"  # Pure composite-score ranking
    RL_ONLY = "rl_only"  # Pure PPO policy selection


class CustomerType(str, enum.Enum):
    """Customer type presets for weight configuration."""

    BANK = "bank"
    SI = "si"  # Systems Integrator
    BPO = "bpo"  # Business Process Outsourcing
    SAAS = "saas"
    DEFAULT = "default"


class PolicyStage(str, enum.Enum):
    """Policy lifecycle stages."""

    CANDIDATE = "candidate"
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class DegradationLevel(str, enum.Enum):
    """Graceful degradation levels for the API."""

    L0_FULL = "L0_full"  # Full pipeline: multi-judge + RL
    L1_REDUCED = "L1_reduced"  # Reduced: single judge + RL
    L2_FALLBACK = "L2_fallback"  # Scoring only (skip RL)
    L3_EMERGENCY = "L3_emergency"  # Minimal scoring, single candidate


# ── Format Detection ─────────────────────────────────────────────────────────

# Pre-compiled patterns for format sniffing
_JSON_PATTERN = re.compile(r"^\s*[\[{]")
_YAML_FRONT_MATTER = re.compile(r"^---\s*$", re.MULTILINE)
_YAML_KEY_VALUE = re.compile(r"^[a-zA-Z_][\w]*\s*:", re.MULTILINE)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_MARKDOWN_FENCED = re.compile(r"^```", re.MULTILINE)


def detect_format(content: str) -> SpecFormat:
    """Sniff the format of specification content.

    Heuristic order:
      1. Leading ``{`` or ``[`` → JSON
      2. YAML front-matter (``---``) or multiple key-colon lines → YAML
      3. Markdown headings (``#``) or fenced code blocks → MARKDOWN
      4. Fallback → TEXT

    Parameters
    ----------
    content : str
        Raw specification content string.

    Returns
    -------
    SpecFormat
        Detected content format.

    """
    stripped = content.strip()
    if not stripped:
        return SpecFormat.TEXT

    # JSON: starts with { or [
    if _JSON_PATTERN.match(stripped):
        return SpecFormat.JSON

    # YAML: has front-matter or multiple key: value lines
    if _YAML_FRONT_MATTER.search(stripped):
        return SpecFormat.YAML
    yaml_key_matches = _YAML_KEY_VALUE.findall(stripped[:2000])
    if len(yaml_key_matches) >= 3:
        # Could be YAML — but also check if it looks more like Markdown
        if not _MARKDOWN_HEADING.search(stripped[:500]):
            return SpecFormat.YAML

    # Markdown: has headings or fenced code blocks
    if _MARKDOWN_HEADING.search(stripped[:1000]):
        return SpecFormat.MARKDOWN
    if _MARKDOWN_FENCED.search(stripped[:1000]):
        return SpecFormat.MARKDOWN

    return SpecFormat.TEXT


# ── Scoring Types ─────────────────────────────────────────────────────────────


class DimensionScore(BaseModel):
    """Score for a single enterprise-readiness dimension."""

    dimension: str
    score: float = Field(ge=1.0, le=5.0, description="Score on 1-5 scale")
    justification: str = Field(
        default="", description="2-3 sentence justification from the judge"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Judge confidence in this score"
    )

    model_config = {"frozen": True}


class ScoringWeights(BaseModel):
    """Weights for each scoring dimension. Must sum to 1.0."""

    compliance_regulatory: float = Field(default=0.10, ge=0.0, le=1.0)
    identity_access: float = Field(default=0.09, ge=0.0, le=1.0)
    deployment_topology: float = Field(default=0.09, ge=0.0, le=1.0)
    data_governance: float = Field(default=0.08, ge=0.0, le=1.0)
    observability_monitoring: float = Field(default=0.08, ge=0.0, le=1.0)
    incident_workflow: float = Field(default=0.07, ge=0.0, le=1.0)
    security_architecture: float = Field(default=0.10, ge=0.0, le=1.0)
    vendor_model_abstraction: float = Field(default=0.08, ge=0.0, le=1.0)
    scalability_performance: float = Field(default=0.09, ge=0.0, le=1.0)
    finops_cost: float = Field(default=0.07, ge=0.0, le=1.0)
    developer_experience: float = Field(default=0.08, ge=0.0, le=1.0)
    onboarding_production_path: float = Field(default=0.07, ge=0.0, le=1.0)

    def as_dict(self) -> dict[str, float]:
        """Return weights as a dimension-name → weight mapping."""
        return self.model_dump()

    def validate_sum(self) -> bool:
        """Check that weights sum to 1.0 within tolerance."""
        total = sum(self.as_dict().values())
        return abs(total - 1.0) < 1e-6


# ── Candidate & Result Types ─────────────────────────────────────────────────


class CandidateSpec(BaseModel):
    """A user-provided specification candidate with its scores.

    The ``content`` field accepts any textual format (plain text, JSON, YAML,
    Markdown, etc.).  The ``format`` field is auto-detected from the content
    if not explicitly set.  Users may optionally label their spec via
    ``spec_type`` (free-form string, e.g. ``"srs"``, ``"api"``, ``"prd"``).
    """

    index: int = Field(default=0, description="0-based index (auto-assigned if omitted)")
    content: str = Field(min_length=1, description="The full specification text/content")
    format: SpecFormat = Field(
        default=SpecFormat.TEXT,
        description="Content format — auto-detected from content if not set",
    )
    spec_type: str = Field(
        default="",
        description="Optional user label (e.g. 'srs', 'api', 'prd', 'architecture')",
    )
    source_model: str = Field(
        default="",
        description="Optional: model that authored this spec (for bias detection)",
    )
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    composite_score: float = Field(default=0.0, ge=0.0, le=5.0)
    judge_models: list[str] = Field(
        default_factory=list, description="Models used to judge this spec"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _auto_detect_format(self) -> "CandidateSpec":
        """Auto-detect format from content when using the default."""
        if self.format == SpecFormat.TEXT:
            detected = detect_format(self.content)
            if detected != SpecFormat.TEXT:
                object.__setattr__(self, "format", detected)
        return self


class SpecResult(BaseModel):
    """The selected best spec with full context."""

    selected: CandidateSpec
    all_candidates: list[CandidateSpec]
    selection_method: SelectionMethod
    selection_confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    policy_version: str | None = Field(default=None)
    degradation_level: DegradationLevel = Field(default=DegradationLevel.L0_FULL)
    latency_ms: float = Field(ge=0.0)
    request_id: str


# ── Request / Response Types ─────────────────────────────────────────────────


class SelectionRequest(BaseModel):
    """Request to evaluate and select the best spec from user-provided candidates.

    Candidates can be provided in any textual format (plain text, JSON, YAML,
    Markdown, etc.).  The framework auto-detects the format and uses it as a
    feature signal for the RL policy.

    At least 2 candidates are required; 5 or more is recommended.
    """

    candidates: list[CandidateSpec] = Field(
        ...,
        min_length=2,
        description="Specification candidates to evaluate (min 2, recommended ≥ 5)",
    )
    customer_type: CustomerType = Field(default=CustomerType.DEFAULT)
    weight_overrides: ScoringWeights | None = Field(default=None)
    selection_method: SelectionMethod = Field(default=SelectionMethod.HYBRID)
    request_id: str | None = Field(
        default=None, description="Idempotency key (auto-generated if omitted)"
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="Optional description or context for auditing",
    )

    @field_validator("candidates", mode="after")
    @classmethod
    def _assign_indices(cls, candidates: list[CandidateSpec]) -> list[CandidateSpec]:
        """Ensure every candidate has a unique, sequential index."""
        for i, c in enumerate(candidates):
            object.__setattr__(c, "index", i)
        return candidates


class SelectionResponse(BaseModel):
    """Response from spec evaluation and selection."""

    request_id: str
    selected: CandidateSpec
    all_candidates: list[CandidateSpec]
    selection_method: str
    selection_confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    scoring_summary: dict[str, float] = Field(
        default_factory=dict,
        description="Per-dimension average score across all candidates",
    )
    latency_ms: float = Field(ge=0.0)
    timestamp: datetime

    model_config = {"ser_json_timedelta": "float"}


class FeedbackRequest(BaseModel):
    """User feedback on a selection result."""

    request_id: str
    preferred_spec_index: int = Field(ge=0, le=99)
    rating: float | None = Field(default=None, ge=1.0, le=5.0)
    rationale: str | None = Field(default=None, max_length=2000)


class PolicyStatus(BaseModel):
    """Current state of the RL policy."""

    version: str
    stage: PolicyStage
    training_episodes: int
    mean_reward: float
    explore_rate: float
    drift_psi: float | None = Field(default=None)
    last_trained: datetime | None = Field(default=None)
    last_promoted: datetime | None = Field(default=None)
