"""Compatibility shim for older deployments that still import clarification_agent.

The current codebase uses ClarificationSession in clarification_engine.py, but some
older runtime paths still import ClarificationAgent from this module. Keep the
legacy name available by delegating to the current implementation.
"""

from kaanoon_test.system_adapters.clarification_engine import ClarificationSession


class ClarificationAgent(ClarificationSession):
    """Backward-compatible alias for ClarificationSession."""


__all__ = ["ClarificationAgent", "ClarificationSession"]