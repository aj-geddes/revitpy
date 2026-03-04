"""
Prompt template library for AI interactions.

Manages a set of Jinja2 templates used to construct prompts for
LLM interactions within the MCP server, and exposes them in the
MCP prompt-list format.
"""

from __future__ import annotations

from typing import Any

import jinja2
from loguru import logger

from .exceptions import PromptError

# ---------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------

_BUILTIN_TEMPLATES: dict[str, str] = {
    "element_summary": (
        "Summarize the following Revit element:\n"
        "- ID: {{ element_id }}\n"
        "- Name: {{ name }}\n"
        "- Category: {{ category }}\n"
        "- Parameters:\n"
        "{% for key, value in parameters.items() %}"
        "  - {{ key }}: {{ value }}\n"
        "{% endfor %}"
    ),
    "quantity_takeoff": (
        "Generate a quantity takeoff report for "
        "{{ category }} elements.\n"
        "Group by: {{ group_by | default('type') }}\n"
        "Include the following columns: "
        "{{ columns | default('name, count, area, volume') }}\n"
    ),
    "validation_report": (
        "Model validation report:\n"
        "{% for issue in issues %}"
        "- [{{ issue.severity }}] {{ issue.message }}\n"
        "{% endfor %}"
        "{% if not issues %}"
        "No issues found. Model is valid.\n"
        "{% endif %}"
    ),
    "natural_language_query": (
        "Translate the following natural language request into "
        "a Revit element query:\n"
        "Request: {{ user_query }}\n"
        "Available categories: {{ categories | join(', ') }}\n"
    ),
    "safety_preview": (
        "The following operation will be performed:\n"
        "- Tool: {{ tool_name }}\n"
        "- Category: {{ category }}\n"
        "- Arguments:\n"
        "{% for key, value in arguments.items() %}"
        "  - {{ key }}: {{ value }}\n"
        "{% endfor %}"
        "Safety mode: {{ safety_mode }}\n"
        "Requires confirmation: {{ requires_confirmation }}\n"
    ),
}


class PromptLibrary:
    """Manages and renders Jinja2 prompt templates.

    Built-in templates are registered at construction time.  Additional
    templates can be added at runtime via ``register_template``.
    """

    def __init__(self) -> None:
        self._templates: dict[str, str] = dict(_BUILTIN_TEMPLATES)
        self._env = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            autoescape=False,  # noqa: S701 - plain-text prompts, not HTML
            keep_trailing_newline=True,
        )
        logger.debug(
            "PromptLibrary initialized with {} built-in templates",
            len(self._templates),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, template_name: str, /, **kwargs: Any) -> str:
        """Render a template by name.

        Args:
            template_name: Template name (positional-only to avoid
                collisions with template variables).
            **kwargs: Variables passed to the template.

        Returns:
            The rendered prompt string.

        Raises:
            PromptError: If the template does not exist or rendering
                fails.
        """
        source = self._templates.get(template_name)
        if source is None:
            raise PromptError(
                f"Template '{template_name}' not found",
                template_name=template_name,
            )

        try:
            template = self._env.from_string(source)
            return template.render(**kwargs)
        except jinja2.TemplateError as exc:
            raise PromptError(
                f"Failed to render template '{template_name}': {exc}",
                template_name=template_name,
                cause=exc,
            ) from exc

    def register_template(self, name: str, template: str) -> None:
        """Register or overwrite a template.

        Args:
            name: Template name.
            template: Jinja2 template source string.
        """
        logger.debug("Registering template: {}", name)
        self._templates[name] = template

    def get_template(self, name: str) -> str | None:
        """Return the raw source of a template, or ``None``."""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """Return sorted list of all template names."""
        return sorted(self._templates)

    def to_mcp_prompts_list(self) -> list[dict[str, Any]]:
        """Convert templates to MCP-format prompt definitions."""
        prompts: list[dict[str, Any]] = []
        for name in sorted(self._templates):
            prompts.append(
                {
                    "name": name,
                    "description": f"Prompt template: {name}",
                    "arguments": [],
                }
            )
        return prompts
