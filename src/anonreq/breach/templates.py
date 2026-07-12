"""Breach notification templates with variable substitution.

Per D-026: Templates are configurable per framework/region with
support for ``{{variable_name}}`` substitution.

Default templates provided for GDPR (EU/UK), DORA (EU), and
other common frameworks.
"""

from __future__ import annotations

import logging
from string import Template
from typing import Any

from anonreq.models.breach import BreachTemplate

logger = logging.getLogger("anonreq.breach.templates")

# ── Default templates ────────────────────────────────────────────────────────
# Keyed by framework, then region, then language.
# Supports {{variable_name}} substitution per D-026.

DEFAULT_TEMPLATES: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "gdpr": {
        "eu": {
            "en": {
                "subject": "GDPR Breach Notification - {{tenant_name}}",
                "body": (
                    "Dear {{recipient_name}},\n\n"
                    "This is a breach notification pursuant to Article 33 "
                    "of the General Data Protection Regulation (GDPR).\n\n"
                    "Breach ID: {{breach_id}}\n"
                    "Date: {{date}}\n"
                    "Description: {{description}}\n\n"
                    "Estimated affected data subjects: {{affected_count}}\n"
                    "Mitigation steps: {{mitigation}}\n\n"
                    "This notification is sent in compliance with GDPR "
                    "Article 33 requirements.\n\n"
                    "Regards,\n"
                    "{{sender_name}}"
                ),
            },
        },
        "uk": {
            "en": {
                "subject": "UK DPA Breach Notification - {{tenant_name}}",
                "body": (
                    "Dear {{recipient_name}},\n\n"
                    "This is a breach notification pursuant to the UK Data "
                    "Protection Act 2018.\n\n"
                    "Breach ID: {{breach_id}}\n"
                    "Date: {{date}}\n"
                    "Description: {{description}}\n\n"
                    "Estimated affected data subjects: {{affected_count}}\n"
                    "Mitigation steps: {{mitigation}}\n\n"
                    "This notification is sent in compliance with UK DPA "
                    "requirements.\n\n"
                    "Regards,\n"
                    "{{sender_name}}"
                ),
            },
        },
    },
    "dora": {
        "eu": {
            "en": {
                "subject": "DORA ICT Incident Notification - {{tenant_name}}",
                "body": (
                    "Dear {{recipient_name}},\n\n"
                    "This is an ICT incident notification pursuant to "
                    "Regulation (EU) 2022/2554 (DORA).\n\n"
                    "Breach ID: {{breach_id}}\n"
                    "Date: {{date}}\n"
                    "Incident description: {{description}}\n"
                    "Classification: {{classification}}\n"
                    "Affected services: {{affected_services}}\n\n"
                    "Estimated impact: {{impact_description}}\n"
                    "Mitigation steps: {{mitigation}}\n\n"
                    "This notification is sent in compliance with DORA "
                    "Article 19 requirements.\n\n"
                    "Regards,\n"
                    "{{sender_name}}"
                ),
            },
        },
    },
}

REQUIRED_VARIABLES = {
    "recipient_name",
    "tenant_name",
    "breach_id",
    "date",
    "description",
    "sender_name",
}
"""Variables that MUST be present in all template renderings."""

OPTIONAL_VARIABLES = {
    "affected_count",
    "mitigation",
    "classification",
    "affected_services",
    "impact_description",
    "contact_email",
}
"""Variables that MAY be present depending on framework."""


class BreachTemplateManager:
    """Manages breach notification templates with variable substitution.

    Loads DEFAULT_TEMPLATES and supports custom template overrides
    stored in the database per framework/region.
    """

    def __init__(self, db: Any = None) -> None:
        """Initialize the template manager.

        Args:
            db: Optional database session for custom template storage.
        """
        self._db = db
        self._custom_templates: dict[str, BreachTemplate] = {}

    def get_template(
        self,
        framework: str,
        region: str,
        language: str = "en",
    ) -> BreachTemplate:
        """Get a breach notification template.

        Checks custom templates first, then falls back to defaults.

        Args:
            framework: Regulatory framework (e.g., ``gdpr``, ``dora``).
            region: Region code (e.g., ``eu``, ``uk``).
            language: Language code (default ``en``).

        Returns:
            A BreachTemplate instance.

        Raises:
            ValueError: If no template found for the given parameters.
        """
        # Check custom templates
        custom_key = f"{framework}:{region}:{language}"
        if custom_key in self._custom_templates:
            return self._custom_templates[custom_key]

        # Check defaults
        try:
            tpl_data = DEFAULT_TEMPLATES[framework][region][language]
            template_id = f"{framework}-{region}-{language}"
            return BreachTemplate(
                id=template_id,
                framework=framework,
                region=region,
                subject_template=tpl_data["subject"],
                body_template=tpl_data["body"],
                language=language,
            )
        except KeyError:
            raise ValueError(  # noqa: B904
                f"No template found for framework={framework}, "
                f"region={region}, language={language}"
            )

    def render_template(
        self,
        template: BreachTemplate,
        variables: dict[str, Any],
    ) -> tuple[str, str]:
        """Render a breach notification template with variables.

        Uses Python ``string.Template`` for variable substitution
        with ``$variable_name`` or ``${variable_name}`` syntax.
        Templates use ``{{variable_name}}`` which is converted to
        ``$variable_name`` for ``string.Template``.

        Args:
            template: The BreachTemplate to render.
            variables: Dict of variable names to values.

        Returns:
            Tuple of ``(rendered_subject, rendered_body)``.

        Raises:
            KeyError: If a required variable is missing.
        """
        # Convert {{var}} to $var for string.Template
        # First escape literal $ signs, then replace {{var}} with $var
        subject_str = template.subject_template.replace("{{", "${").replace(
            "}}", "}"
        )
        body_str = template.body_template.replace("{{", "${").replace(
            "}}", "}"
        )

        # Validate required variables
        missing = REQUIRED_VARIABLES - set(variables.keys())
        if missing:
            raise KeyError(
                f"Missing required template variables: {missing}"
            )

        subject_tpl = Template(subject_str)
        body_tpl = Template(body_str)

        rendered_subject = subject_tpl.safe_substitute(variables)
        rendered_body = body_tpl.safe_substitute(variables)

        return rendered_subject, rendered_body

    async def set_custom_template(
        self,
        framework: str,
        region: str,
        template: BreachTemplate,
    ) -> None:
        """Store a custom template for a framework/region.

        Args:
            framework: Regulatory framework.
            region: Region code.
            template: The BreachTemplate to store.
        """
        custom_key = f"{framework}:{region}:{template.language}"
        self._custom_templates[custom_key] = template
        logger.info(
            "Custom template set: framework=%s region=%s language=%s",
            framework, region, template.language,
        )

    def list_available_templates(
        self,
    ) -> list[dict[str, str]]:
        """List all available templates.

        Returns:
            List of dicts with framework, region, language, and id.
        """
        templates: list[dict[str, str]] = []

        for framework, regions in DEFAULT_TEMPLATES.items():
            for region, languages in regions.items():
                for language in languages:
                    templates.append({
                        "framework": framework,
                        "region": region,
                        "language": language,
                        "id": f"{framework}-{region}-{language}",
                    })

        for custom_key, template in self._custom_templates.items():
            framework, region, language = custom_key.split(":")
            templates.append({
                "framework": framework,
                "region": region,
                "language": language,
                "id": template.id,
                "custom": "true",
            })

        return templates
