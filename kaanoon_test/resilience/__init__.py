"""Operational resilience helpers for the LAW-GPT API server.

This package is deliberately dependency-free (stdlib + fastapi/starlette only)
so that a failure here can never take the app down at import time.  The server
imports it inside a try/except and degrades to "no guard" if it is unavailable.

See ``guards.py`` for the concurrency guard and the wall-clock query deadline.
"""