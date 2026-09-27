"""Version-1 storage codec for the fixed Core dataclasses (never pickle)."""

from dataclasses import fields, is_dataclass
from enum import StrEnum
from types import UnionType
from typing import get_args, get_origin, get_type_hints


def encode(value):
    if is_dataclass(value):
        return {f.name: encode(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, (tuple, frozenset)):
        return [encode(v) for v in (sorted(value) if isinstance(value, frozenset) else value)]
    return value


def decode(kind, value):
    origin, args = get_origin(kind), get_args(kind)
    if origin is UnionType:
        for alternative in args:
            try:
                return decode(alternative, value)
            except (TypeError, ValueError):
                pass
        raise ValueError("invalid optional value")
    if origin in (tuple, frozenset):
        if type(value) is not list:
            raise ValueError("expected array")
        return origin(decode(args[0], v) for v in value)
    if is_dataclass(kind):
        if type(value) is not dict or set(value) != {f.name for f in fields(kind)}:
            raise ValueError("unexpected storage fields")
        hints = get_type_hints(kind)
        return kind(**{k: decode(hints[k], v) for k, v in value.items()})
    if isinstance(kind, type) and issubclass(kind, StrEnum):
        return kind(value)
    if kind is float and type(value) in (float, int):
        return float(value)
    if type(value) is not kind:
        raise ValueError("unexpected storage value type")
    return value
