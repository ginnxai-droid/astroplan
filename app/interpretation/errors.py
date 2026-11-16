class GuardrailViolation(ValueError):
    """Raised when user-visible text violates a safety or claim guardrail."""


class RuleSchemaError(ValueError):
    """Raised when rules/mvp_rules.yaml is invalid or non-conforming."""


class MissingI18nKeyError(KeyError):
    """Raised when an i18n key is missing (G6). Never silently fall back."""
