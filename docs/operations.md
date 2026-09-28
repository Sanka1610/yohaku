# Operational Alpha Foundation

The installed `yohaku` command provides **operational lifecycle management**, not
an Alpha release or a general task runner. It starts a dedicated native host,
reports its identity, and stops it while keeping state. These profiles accept no
task input and perform no inference, compaction, handoff or resume verification.
A missing real-task observer/assessor is reported as `TASK_PROFILE_REQUIRED`.
There is no flag to bypass this restriction.

## Profiles and evidence

Run `yohaku profiles`. Every entry reports runtime/version/surface, maturity,
evidence level, verdict, evidence scope, and Known Limitations. Runtime maturity
is `experimental`; release channel is `undeclared`. A lifecycle `PASS` does not
change historical Transition Evidence or imply `RESUME_VERIFIED`.

| Profile | Launcher scope | Transition scope |
|---|---|---|
| `codex-operational-0.158` | Codex `0.158.0-alpha.2.1`, dedicated App Server, fresh thread, Companion/store | Disabled; current-version real-task acceptance NOT_RUN |
| `hermes-operational-h-cli-01` | Hermes `0.21.0`, source `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`, native CLI construction and store in one process | Disabled; lazy inference agent and H-CLI-01 transition adapter are **not activated** |
| `codex-reference-0.155` | Historical profile; launcher refuses start | Reference `0.155.0-alpha.16.4`, overall PARTIAL; not evidence for 0.158 |
| `hermes-h-cli-01` | Historical embedded adapter; launcher refuses start | One fixture tool, one manual compression; bounded PASS / overall PARTIAL |
| `claude-c-cli` | Listed, no operational launcher | Bounded external manual-completion PASS; subscription recovery live NOT_RUN |
| `claude-c-cli-local-nonce` | Listed, no operational launcher | Maintainer Ollama/qwen3.5:9b nonce recovery: bounded synthetic PASS / overall PARTIAL |

No Claude entry declares Claude-wide Alpha support. Existing full-identity and
nonce receipt adapters retain their separate contracts.

The operational checks cover CPython 3.14.4 with Codex and CPython 3.11.16 in the
existing Hermes venv, on WSL2 Linux. Preflight requires these exact CPython/runtime versions on WSL2 Linux.
Other versions and platforms need separate review. Operational Evidence IDs are
`S5-OP-CODEX-0158` and `S5-OP-HERMES`; they describe native lifecycle with no inference.
Timeout evidence includes local tests with an injected host and a separate
controlled pause of the owned native App Server. The latter confirms that the
owner retains its lock until native shutdown actually completes.

## Install the common wheel

Use the [installation guide](installation.md) to obtain/build a reviewed wheel.
Record its SHA-256 and source commit. The development package version `0.1.0`
alone does not identify a candidate. Do not use editable installs or copy Yohaku
source into the native host.

For Codex:

```sh
python3.14 -m venv /absolute/path/yohaku-venv
/absolute/path/yohaku-venv/bin/python -m pip install --no-index --no-deps /absolute/path/yohaku-0.1.0-py3-none-any.whl
/absolute/path/yohaku-venv/bin/python -m pip check
/absolute/path/yohaku-venv/bin/yohaku profiles
```

For Hermes, use `/absolute/hermes-root/venv/bin/python` and install the **same**
wheel without upgrading native dependencies. Its CLI executable will be
`/absolute/hermes-root/venv/bin/yohaku`. All Hermes commands must run in that venv
and on the host where the pinned source exists; this is not a remote bridge.

## Configure and start

Use a new private configuration directory and a separate new state directory.
The task workspace must already exist. Paths must be absolute and contain no
symlink components; resolve an executable symlink before configuring.
Configuration is JSON, separate from the older embedded-library TOML helper.

```sh
install -d -m 700 /absolute/path/yohaku-config
/absolute/path/yohaku-venv/bin/yohaku configure \
  --config /absolute/path/yohaku-config/codex.json \
  --profile codex-operational-0.158 \
  --runtime-path /absolute/path/to/codex \
  --workspace /absolute/path/project \
  --state-dir /absolute/path/yohaku-codex-state \
  --single-owner --dedicated-session
/absolute/path/yohaku-venv/bin/yohaku preflight --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku enable --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku start --config /absolute/path/yohaku-config/codex.json
```

For Hermes, use its `venv/bin/yohaku`, profile `hermes-operational-h-cli-01`, and
`--runtime-path /absolute/hermes-root` (source directory, not its shell launcher).
Choose a distinct config and state directory. No existing native profile is adopted.

`configure` creates a disabled configuration and binds it to the new state root.
`enable` allows the next start; it does not start a process or enable transitions.
Preflight can pass while disabled; `start` still refuses until explicitly enabled.
`--single-owner` and `--dedicated-session` acknowledge operating assumptions;
they do not discover other clients or prove global workspace exclusivity.
A local lock prevents cooperating launchers from sharing one state root.

The foreground `start` command prints a JSON startup record and remains running.
Use another terminal for status/stop. The same commands are available through
`/absolute/venv/bin/python -I -m yohaku`.

Configuration fields are schema, profile, runtime_path, workspace, state_dir,
single_owner, dedicated_session, enabled and stop_timeout (0.1–60 seconds).
Unknown fields and changed binding fields fail closed. Use enable/disable for
activation changes; configure a new root for a different runtime/profile/workspace.
Do not reuse an old session by copying or editing its configuration binding.

Codex uses a fresh per-run home, no credentials, a disabled loopback provider,
and only initialize/thread-start requests. It never sends turn/start or compact.
Its Companion is attached, but task hooks, work observations and recovery dispatch
are unavailable. Project-local config/hooks are untrusted and disabled. A nonempty
`/etc/codex` is rejected because system configuration has not been reviewed for
this isolated profile. App Server startup follows the [official protocol](https://learn.chatgpt.com/docs/app-server);
Yohaku's restrictions and acceptance are specific to the profile above.

Hermes constructs the pinned native `HermesCLI`, opens its native DB and a
Yohaku SessionStore in the same process, and leaves its lazy inference agent
uninitialized. Native chat/compress/agent activation are rejected. A process-local
audit guard rejects Internet sockets and child processes, including during native
cleanup. It is a lifecycle-only connection, not the measured H-CLI-01 task/tool
workflow. Status exposes `native_host_constructed`, `inference_agent_initialized`,
`companion_attached`, `transition_adapter_attached` and `work_observation_available`
separately. The launcher does not register task Hooks or claim their coverage.

## Status, stop, disable and recovery

```sh
yohaku status --config /absolute/path/yohaku-config/codex.json
yohaku stop --config /absolute/path/yohaku-config/codex.json
yohaku disable --config /absolute/path/yohaku-config/codex.json
yohaku recover --inspect --config /absolute/path/yohaku-config/codex.json
```

Replace `yohaku` with the absolute executable used above. Output is always JSON;
`--json` is also accepted. Status includes installed package identity, Python,
expected and observed runtime identity, historical evidence, live owner reachability,
last operation, recovery decision and refusal reasons. It is not a proof of task
completion. Inspection does not automatically validate all historical checkpoint
contents or grant any execution authority.

`stop` requests shutdown over a private Unix socket. Codex receives stdin EOF and
must exit successfully; Hermes closes its native DB and Yohaku store. The owner
marks STOPPED only after host cleanup. Ctrl-C/SIGTERM request the same graceful
shutdown. No task can be active in these lifecycle-only profiles.

On timeout the owner retains its lock and reports `STOP_INCOMPLETE`. It continues
to observe shutdown, accepts status/stop, and does not escalate to SIGKILL.
Do not uninstall while it is still running. An unreachable owner is not assumed
dead. A crashed owner or incomplete startup keeps restart blocked even if a PID
is absent; deleting lock files or changing STOPPED metadata is not recovery.
Preserve the run directory and inspect the runtime before maintainer review.

After a confirmed clean stop, enable/start can create a **new** dedicated session
under the same root. It never resumes or overwrites the old session. `recover`
without `--inspect` is rejected. Codex's embedded library has narrower historical
reconciliation APIs, but the launcher supplies no real-task assessor for them.
Hermes owner restart remains unsupported. Old leases and dispatch permits are not
restored. `transition` always rejects with `TASK_PROFILE_REQUIRED`.

## Data retention and uninstall

The private state root contains a configuration binding, owner lock, last-run
metadata and separate `runs/<run-id>/` directories. Native homes, databases and
Yohaku session storage live inside each run. Operational metadata is separate
from existing checkpoint, handoff, archive and journal formats. Each start leaves
all older run directories intact; the launcher does not create verified
checkpoints without the required task observations.

After `stop`, confirm `owner_lock_busy=false` and `operational.state=STOPPED`,
then `disable`. Uninstall using the same interpreter:

```sh
/absolute/path/to/venv/bin/python -m pip uninstall yohaku
```

Keep the configuration and entire state root, including native DB files and their
sidecars. Package uninstall does not remove these user-managed directories.
Reinstall a reviewed wheel before running inspect again. Retention tests compare
checkpoint/handoff/archive bytes; they do not establish task or crash recovery.
The commands do not migrate old state or downgrade its schema.

## Remaining Alpha requirements

This foundation is usable for installation, lifecycle and refusal checks. An
Alpha transition profile still needs a selected real workflow, trusted boundary
and current-state observation, an independent assessor, permitted tools and
negative cases, then artifact-specific Evidence review. Current Codex transition
acceptance and general Hermes tool coverage remain unestablished. Issue triage,
release/version record and maturity decisions remain separate release work.
