"""
Tool registry for extensible synthesis tool support.

This module provides a plugin-based system for registering and using
different synthesis tools (circt-synth, yosys, abc, etc.) in the test framework.
"""

import os
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass


@dataclass
class ToolConfig:
    """Configuration for a synthesis tool."""

    name: str
    command: str
    default_args: List[str]
    env_var: str  # Environment variable to override the tool path

    def get_command(self) -> str:
        """Get the tool command, checking environment variable first."""
        return os.environ.get(self.env_var, self.command)


class ToolRegistry:
    """Registry for synthesis tools."""

    def __init__(self):
        self._tools: Dict[str, ToolConfig] = {}
        self._converters: Dict[str, Callable] = {}

    def register_tool(self, config: ToolConfig):
        """Register a synthesis tool."""
        self._tools[config.name] = config

    def register_converter(self, name: str, converter: Callable):
        """Register a format converter function."""
        self._converters[name] = converter

    def get_tool(self, name: str) -> Optional[ToolConfig]:
        """Get tool configuration by name."""
        return self._tools.get(name)

    def get_converter(self, name: str) -> Optional[Callable]:
        """Get converter function by name."""
        return self._converters.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tools."""
        return list(self._tools.keys())

    def get_substitutions(self) -> Dict[str, str]:
        """Get lit substitutions for all registered tools."""
        substitutions = {}
        for name, config in self._tools.items():
            cmd = config.get_command()
            if config.default_args:
                cmd = f"{cmd} {' '.join(config.default_args)}"
            substitutions[f"%{name}"] = cmd
        return substitutions


# Global registry instance
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


# Register built-in tools
def register_builtin_tools():
    """Register all built-in synthesis tools."""

    # CIRCT Synth
    _registry.register_tool(
        ToolConfig(
            name="circt-synth",
            command="circt-synth",
            default_args=[],
            env_var="CIRCT_SYNTH",
        )
    )

    # CIRCT Verilog
    _registry.register_tool(
        ToolConfig(
            name="circt-verilog",
            command="circt-verilog",
            default_args=[],
            env_var="CIRCT_VERILOG",
        )
    )

    # CIRCT Translate
    _registry.register_tool(
        ToolConfig(
            name="circt-translate",
            command="circt-translate",
            default_args=[],
            env_var="CIRCT_TRANSLATE",
        )
    )

    # CIRCT LEC
    _registry.register_tool(
        ToolConfig(
            name="circt-lec",
            command="circt-lec",
            default_args=[],
            env_var="CIRCT_LEC",
        )
    )

    # Yosys
    _registry.register_tool(
        ToolConfig(name="yosys", command="yosys", default_args=[], env_var="YOSYS")
    )

    # ABC
    _registry.register_tool(
        ToolConfig(name="abc", command="abc", default_args=[], env_var="ABC")
    )

    # FileCheck
    _registry.register_tool(
        ToolConfig(
            name="FileCheck", command="FileCheck", default_args=[], env_var="FILECHECK"
        )
    )


# Initialize built-in tools
register_builtin_tools()
