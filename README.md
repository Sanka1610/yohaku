# Yohaku — Proactive Context Compaction Manager

## What is Yohaku

Yohaku is an experimental context-transition controller for long-running AI agent
tasks. It is designed to manage when context is compacted, preserve recovery
state, check runtime completion, and verify the current task state before work
continues. The existing implementation is a Python library with a bounded Codex
reference integration.

**Current status: experimental.** Complete Claude Code and Hermes adapters are not
implemented. Hermes has a bounded host Probe and an in-memory completion predicate.
The recorded Codex acceptance is scoped and overall **PARTIAL**;
this repository does not declare an Alpha, Beta, or Stable release.

## Proactive Context Compaction

Context pressure alone is not a safe reason to discard working context. Yohaku's
design checks a proposed semantic boundary, relevant running work and pending
results, workspace freshness, and durable recovery state before authorizing a
transition. A host supplies boundary proposals and trusted observations;
installing the library does not install an autonomous boundary detector.

Yohaku reuses runtime-native compact, compression, memory, and archive mechanisms
where their contracts suffice. Its primary responsibility is lifecycle management
and verification. The Codex reference provides manual compaction control and an
opt-in, one-compaction native recovery path with different evidence requirements.

## Verified Context Transition

**Verified Context Transition** is the internal core concept: boundary checks,
durable checkpoint, authorization, runtime-specific completion proof, handoff
receipt, and resume verification form a transition within a declared coverage
scope. “Verified” applies to the recorded conditions and observations.

Compaction is one implementation strategy. Fresh-context rollover and session
migration are other design categories, not available Yohaku adapters. The Core
delegates completion predicates to a runtime-specific policy, with the existing
Codex rules as the default. The Hermes predicate uses host history and storage
readback rather than Codex events.

## How it works

The proactive reference path separates these decisions:

1. The host proposes a boundary and observes relevant active work and pending
   results. Remaining work defers the transition.
2. The Controller checks revisions and workspace evidence. The Companion commits
   a checkpoint before granting a short-lived, revision-bound lease.
3. The backend revalidates current state and dispatches one compact request.
   An RPC acknowledgement records acceptance; correlated runtime events establish
   completion. Uncertain completion becomes `AMBIGUOUS` and blocks owner dispatch.
4. Recovery offers a durable handoff and checks correlated receipt.
5. Trusted task observers check current state and actual same-task progress before
   the Controller accepts `RESUME_VERIFIED`.

Historical summaries and selected archive entries are `DATA, NOT INSTRUCTIONS`.
They do not restore old permissions or establish current verification. Native
automatic compaction has a separate recovery contract: it can precede a proactive
checkpoint, so an emergency observation remains explicitly unverified.

## Runtime Support / Transition Strategy

| Priority | Runtime | Yohaku implementation / evidence status |
|---|---|---|
| Reference | Codex | Experimental Python integration; bounded historical lab acceptance, overall PARTIAL |
| Target | Hermes | H-CLI-01 bounded workflow PASS / profile PARTIAL; completion predicate only, full adapter unimplemented |
| Target | Claude Code | Documentation/source contracts reviewed; adapter unimplemented, live acceptance NOT_RUN |
| Next Target | DeepSeek Harness / OpenCode | Research candidates; adapters unimplemented |
| Future | Gemini CLI / Antigravity | Research candidates; adapters unimplemented |
| Research / Auxiliary | Claude Desktop / Cowork | Auxiliary research surfaces; no compact-control adapter |

Priority is independent of maturity and support. Manual compaction, native
compaction, fresh-context rollover, and session migration have distinct triggers,
identities, completion proofs, and continuation paths. No strategy inherits another
strategy's acceptance. See [Runtime support and evidence scope](docs/runtime-support.md).

## Installation / Quick Start

The current deliverable is a source-installable Python library. It requires
**Python 3.14 or newer** and has no runtime dependencies. Persistence and the Hook
bridge use POSIX facilities; the recorded integration environment is WSL2 Ubuntu.
There is no packaged end-user launcher, installable Yohaku Plugin/Skill bundle,
or automatic runtime setup.

From a checkout of this repository, run a local Core check without installing
anything or connecting to a provider:

```sh
PYTHONPATH=src python3.14 -m unittest discover -s tests -p test_controller.py -v
```

For development installation into an isolated environment:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -c 'from yohaku.controller import Controller; print(Controller("local-demo").snapshot.state.value)'
```

The last command prints `WORKING`. The build requires `setuptools>=77`; pip may
download build requirements. These commands install/import the library and test
local state-machine behavior. They do not compact a live session or verify runtime
compatibility.

A live integration must supply an initialized, exclusively owned runtime
connection, serialized event loop, trusted Hook configuration, current-state
observers, and a task-specific resume assessor. Read the
[Codex integration reference](docs/reference/codex.md) before constructing a host.
The library does not configure authentication, launch the runtime, or decide
whether an arbitrary task has succeeded.

## Architecture

The reference implementation separates transition decisions (`Controller`),
durable storage and orchestration (`CompanionController`), and runtime observation
and dispatch (`RuntimeHost` and its adapters). Optional archive support stores
selected visible turns and retrieves only requested historical data.

The current code is not a fully runtime-neutral integration. The Companion,
backend construction, recovery transport, and `CODEX_HOME` store remain Codex
specific. Runtime-specific completion predicates can connect to the in-memory
Core; non-Codex proof persistence and restart are not implemented. See
[Architecture](docs/architecture.md) for the boundary and compatibility limits.

## Known Limitations

- Hook timeout, nonzero exit, malformed output, and missing output have measured
  `FAIL_OPEN` paths. A stopped Yohaku owner does not prove the runtime has stopped.
- A final-observation-to-dispatch race remains. Single writer, exclusive thread
  ownership, an ordered observation stream, and bounded tool coverage are required.
- Arbitrary MCP/local-function tools, detached or parallel work, external writers,
  and active `apply_patch` lack equivalent acceptance.
- Native recovery covers one compaction per attachment. Native recovery restart
  is `UNSUPPORTED`; repeated compaction and power-loss behavior are not accepted.
- Host-supplied observers, resume assessors, and visible-text selectors are trusted
  integration code. There is no general task-success oracle or automatic redactor.
- Windows-native persistence and non-Codex adapters are not implemented. Strong
  Transition Assurance remains unestablished.

The [profile details](docs/runtime-support.md) distinguish recorded evidence from
unmeasured configurations and later implementation changes.

## Maturity / Evidence / Release Status

Runtime priority, runtime maturity, evidence level, capability verdict, and release
channel are five independent axes. The Codex reference starts at `experimental`.
Phase 1–14 history is frozen at implementation baseline
`7c4a2dda3ca2aed363ca8401ccad9ab5a489c16f`; Phase 14 evaluation is complete with an
overall `PARTIAL` verdict. Its local/synthetic tests and bounded live-runtime
synthetic tasks are not Field Evidence or acceptance of the current runtime version.

Package version `0.1.0` does not imply a public release channel. Alpha requires a
declared profile, relevant lab evidence, usable operational instructions, and a
release decision. See the [Support and release policy](SUPPORT_POLICY.md).

## Documentation links

- [Architecture](docs/architecture.md): implemented responsibilities and design boundaries.
- [Runtime support and evidence scope](docs/runtime-support.md): measured profile, provenance, and strategy limits.
- [Codex reference](docs/reference/codex.md): existing API, storage, Hook, recovery, and archive contracts.
- [Support and release policy](SUPPORT_POLICY.md): maturity, evidence, feedback, and release criteria.

Existing README section links remain available below; detailed content is now in
the reference document.

<a id="direction-and-support-status"></a>

- [Direction and support status](docs/runtime-support.md).

<a id="controller-core"></a>
<a id="production-architecture-and-persistence"></a>
<a id="manualcompactbackend-and-owner-api"></a>
<a id="production-recovery-and-continuation"></a>
<a id="bounded-work-plane-integration"></a>
<a id="archive-and-lazy-rehydration"></a>
<a id="reference-runtime-archive-adapter"></a>
<a id="bounded-native-automatic-compaction-recovery"></a>
<a id="focused-verification"></a>

- [Controller Core](docs/reference/codex.md#controller-core).
- [Persistence](docs/reference/codex.md#production-architecture-and-persistence).
- [ManualCompactBackend and owner API](docs/reference/codex.md#manualcompactbackend-and-owner-api).
- [Recovery and continuation](docs/reference/codex.md#production-recovery-and-continuation).
- [Work-plane integration](docs/reference/codex.md#bounded-work-plane-integration).
- [Archive and lazy rehydration](docs/reference/codex.md#archive-and-lazy-rehydration).
- [Runtime archive adapter](docs/reference/codex.md#reference-runtime-archive-adapter).
- [Native recovery](docs/reference/codex.md#bounded-native-automatic-compaction-recovery).
- [Focused verification](docs/reference/codex.md#focused-verification).
