"""Validator pipeline / manager for dynamic registration of Layer-2 validators."""
from __future__ import annotations

import logging
from typing import Any

from app.guardrails.base_validator import BaseValidator
from app.guardrails.exceptions import FactualValidationError

logger = logging.getLogger(__name__)


def _get_field(payload: Any, field: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(field)
    try:
        return getattr(payload, field)
    except Exception:  # noqa: BLE001
        return None


class ValidatorPipeline:
    """Dynamic registry + runner for Layer-2 validators.

    Validators can be registered globally (validate the whole payload) or against
    a specific field name. Registration returns ``self`` for fluent chaining.
    """

    def __init__(self) -> None:
        self._field_validators: dict[str, list[BaseValidator]] = {}
        self._global_validators: list[BaseValidator] = []

    def register(
        self, validator: BaseValidator, field: str | None = None
    ) -> "ValidatorPipeline":
        if field is None:
            self._global_validators.append(validator)
        else:
            self._field_validators.setdefault(field, []).append(validator)
        return self

    def unregister(self, validator: BaseValidator, field: str | None = None) -> None:
        if field is None:
            if validator in self._global_validators:
                self._global_validators.remove(validator)
        else:
            lst = self._field_validators.get(field, [])
            if validator in lst:
                lst.remove(validator)

    def validators(self) -> list[BaseValidator]:
        out: list[BaseValidator] = list(self._global_validators)
        for vs in self._field_validators.values():
            out.extend(vs)
        return out

    async def validate_payload(
        self, payload: Any, context: dict[str, Any] | None = None
    ) -> None:
        ctx = dict(context or {})
        ctx.setdefault("payload", payload)

        errors: list[dict[str, Any]] = []

        # Field-level validators.
        for field, validators in self._field_validators.items():
            value = _get_field(payload, field)
            field_ctx = {**ctx, "field": field}
            for v in validators:
                try:
                    await v.validate(value, field_ctx)
                except FactualValidationError as exc:
                    if exc.errors:
                        errors.extend(exc.errors)
                    else:
                        errors.append(
                            {
                                "loc": [field],
                                "msg": str(exc),
                                "type": "factual",
                                "input": value,
                            }
                        )
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        {
                            "loc": [field],
                            "msg": str(exc),
                            "type": "factual_error",
                            "input": value,
                        }
                    )

        # Global validators (whole payload).
        for v in self._global_validators:
            try:
                await v.validate(payload, {**ctx, "field": None})
            except FactualValidationError as exc:
                if exc.errors:
                    errors.extend(exc.errors)
                else:
                    errors.append(
                        {
                            "loc": [],
                            "msg": str(exc),
                            "type": "factual",
                            "input": payload,
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "loc": [],
                        "msg": str(exc),
                        "type": "factual_error",
                        "input": payload,
                    }
                )

        if errors:
            raise FactualValidationError(errors)
