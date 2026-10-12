"""Initial migration baseline; application tables are introduced by later vertical slices.

Revision ID: 0001_phase2_baseline
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_phase2_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the database schema baseline without inventing business tables."""


def downgrade() -> None:
    """The initial baseline has no schema objects to remove."""
