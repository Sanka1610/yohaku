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
Claude Desktop and Cowork are Research / Auxiliary surfaces. Non-Codex adapters
beyond the bounded Hermes profile remain unimplemented. Claude Code's reviewed
documentation/source contracts are design inputs; its live acceptance remains NOT_RUN.

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

The host used Python 3.11.16 with copied source; local checks used Python 3.14.4.
This does not change the package's Python >=3.14 installation requirement.
The explicit receipt is an adapter-defined protocol over native tool calls,
not a built-in Hermes acknowledgement. General tool coverage, Hook-fault safety,
races, background/parallel work, restart, late completion, repeated compression
and live selected-archive retrieval remain unaccepted. See the
[Hermes integration reference](reference/hermes.md) for required host wiring.

Dated documentation/source research can identify candidate control points. Before
implementation, each probe must fix runtime and SDK versions, surface, provider,
permissions, tools, ownership, storage, cost bounds, strategy, and stop conditions.
Actual completion, receipt, current-state reconciliation, and negative cases must
be observed for that profile. Candidate APIs and runtime-native primitives alone
do not establish Yohaku support.
