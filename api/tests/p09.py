"""P-09 as tests (ADR 0004, amended by ADR 0005): decision wording exists only in two designated
places, the labelled draft recommendation and the human decision. Everything else stays forbidden.

The allow-lists below are exact and deliberately short. Adding to them is a governance decision,
not a code change: it needs a new ADR approved by the Product Owner.
"""

from typing import Any

BANNED_WORDS = (
    "approv",
    "declin",
    "rating",
    "score",
    "decision",
    "credit_limit",
    "bind",
    "traffic",
)

# Names (paths, schema properties, permissions) allowed to contain a banned word.
ALLOWED_PATHS = {
    "/api/v1/cases/{case_id}/draft-recommendations/{draft_id}/decision",
}
ALLOWED_PROPERTIES = {"decline_findings"}  # the verified findings that mean decline (policy 2e2)
ALLOWED_PERMISSIONS = {"decision:record"}  # ADR 0005 item 9
# Enum values may read as an outcome only in these designated schemas.
ALLOWED_OUTCOME_SCHEMAS = {"Outcome", "Band"}


def contains_banned(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in BANNED_WORDS)


def offending_names(schema: dict[str, Any]) -> list[str]:
    """Every path, property or enum value in an OpenAPI schema that breaks the P-09 rule."""
    problems: list[str] = []
    for path in schema["paths"]:
        if contains_banned(path) and path not in ALLOWED_PATHS:
            problems.append(f"path {path}")
    for name, model in schema["components"]["schemas"].items():
        for prop in model.get("properties", {}):
            if contains_banned(prop) and prop not in ALLOWED_PROPERTIES:
                problems.append(f"property {name}.{prop}")
        for value in model.get("enum", []):
            if contains_banned(str(value)) and name not in ALLOWED_OUTCOME_SCHEMAS:
                problems.append(f"enum value {name}.{value}")
    return problems
