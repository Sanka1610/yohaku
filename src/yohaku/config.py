"""Explicit startup opt-in for the two existing embedded host integrations.

This does not install native hooks, configure authentication, or change a running
owner. Stop and reconcile an existing owner before starting with another config.
"""

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class HostConfig:
    runtime: str
    enabled: bool = False

    def __post_init__(self):
        if self.runtime not in ('codex', 'hermes-h-cli-01') or type(self.enabled) is not bool:
            raise ValueError('expected codex or hermes-h-cli-01 and a boolean enabled flag')


def load_config(path):
    """Read an explicitly selected TOML file; malformed/missing input is an error."""
    with Path(path).open('rb') as stream:
        data = tomllib.load(stream)
    if set(data) != {'yohaku'} or not isinstance(data['yohaku'], dict):
        raise ValueError('expected only a yohaku table')
    config = data['yohaku']
    if 'runtime' not in config or set(config) - {'runtime', 'enabled'}:
        raise ValueError('expected runtime and optional enabled settings')
    return HostConfig(**config)


def activate(config, *, runtime, create):
    """Call the supplied existing host factory only when enabled for that runtime.

    The caller must also omit observer/hook registration when this returns None.
    No environment variables, configuration files or runtime settings are changed.
    """
    if not isinstance(config, HostConfig) or config.runtime != runtime:
        raise ValueError('configuration does not match the embedding runtime')
    return create() if config.enabled else None
