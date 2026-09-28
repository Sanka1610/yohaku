# Operational Alpha Foundation

The installed `yohaku` command provides operational lifecycle management and one
fixed Real-task Profile, not an Alpha release or a general task runner. The
lifecycle-only profiles accept no task input and report
`TASK_PROFILE_REQUIRED`. `document-review-report-v1` has a separate `run`
entry point with a task-specific observer and assessor. There is no flag that
turns a lifecycle profile into a general task profile.

## Profiles and evidence

Run `yohaku profiles`. Every entry reports runtime/version/surface, maturity,
evidence level, verdict, evidence scope, and Known Limitations. Runtime maturity
is `experimental`; release channel is `undeclared`. A lifecycle `PASS` does not
change historical Transition Evidence or imply `RESUME_VERIFIED`.

| Profile | Launcher scope | Transition scope |
|---|---|---|
| `codex-document-review-report-v1` | Codex `0.158.0-alpha.2.1`, dedicated App Server, fresh thread, two exact dynamic tools | One declared input set, one manual compact, one create-only Markdown report; bounded live PASS |
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

The Real-task Evidence ID is `DRR-V1-CODEX-0158-LIVE-01`. Its PASS covers one
public-document review run, not prose quality, arbitrary inputs, another Runtime,
restart, repeated transitions, field use or release readiness.

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
The document-review profile additionally binds task_inputs, task_output,
task_instruction and credential_home; other profiles reject those fields.
Unknown fields and changed binding fields fail closed. Use enable/disable for
activation changes; configure a new root for a different runtime/profile/workspace.
Do not reuse an old session by copying or editing its configuration binding.

## Run `document-review-report-v1`

Create a new mode-0700 workspace containing only the declared mode-0600 input
files. The fixed output must not exist. Configuration and state directories must
remain outside the task workspace. `--credential-home` identifies an existing
Codex home containing `auth.json`; Yohaku links that credential into the isolated
run home and does not copy it into Evidence.

```sh
/absolute/path/yohaku-venv/bin/yohaku configure \
  --config /absolute/path/yohaku-config/review.json \
  --profile codex-document-review-report-v1 \
  --runtime-path /absolute/path/to/codex \
  --workspace /absolute/path/review-workspace \
  --state-dir /absolute/path/yohaku-review-state \
  --single-owner --dedicated-session \
  --input /absolute/path/review-workspace/first.md \
  --input /absolute/path/review-workspace/second.md \
  --output /absolute/path/review-workspace/review-report.md \
  --instruction "Review the declared documents for contradictions and risks." \
  --credential-home /absolute/path/existing-codex-home
/absolute/path/yohaku-venv/bin/yohaku preflight \
  --config /absolute/path/yohaku-config/review.json
/absolute/path/yohaku-venv/bin/yohaku enable \
  --config /absolute/path/yohaku-config/review.json
/absolute/path/yohaku-venv/bin/yohaku run \
  --config /absolute/path/yohaku-config/review.json
```

The Runtime can call only `read_review_inputs` and `publish_review_report`.
The first read establishes the boundary. After manual compaction and receipted
handoff, the Runtime must perform a fresh read and then create the pending report.
The report receives a provenance comment with input and instruction hashes.
Mechanical completion and writing quality are separate fields; a successful run
reports `mechanical_task_completion=PASS`, `core_state=RESUME_VERIFIED` and
`writing_quality=NOT_ASSESSED`.

The report write uses exclusive creation and is never retried after an uncertain
result. A second preflight or run with the same output returns
`STALE_OUTPUT_PRESENT`. Interrupted task runs are inspect-only; configure a new
workspace and state root after maintainer review rather than deleting state or
reusing the old output. See the [task contract](reference/document-review-report-v1.md).

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
shutdown. No task can be active in the lifecycle-only profiles. The document-review
`run` command is foreground and exits after verified completion or refusal; it is
not controlled by the lifecycle `stop` command.

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

The first Real-task Profile now has a trusted boundary, current-state observation,
independent assessor, exact tools, negative cases and current Codex live Evidence.
This removes the lifecycle-only blocker for that one profile. Alpha still needs a
reviewed release candidate, published release record and issue workflow, an
explicit maturity decision, and final Evidence review. Field Evidence, restart,
repeated transitions, general Hermes tool coverage, general document work and
coding work remain outside the accepted scope.
