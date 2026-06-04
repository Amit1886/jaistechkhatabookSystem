# khataapp/utils/permissions.py
"""
Compatibility wrapper for feature gating.

Historically this module implemented its own (incorrect) plan-feature check which could
diverge from the billing subscription/feature registry system. Keep a stable import
path for legacy callers but delegate to the canonical implementation.
"""

from billing.services import user_has_feature  # re-export

__all__ = ["user_has_feature"]
