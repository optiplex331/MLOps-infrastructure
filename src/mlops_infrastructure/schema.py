"""Small Draft 2020-12 subset for bounded infrastructure JSON contracts.

An unknown assertion keyword fails closed so contract evolution cannot
silently bypass validation.
"""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any


_ANNOTATIONS = {"$id", "$schema", "title", "description", "$defs"}
_ASSERTIONS = {
    "$ref",
    "additionalProperties",
    "const",
    "enum",
    "format",
    "items",
    "minimum",
    "minItems",
    "minLength",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "type",
    "uniqueItems",
}


class SchemaError(ValueError):
    pass


def validate(instance: Any, schema: dict[str, Any]) -> None:
    _validate(instance, schema, schema, "$")


def _validate(value: Any, node: dict[str, Any], root: dict[str, Any], path: str) -> None:
    unknown = set(node) - _ANNOTATIONS - _ASSERTIONS
    if unknown:
        raise SchemaError(f"unsupported schema keywords at {path}: {sorted(unknown)}")

    if "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise SchemaError(f"only local JSON pointers are supported at {path}")
        target: Any = root
        for token in ref[2:].split("/"):
            target = target[token.replace("~1", "/").replace("~0", "~")]
        _validate(value, target, root, path)
        return

    if "oneOf" in node:
        successes = 0
        for option in node["oneOf"]:
            try:
                _validate(value, option, root, path)
                successes += 1
            except SchemaError:
                pass
        if successes != 1:
            raise SchemaError(f"{path} must match exactly one oneOf branch")

    if "const" in node and value != node["const"]:
        raise SchemaError(f"{path} must equal {node['const']!r}")
    if "enum" in node and value not in node["enum"]:
        raise SchemaError(f"{path} is not an allowed value")

    expected = node.get("type")
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
        None: True,
    }
    if expected not in matches:
        raise SchemaError(f"unsupported type {expected!r} at {path}")
    if not matches[expected]:
        raise SchemaError(f"{path} must be {expected}")

    if isinstance(value, dict):
        required = node.get("required", [])
        missing = sorted(set(required) - set(value))
        if missing:
            raise SchemaError(f"{path} is missing required properties: {missing}")
        properties = node.get("properties", {})
        if node.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise SchemaError(f"{path} has unexpected properties: {extra}")
        for key, child in properties.items():
            if key in value:
                _validate(value[key], child, root, f"{path}.{key}")

    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            raise SchemaError(f"{path} has too few items")
        if node.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                raise SchemaError(f"{path} items must be unique")
        if "items" in node:
            for index, child in enumerate(value):
                _validate(child, node["items"], root, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            raise SchemaError(f"{path} is too short")
        if "pattern" in node and re.search(node["pattern"], value) is None:
            raise SchemaError(f"{path} does not match {node['pattern']!r}")
        if node.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise SchemaError(f"{path} is not an RFC 3339 date-time") from exc
            if parsed.tzinfo is None:
                raise SchemaError(f"{path} date-time must include an offset")

    if isinstance(value, int) and value < node.get("minimum", value):
        raise SchemaError(f"{path} is below its minimum")
