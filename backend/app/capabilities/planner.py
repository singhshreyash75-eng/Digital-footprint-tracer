from typing import Any

from app.investigations.models import Subject
from app.providers.base import BaseProvider


class CapabilityPlanner:
    """
    Validates a requested capability set against
    the selected provider's capability catalog.
    """

    def build_plan(
        self,
        subject: Subject,
        provider: BaseProvider,
        requested: list[str],
    ) -> dict[str, Any]:

        definitions = provider.get_capability_definitions()

        plan = []

        for capability in requested:
            definition = definitions.get(capability)

            if definition is None:
                plan.append(
                    {
                        "capability": capability,
                        "supported": False,
                        "requires_auth": False,
                        "description": None,
                    }
                )
                continue

            plan.append(
                {
                    "capability": capability,
                    "supported": True,
                    "requires_auth": definition.get(
                        "requires_auth",
                        False,
                    ),
                    "description": definition.get(
                        "description"
                    ),
                }
            )

        executable = all(
            item["supported"]
            for item in plan
        )

        return {
            "subject_id": subject.id,
            "provider": provider.name,
            "requested": requested,
            "plan": plan,
            "executable": executable,
        }