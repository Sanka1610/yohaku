# Installation and startup configuration

Yohaku provides an embedded Python library and a limited operational CLI.
For end-user configure/start/status/stop, follow [Operational Alpha Foundation](operations.md).
The embedded-host setup below remains available for existing integrations.
Install the same normal wheel into the Python environment that owns each integration. The minimum version is **Python
3.11**; installation and regression checks cover CPython 3.11.16 and 3.14.4 on
WSL2 Linux. CPython 3.12/3.13, other operating systems and other interpreters are
not covered by that installation record. Persistence and the Hook bridge require
POSIX facilities.

There are no runtime package dependencies. Building requires `setuptools>=77`;
installing a prebuilt wheel does not require setuptools. Hermes is supplied by
the existing pinned Hermes installation, not downloaded as a Yohaku dependency.

Source-copy imports, `PYTHONPATH=.../src` and editable installs are development or
Probe techniques, not the installation path for a release candidate. No public
release is declared by the current `0.1.0` package version.

## Build and inspect the wheel

From the product checkout, build a wheel into a staging directory:

```sh
python3.11 -m pip wheel --no-deps --wheel-dir /absolute/staging/directory .
sha256sum /absolute/staging/directory/yohaku-0.1.0-py3-none-any.whl
```

The build frontend may download build requirements. Record the wheel checksum
and source commit together; the checksum distinguishes local candidates sharing
the current development version. `uv build --wheel` is another supported build
frontend. For an offline installation, obtain a reviewed wheel before proceeding.

## Codex host environment

Use an isolated venv for the existing Companion/RuntimeHost integration:

```sh
python3.14 -m venv /absolute/path/yohaku-venv
/absolute/path/yohaku-venv/bin/python -m pip install --no-index --no-deps /absolute/staging/directory/yohaku-0.1.0-py3-none-any.whl
/absolute/path/yohaku-venv/bin/python -m pip check
/absolute/path/yohaku-venv/bin/python -I -c 'import yohaku; from importlib.metadata import metadata; print(yohaku.__file__); print(metadata("yohaku")["Requires-Python"])'
```

The package path must be inside this venv's `site-packages`. The Codex process
and its Python Companion remain separate as in the existing reference. Configure
the Hook command with the **absolute path to this venv's Python**:

```text
/absolute/path/yohaku-venv/bin/python -m yohaku.hook --socket <bridge.path>
```

See the [Codex reference](reference/codex.md) for connection initialization, Hook
trust, work coverage and observer requirements. Installing the wheel does not
start Codex or register Hooks.

## Hermes host environment

For the pinned H-CLI-01 profile, install into the Python environment already used
by Hermes. Do not replace Hermes's interpreter or upgrade its dependencies:

```sh
/absolute/hermes/venv/bin/python -m pip install --no-index --no-deps /absolute/staging/directory/yohaku-0.1.0-py3-none-any.whl
/absolute/hermes/venv/bin/python -m pip check
/absolute/hermes/venv/bin/python -I -c 'import yohaku; from yohaku.hermes_adapter import HermesCLIAdapter; print(yohaku.__file__)'
```

Use the actual Hermes venv path, not an unrelated Python executable. Record
installed package versions before and after; only Yohaku should change. The
measured Hermes 0.21.0 environment uses Python 3.11.16. Its source pin and native
API requirements remain those in the [Hermes reference](reference/hermes.md).
There is no added bridge, RPC protocol or second Yohaku process for this profile.

## Enable and disable at host startup

Create an explicitly selected UTF-8 TOML file for each host. Disabled is the
default when `enabled` is omitted:

```toml
[yohaku]
runtime = "hermes-h-cli-01" # use "codex" for the Codex host
enabled = false
```

The embedding application reads it using `load_config` and wraps its existing
owner factory with `activate`:

```python
from yohaku.config import activate, load_config

config = load_config("/absolute/path/yohaku.toml")
owner = activate(config, runtime="hermes-h-cli-01", create=create_owned_hermes_host)
```

`create_owned_hermes_host` is the embedding application's existing factory, not
a Yohaku launcher. It must construct the dedicated SessionStore and adapter,
register its native observers/Hooks and return the owner. For Codex use
`runtime="codex"` and a factory that constructs its existing Companion,
HookBridge and RuntimeHost. Keep all Yohaku storage creation and Hook/observer
registration **inside** that factory. If `owner is None`, omit those registrations
and do not call owner methods. Ordinary runtime behavior remains the host's
responsibility.

Set `enabled = true` and start the host to opt in. A missing file, unknown field,
unknown runtime, non-boolean flag or runtime mismatch raises an error before
activation. The configuration contains no provider credentials or arbitrary
module/command loading. It does not change `CODEX_HOME`; configure that explicitly
in the dedicated host environment using the existing reference contract.

To disable, finish or stop the current owner using the host's existing shutdown
procedure, set `enabled = false`, and start again without the Yohaku registrations.
The flag is a startup choice, not an emergency stop for a running owner or an
instruction to repeat interrupted work. Keep checkpoint, handoff and archive
files. If completion is ambiguous, retain evidence and reconcile manually;
disabling does not establish completion. Hermes owner restart remains unsupported.

The setting is read only when the embedding application calls `load_config`.
No normal Codex/Hermes configuration is automatically edited. Installing the
package alone never enables it. The separate [operational CLI](operations.md)
supplies lifecycle-only host startup.
It uses its own JSON configuration; this embedded TOML helper remains unchanged.

## Remove the package

After stopping the owner and removing its host registrations:

```sh
/absolute/path/to/host/python -m pip uninstall yohaku
```

Uninstall removes package files, not runtime profiles or Yohaku state. Do not
delete those records as an uninstall step. Reinstall a reviewed wheel using the
same interpreter before reconnecting any host registrations.

## Evidence limits

Clean non-editable installs on 3.11.16/3.14.4, installed-package regression tests,
configuration rejection, disabled/no-owner behavior and enabled host construction
have been checked. The installed Hermes wheel also completed a native host
rehearsal through `RESUME_VERIFIED` using synthetic HTTP responses and zero
provider requests. That is installation/connection preparation, not a new live
acceptance run. The preceding Stage 4 source-based live evidence retains its
original scope; [runtime support](runtime-support.md) separates those records.
