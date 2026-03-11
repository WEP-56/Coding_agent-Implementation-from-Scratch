from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SchemaValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidationResult:
    # Validated value (may have defaults injected).
    value: Any


def _is_int(value: object) -> bool:
    # bool is a subclass of int in Python; treat it as boolean only.
    return isinstance(value, int) and not isinstance(value, bool)


def _format_path(path: list[str]) -> str:
    if not path:
        return "$"
    return "$." + ".".join(path)


def _validate_scalar(schema: dict[str, Any], value: Any, path: list[str]) -> None:
    schema_type = schema.get("type")
    if schema_type == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{_format_path(path)}: expected string")
        return
    if schema_type == "integer":
        if not _is_int(value):
            raise SchemaValidationError(f"{_format_path(path)}: expected integer")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            raise SchemaValidationError(f"{_format_path(path)}: must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise SchemaValidationError(f"{_format_path(path)}: must be <= {maximum}")
        return
    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{_format_path(path)}: expected boolean")
        return
    raise SchemaValidationError(f"{_format_path(path)}: unsupported schema type: {schema_type!r}")


def _validate(schema: dict[str, Any], value: Any, path: list[str]) -> Any:
    if "oneOf" in schema:
        last_err: Exception | None = None
        for option in schema["oneOf"]:
            try:
                return _validate(option, value, path)
            except SchemaValidationError as e:
                last_err = e
        raise SchemaValidationError(str(last_err) if last_err else f"{_format_path(path)}: no oneOf match")

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{_format_path(path)}: expected object")
        props: dict[str, Any] = schema.get("properties") or {}
        required: list[str] = schema.get("required") or []
        additional = schema.get("additionalProperties", True)

        out: dict[str, Any] = dict(value)

        # Inject simple defaults at the top level only.
        for key, prop_schema in props.items():
            if key not in out and isinstance(prop_schema, dict) and "default" in prop_schema:
                out[key] = prop_schema["default"]

        for key in required:
            if key not in out:
                raise SchemaValidationError(f"{_format_path(path + [key])}: required")

        if additional is False:
            unexpected = sorted([k for k in out.keys() if k not in props])
            if unexpected:
                raise SchemaValidationError(f"{_format_path(path)}: unexpected properties: {unexpected}")

        for key, prop_schema in props.items():
            if key in out:
                out[key] = _validate(prop_schema, out[key], path + [key])
        return out

    if schema_type == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{_format_path(path)}: expected array")
        items_schema = schema.get("items")
        if not isinstance(items_schema, dict):
            raise SchemaValidationError(f"{_format_path(path)}: array missing items schema")
        return [_validate(items_schema, item, path + [str(i)]) for i, item in enumerate(value)]

    return _validate_scalar(schema, value, path) or value


def validate_object(schema: dict[str, Any], value: Any) -> ValidationResult:
    """
    Validate a tool args payload against a restricted JSON-schema subset.
    Supported: object/properties/required/additionalProperties, string/integer/boolean/array, oneOf, min/max.
    """
    validated = _validate(schema, value, [])
    return ValidationResult(value=validated)

