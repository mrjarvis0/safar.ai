"""Safar UI layer — premium dark theme + data-visualisation helpers.

Presentation only. Nothing here touches the agent pipeline; app.py imports
`theme` (CSS + HTML components) and `charts` (Altair builders) to render the
data the orchestrator produces.
"""
from . import theme, charts  # noqa: F401
