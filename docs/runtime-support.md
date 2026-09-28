# Runtime support and evidence scope

This page summarizes the preserved Codex reference records and the bounded
Hermes H-CLI-01 Probe and connected adapter run as of 2026-09-28.
Local regression tests and the single adapter live run have separate evidence.
The implementation is experimental; no public release channel is declared. [Support policy](../SUPPORT_POLICY.md) defines the independent axes
of priority, maturity, evidence level, verdict, and release channel.

## Recorded Codex reference profile

| Dimension | Recorded scope |
|---|---|
| Runtime / surface | Codex CLI `0.155.0-alpha.16.4`, owned App Server connection |
| OS / language runtime | WSL2 Ubuntu / Python `3.14.4` |
| Provider/model record | Model `gpt-5.6-luna`, effort `low`; no claim for other providers or subscriptions |
| Owner assumptions | Single writer, exclusively owned thread, ordered observation stream, bounded work coverage |
| Work | Normal deny/ordering for Bash and apply_patch; active/pending DEFER for one registered foreground Bash worker |
| Archive integration | Opt-in dynamic tools with `experimentalApi=true`; trusted visible-text selector |
| Maturity | experimental |
| Acceptance | Phase 14 evaluation COMPLETE; overall PARTIAL |
| Evidence kinds | lab tested / local-synthetic and lab tested / live-runtime synthetic tasks, with controlled negatives |
| Field / current-version evidence | Not established by these records |

Raw run records and CoverageProfiles are retained in the private development
workspace and ignored local Probe results. They are not bundled with the source
distribution. This public summary is not an independently reproducible evidence
bundle; publication of reviewed, shareable evidence remains release preparation.

## Transition strategies

| Strategy | Implementation and completion contract | Limits |
|---|---|---|
| Codex manual compaction | `ManualCompactBackend`; correlated compaction item completion, successful PostCompact, and successful compact turn completion | RPC ACK alone is insufficient; one outstanding request and exclusive ownership required |
| Codex native automatic compaction recovery | Opt-in observer; correlated compaction item completion and PostCompact, followed by same-turn receipt and resume verification | One compaction per attachment; emergency delta unverified; native recovery restart UNSUPPORTED |
| Codex experimental `new_context` | Not selected by the package; UNSUPPORTED in the measured configurations | No fresh-context support inferred from the manual path |
| Hermes manual in-place compression | H-CLI-01 adapter uses host-history update plus independent DB readback, explicit tool receipt and Core resume gates | One fresh exclusive session and one manual request; embedded instrumentation required, no restart |

Native recovery does not prove the proactive boundary/checkpoint/lease sequence
was completed before native compaction. Manual and native results remain separate.
For exact host requirements, see the [implementation reference](reference/codex.md).

## Historical provenance

| Record | Source association and permitted interpretation |
|---|---|
| Phase 1–14 freeze | Integrated implementation baseline `7c4a2dda3ca2aed363ca8401ccad9ab5a489c16f` |
| Phase 14 A–F/H/I | Retain the `c490f9172dcb7928810d8c2ff5e3ac217f7f7de0` profile association and each scenario's original evidence; B reuses earlier live evidence and E is post-run artifact validation |
| Phase 14 G | `7c4a2dda3ca2aed363ca8401ccad9ab5a489c16f`; one native compaction, same-turn continuation, and controlled missing-completion negative |
| Recorded 98 tests | Local/synthetic regression evidence at the G baseline; not 98 live or field scenarios |

Freeze preserves source associations and verdicts. A new document or integration
commit does not mean historical scenarios were rerun against that commit. Late
event delivery, duplicate ACK replay, and restart checks retain their controlled
test conditions; they are not general failure-recovery guarantees.

## Remaining limitations

- Hook failure paths remain `FAIL_OPEN`; owner dispatch suppression is not global
  runtime cancellation or an atomic work barrier.
- The final-read-to-dispatch race and lack of native context-generation identity
  remain. Controller generation must not be presented as native context identity.
- Active apply_patch, general MCP/local-function work, detached/parallel work,
  external writers, inflight work-ledger restart, and incomplete-turn archive
  restart lack equivalent acceptance.
- Power loss, repeated native compaction, and live native/manual dispatch races
  remain NOT_RUN in the historical profile. Native recovery restart is UNSUPPORTED.
- A task-specific observer/assessor and a trusted archive selector are required.
  No automatic secret classifier or general success oracle is included.
- Windows-native persistence, other OS/surface profiles, and non-Codex adapters
  are not covered by the reference evidence. Strong Transition Assurance remains
  PARTIAL / unestablished.

## Target runtime status

Claude Code and Hermes are Targets. DeepSeek Harness and
OpenCode are Next Targets; Gemini CLI and Antigravity are Future candidates.
Claude Desktop and Cowork are Research / Auxiliary surfaces.

Claude Code C-CLI has a bounded adapter for 2.1.280/Linux/`claude -p`/stream-json
with synchronous command Hooks. A returned external live-runtime synthetic
acceptance was reviewed against the original bundle source hashes and the unchanged
completion policy: Yohaku ManualRequest through ROLLOVER_OBSERVED is **PASS**,
overall **PARTIAL**, issues `[]`. The observed order was PreCompact,
SessionStart(compact), PostCompact; either order of the last two remains valid.
The sanitized submission supports correlation review, not independent readback of
the tester's private checkpoint/lease or authentication of the external run.
The older Probe report and its TIME_LIMIT remain a separate historical record.

`ClaudeCLIAdapter` still stops at ROLLOVER_OBSERVED. The opt-in
`ClaudeCLIRecoveryAdapter` adds one controller-owned recovery input, explicit
handoff/checkpoint receipt, fresh current-state observation, a single remaining
fixture action and task-specific resume verification. Local fixtures and a fake
CLI using real local command-Hook IPC reach RESUME_VERIFIED and reject missing,
stale, duplicate or inconsistent evidence. This recovery route keeps the CLI
process alive across compaction, unlike the earlier completion-only acceptance;
its new external live acceptance remains **NOT_RUN**. A successful later action
alone is neither receipt nor resume proof. Overall C-CLI remains **PARTIAL**.
See the [C-CLI reference](reference/claude-cli.md) for the exact trust and coverage
boundaries. Agent SDK/API remains a separate unimplemented profile.

Hermes H-CLI-01 measured an instrumented native CLI host on Ubuntu-Hermes, version
0.21.0 at `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`, using the existing
`openai-codex` route with `gpt-5.6-luna` and low effort for main and compression.
The Stage 2 live synthetic-task Probe used eight provider requests and one manual
compression. Bounded workflow: PASS; profile overall: PARTIAL. Host/DB reflection,
fresh task-state read and nonduplicated controller-driven continuation were
observed. Explicit handoff receipt was PARTIAL in that Probe; barrier, race and restart
capabilities were not accepted. This is not interactive terminal acceptance or
Strong Transition Assurance.

The completion predicate was checked locally against saved Probe metadata and
synthetic negatives. Historical Probe source associations and verdicts are preserved.

The Stage 4 adapter then completed one new bounded live synthetic-task run with
nine provider requests (4 before, 1 compression, 4 continuation), one manual
compression and Core `RESUME_VERIFIED`. Existing durable checkpoint and handoff
files were connected. The runtime issued an explicit assistant tool receipt
containing handoff/checkpoint/request/session/generation identity and checkpoint
checksum; independent post-run DB readback confirmed its arguments and result.
Fresh state was read after receipt; A and B executed once each. Completion still
uses the Stage 3 policy, not a new predicate. Bounded workflow and this explicit
adapter receipt: PASS; overall CoverageProfile: PARTIAL.

That Stage 4 run used Python 3.11.16 with copied source and retained the then-current
Python >=3.14 package requirement; its local checks used Python 3.14.4.
The explicit receipt is an adapter-defined protocol over native tool calls,
not a built-in Hermes acknowledgement. General tool coverage, Hook-fault safety,
races, background/parallel work, restart, late completion, repeated compression
and live selected-archive retrieval remain unaccepted. See the
[Hermes integration reference](reference/hermes.md) for required host wiring.

## Claude Code Ollama local maintainer testing profile

Reviewed 2026-09-29. This is a separate **maintainer / local-live / synthetic**
control-plane testing profile. Its maturity remains **experimental**, evidence
level is **lab tested**, and overall verdict is **PARTIAL**.

| Dimension | Fixed scope |
|---|---|
| Profile ID | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` |
| Runtime / OS / surface | Claude Code CLI `2.1.280` / Linux / `claude -p` / stream-json / synchronous command Hooks |
| Backend | Ollama local client and server `0.34.1`, loopback upstream |
| Model | `spark-x2.5-4b-uncensored:latest`, 4.1B, `Q4_K_M` |
| Model digest | `e1646156c20479fe89690bad3f6a38062f4888cc33e03fcbb7a4944556be417f` |
| Source | Product `e50455e7adef26b6609731ac3b6d45724ca64bd1`; adapter implementation `8ffc81b17876e94418a6d618f3c9c9284816cb41` |
| Bounds | 300-second owner deadline; 4096 output tokens per inference request including compact; max turns 6; inference request ceiling 20 |
| Ownership / tools | Fresh exclusive session, single writer, sequential foreground Bash fixture commands, one manual compact and one recovery input in the same CLI process |
| Backend context | Observed 131072; model metadata maximum is a separate value |
| Evidence record | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29`; private workspace retains profile, coverage, source snapshots and hashed records |
| Regression use | Conditional manual maintainer testing with evidence review; not accepted as a required automated pass/fail gate |

The earlier `recovery-04` reached **RESUME_VERIFIED** in 294.11 seconds using
7 local inference requests. Delivery, explicit handoff/checkpoint receipt,
fresh observation, token-bound continuation and task-specific assessment each
had separate evidence. Counters were before=1, after=1, stale=0. Its bounded
workflow **PASS** is retained.

Exactly one additional attempt, `recovery-05`, used matching runtime binaries,
model digest, runner and adapter source, prompts and bounds. It stopped in
11.66 seconds after 1 inference request: the model's first structured Bash call
omitted the required `before` argument. The owner rejected it with
`UNEXPECTED_COMMAND` / `CLIENT_REJECTED`; all fixture counters remained zero.
The adapter had not yet been constructed, so its state was null, and compact,
receipt and recovery stages were **NOT_RUN**. This attempt's workflow and the
successful-reproduction check are **FAIL**. The observed defect is in the emitted
command; a Runtime protocol or adapter recovery defect was not established.

Both attempts configured 4096 output tokens. The earlier compact response reported
4026 output tokens; the repeat never requested compact. The shorter failed run
is not a performance improvement. The earlier total time was only 5.89 seconds
below the nominal owner deadline; stage timings were not recorded. IPC and process
cleanup have separate grace periods. Sampling seed, host load and cache state
were not controlled. One success and one failure do not establish reliability.

Completion still accepts either order of SessionStart(compact) and PostCompact.
Missing, stale, duplicate or inconsistent completion proof must stop recovery;
a terminal success or later action alone cannot establish receipt or resume.
Historical local normal-deny evidence and offline negative fixtures retain their
own scope. The new pre-adapter rejection does not prove Hook-fault enforcement.
Hook-fault safety, background/subagent work, restart, general task semantics and
Agent SDK are outside this testing profile. Neither the Anthropic subscription
profile's evidence/verdicts nor Claude Code-wide support are upgraded by these
local records. No release channel is declared.

## MiMo local maintainer model-comparison profile

Reviewed 2026-09-29, independently of the Spark profile above. The actual local
model was `MiMo-V2.6-Distill-Qwen-9B-Ablitrated:latest` (local spelling retained),
9.0B, `Q4_K_M`, digest
`616953773b51de179551c7430e3877ea6af9aedaf533e4cc684465e107c2e990`.
Ollama client/server remained `0.34.1`; Claude Code CLI remained `2.1.280` on
Linux with `claude -p`, stream-json and synchronous command Hooks. Evidence is
**maintainer / local-live / synthetic**, maturity **experimental**, overall
**PARTIAL**. Record: `C-CLI-OLLAMA-MIMO-COMPARE-2026-09-29`.

The comparison imported the original Spark runner and fixture at the same paths.
Binary and source hashes matched; only model selection, isolated output paths
and saved model identity changed. Workflow, fixture prompts, adapter, completion
policy, 300-second owner deadline, 4096 output cap, max turns 6 and inference
request bound 20 were unchanged. Both runs observed backend context 131072.

| Fixed-workflow run | Initial command fidelity | Compact / receipt / resume | Inference requests | Elapsed |
|---|---|---|---|---|
| Spark `recovery-04` (retained) | PASS, then all recovery calls accepted | PASS / PASS / RESUME_VERIFIED | 7 | 294.11 s |
| Spark `recovery-05` (retained) | FAIL | NOT_RUN | 1 | 11.66 s |
| MiMo `recovery-01` | FAIL | NOT_RUN | 1 | 30.12 s |
| MiMo `recovery-02` | FAIL | NOT_RUN | 2 | 83.85 s |

Exactly two MiMo attempts ran. Both omitted required `tool before` arguments in
the first Bash command. The owner rejected both before fixture execution or
adapter construction; counters stayed zero and Core state remained null.
Both bounded workflow attempts are **FAIL**; completion proof, explicit receipt,
fresh observation, continuation and resume verification remain **NOT_RUN**.
The second run also recorded an upstream stream `TimeoutError`, followed by a
nonstream request within the same CLI run. Its error annotation is not a third
inference request. That transport failure's cause is unknown and is recorded
separately from the emitted-command defect; no adapter recovery defect was
established.

**MiMo is not accepted as the primary maintainer regression profile.** Retain
Spark unchanged for optional low-resource/stress diagnostics, with its existing
manual-review requirement. Neither profile is accepted as a required automated
gate. Failed-run times do not measure recovery speed. Two observations per model
cannot establish general reliability or quality rankings; host load, seed and
warm state were not controlled. No official model benchmark is used to infer
quality of this local quantized derivative. Existing Spark and Anthropic
subscription evidence/verdicts, product adapter behavior and release status
remain unchanged.

## Qwen local maintainer model-comparison profile

The additional 2026-09-29 profile used
`hf.co/mradermacher/Qwen3.5-4B-abliterated-GGUF:Q4_K_M`, digest
`4ce045509cfbf9e700a3fa99bcccf93b0b4ad1ff46511294d97598ea7c62c13f`,
4.21B. Both `/api/tags` and `/api/show` reported `Q4_K_M`; `/api/ps`
reported quantization `unknown` for the same digest, which is preserved as an
observation. Ollama client/server `0.34.1`, Claude Code CLI `2.1.280` / Linux /
`claude -p` / stream-json / synchronous command Hooks, the original Spark runner,
fixture, prompts, adapter and evidence conditions were unchanged. The bounds
remained 300 seconds, 4096 output tokens, max turns 6 and 20 inference requests.
Both runs observed context 131072. Provenance is **maintainer / local-live /
synthetic**, maturity **experimental**, overall **PARTIAL**. Record:
`C-CLI-OLLAMA-QWEN-COMPARE-2026-09-29`.

Exactly two attempts ran: `recovery-01` took 189.89 seconds and `recovery-02`
179.84 seconds, each with 11 local inference requests. All requests returned
HTTP 500; the saved CLI error was `Jinja Exception: System message must be at
the beginning.` Both workflow attempts are **FAIL**. No assistant tool calls
occurred: command/argument fidelity, compaction, completion proof, receipt,
fresh observation, continuation and resume verification are **NOT_RUN**.
The adapter was never constructed and fixture counters remained zero.

This is a backend/model-template message-compatibility failure in the fixed
configuration, not an evaluated failure of model tool semantics. No template,
message or prompt correction was made. CLI-internal repeated requests are counted
as requests within each attempt, not extra owner workflow runs. Failed-run times
are not recovery or generation-speed measurements.

**Qwen is not accepted as the primary maintainer regression profile.** Together
with the separate MiMo failures, this comparison provides no basis to replace
Spark as the optional low-resource/stress diagnostic profile. All three remain
unaccepted as required automated gates. Previous profile verdicts and product
adapter code remain unchanged; official model benchmarks are not transferred to
these local derivatives.

## qwen3.5:4b local maintainer retry profile

The separate 2026-09-29 retry used `qwen3.5:4b`, digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`,
Q4_K_M (metadata parameter size 4.7B), on Ollama client/server 0.34.1.
Claude Code 2.1.280/Linux/`claude -p`/stream-json/command Hooks, original runner,
fixture, prompts, adapter and explicit bounds were unchanged: 300 seconds,
4096 output tokens, max turns 6, inference request ceiling 20. Effective context
was observed at 32768, unlike 131072 in the earlier profiles; no context override
was added and the cause of that difference was not established. This is not a
strict weights-only causal comparison. Provenance is maintainer/local-live/synthetic,
maturity experimental, overall PARTIAL.

Both attempts reached manual completion and handoff submission: 33.19 and 30.20
seconds, four local inference requests each. The saved completion proofs passed
replay through the unchanged policy, including either order of the two post-compact
hooks. Explicit receipts failed independently: the first run's receipt call omitted one
character from `session_id` (36 to 35 characters), the second from `handoff_hash`
(64 to 63). Command syntax was valid, but receipt argument fidelity was **FAIL**.
The owner rejected both and ended in RECOVERY_REQUIRED with counters 1/0/0.
Fresh observation, continuation and RESUME_VERIFIED remain **NOT_RUN**.

Both bounded workflows are **FAIL**. This profile is not accepted as the primary
recovery regression profile or required automated gate; it can support conditional
manual completion/rejected-receipt diagnostics. Raw collector `explicit_receipt`
flags remain unchanged; separate reviews record attempted-but-rejected receipts
as FAIL. No HTTP 500 occurred in these two runs, which does not revise the earlier
Abliterated profile. Failed-run elapsed times are not completed recovery speed.
Product code, previous profile verdicts and subscription evidence are unchanged.
Record: `C-CLI-OLLAMA-QWEN35-4B-2026-09-29`.

## qwen3.5:9b local maintainer comparison profile

The separate 2026-09-29 profile used `qwen3.5:9b`, digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`,
Q4_K_M (metadata parameter size 9.7B), on Ollama client/server 0.34.1.
Claude Code CLI 2.1.280/Linux/`claude -p`/stream-json/command Hooks, the original
Spark runner, fixture, prompts, adapter and acceptance conditions were unchanged.
Bounds remained 300 seconds, 4096 output tokens, max turns 6 and 20 inference
requests. Both runs observed context 32768, matching `qwen3.5:4b`; earlier
profiles observed 131072. Host load, cache, seed and memory placement were not
controlled. Provenance is maintainer/local-live/synthetic, maturity experimental,
overall **PARTIAL**. Record: `C-CLI-OLLAMA-QWEN35-9B-2026-09-29`.

Exactly two attempts ran. The first took 113.89 seconds and four inference
requests: completion and handoff submission passed, but the model's explicit
receipt had an incorrect `session_id` (39 characters instead of the expected 36).
The owner rejected it and stopped in RECOVERY_REQUIRED, with counters 1/0/0.
Its workflow is FAIL; fresh observation through resume verification are NOT_RUN.
Raw collector evidence is retained, with attempted receipt failure classified
separately from the absence of an accepted receipt.

The second took 128.37 seconds and seven inference requests and reached
**RESUME_VERIFIED**. Independent receipt, fresh observation, controller-driven
continuation and task-specific assessment passed, with counters 1/1/0 and no
issues. This is a **PASS for this bounded synthetic run only**. Both saved
completion proofs passed the unchanged policy; either order of the two
post-compact hooks remains valid. Compact responses reported 1269 and 1001
output tokens respectively, below the unchanged 4096 bound.

One success out of two does not establish repeatability. This profile is a
conditional manual recovery regression candidate, not an accepted primary
profile or required automated gate. Spark remains an unchanged optional
low-resource/stress diagnostic. No product code or previous profile verdicts
changed; the local success does not extend Anthropic subscription coverage.

## Installation compatibility

The later installation change lowers the package minimum to Python 3.11 and
uses one normal wheel in both host environments. No Core, adapter, completion
policy or saved-data format changed. The package has no runtime dependencies;
Hermes remains an existing host installation with its own dependencies.

| Check | Evidence |
|---|---|
| Clean wheel install | PASS on CPython 3.11.16 and 3.14.4; non-editable, isolated venv, outside the source checkout |
| Python floor regression | 124 local tests on 3.11.16, including all existing modules because the interpreter floor affects the whole package |
| Existing interpreter regression | 40 selected tests on 3.14.4 covering configuration, completion, persistence, work/Hook, recovery, archive and Hermes adapter |
| Codex saved-format compatibility | 16 snapshots and 17 durable files match the retained baseline on both interpreters |
| Activation | Default disabled; enabled real owner construction; disabled startup creates no Yohaku owner/store/Hooks in the tested host wiring |
| Hermes actual venv | Same wheel installed under site-packages; existing dependency versions unchanged; pip check PASS |
| Installed Hermes preparation | Native offline route preflight and synthetic-response H-CLI-01 rehearsal PASS, RESUME_VERIFIED, zero provider requests |
| New live acceptance | NOT_RUN for the installed wheel; historical Stage 4 live scope retained |

See [installation and startup configuration](installation.md). Wheel distribution
and startup opt-in are available; a general end-user host launcher and a release
profile/decision are still required before declaring an Alpha. CPython 3.12/3.13,
other interpreters and other OS installation matrices remain NOT_RUN.

Dated documentation/source research can identify candidate control points. Before
implementation, each probe must fix runtime and SDK versions, surface, provider,
permissions, tools, ownership, storage, cost bounds, strategy, and stop conditions.
Actual completion, receipt, current-state reconciliation, and negative cases must
be observed for that profile. Candidate APIs and runtime-native primitives alone
do not establish Yohaku support.


### C-CLI host-bound nonce receipt maintainer profile

A separate opt-in `ClaudeCLINonceRecoveryAdapter` profile uses a single 128-bit
challenge response while the trusted host retains and checks all handoff,
checkpoint, request, session, attachment, generation and continuation identities.
The original full-identity echo adapter and all earlier verdicts remain unchanged.
Native admission, matching handler/PostToolUse result, fresh observation and an
independent task assessor remain mandatory. A no-argument or automatic ACK is not
accepted. This is restricted to one exclusive owner and one pending handoff.

On Claude Code CLI 2.1.280 / Linux / `claude -p` / stream-json / command Hooks,
Ollama 0.34.1 and `qwen3.5:9b` Q4_K_M (digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`), one
maintainer/local-live/synthetic run at context 32768 reached **RESUME_VERIFIED**
in **100.01 seconds / 7 inference requests**. Actual nonce arguments, the submitted
handoff prompt, durable receipt/read/action records and task effects were reviewed
independently. Counters were before=1, after=1, stale=0; issues were empty. The
fixed bounded workflow is **PASS**, overall **PARTIAL**. Repeated-run reliability
and primary regression-gate adoption remain unestablished.

An earlier attempt after backend startup used context 4096, ended AMBIGUOUS after
PreCompact only (28.61 seconds / 6 requests), and never reached receipt. It is
retained but excluded from the same-condition comparison. The corrected run used
a fresh session and checked context before compact; no old owner/request resumed.
The 300-second owner bound, 4096 output cap, 6 turns, 20-request ceiling and original
fixture were preserved. Only receipt arguments changed in the recovery prompt.
No speed or reliability improvement is inferred from this single comparable run.

Local tests reject missing, stale, duplicate, foreign-owner and mismatched identity
or result evidence. Tool success does not establish semantic result incorporation;
the fresh-read token and task assessment remain independent. This profile does not
promote Anthropic subscription evidence or Claude Code as a whole to PASS. See the
[nonce receipt contract](reference/claude-cli.md#opt-in-host-bound-nonce-receipt).
