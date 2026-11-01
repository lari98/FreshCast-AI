"""Deployment configuration, read from CDK context (never hard-coded secrets)."""

from __future__ import annotations

from dataclasses import dataclass

# Data stays in the EU by default. Changing region is an explicit, reviewed act.
ALLOWED_REGIONS = frozenset({"eu-central-1", "eu-central-2", "eu-west-1"})


@dataclass(frozen=True, slots=True)
class DeployConfig:
    """Environment-specific settings."""

    env_name: str = "dev"  # dev | prod
    region: str = "eu-central-1"  # Frankfurt
    alert_email: str | None = None
    monthly_budget_usd: float = 50.0

    def __post_init__(self) -> None:
        """Reject unsafe or unsupported settings."""
        if self.env_name not in {"dev", "prod"}:
            raise ValueError("env_name must be 'dev' or 'prod'")
        if self.region not in ALLOWED_REGIONS:
            raise ValueError(f"region must be one of {sorted(ALLOWED_REGIONS)}")
        if self.monthly_budget_usd <= 0:
            raise ValueError("monthly_budget_usd must be positive")

    @property
    def is_prod(self) -> bool:
        """Return True for production (retain data, enable Multi-AZ)."""
        return self.env_name == "prod"
