from __future__ import annotations

"""
Compatibility wrapper.

The codebase historically had "find_people/find_things" as the two tools.
We now expose two fat tools (intelligent_discovery/deep_profile_analysis) under
`app/tool_library/`, but keep this module path stable for the orchestrator.
"""

from .tool_library.registry import ToolSpec, tool_by_name, tool_schemas

__all__ = ["ToolSpec", "tool_by_name", "tool_schemas"]
