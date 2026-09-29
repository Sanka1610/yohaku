# Codex `document-review-report-v1`

> **Historical / compatibility reference:** Current public canonicalは
> [Task Profile: `document-review-report-v1`](../task-profiles/document-review-report-v1.md)である。
> 本pathは既存linkとretained Evidenceの参照を維持するため残している。

`document-review-report-v1` is Yohaku's first nonfixture Real-task Profile. It
reviews an explicitly declared set of UTF-8 text documents and creates one fixed
Markdown report. It is not a general document, filesystem, shell or coding profile.

## Fixed Support Profile

| Field | Accepted value |
|---|---|
| Runtime | Codex CLI `0.158.0-alpha.2.1` |
| Surface | Dedicated App Server over stdio |
| Platform / Python | WSL2 Linux / CPython `3.14.4` |
| Strategy | One proactive manual compact |
| Task tools | `read_review_inputs`, `publish_review_report` |
| Output | One absent-at-start Markdown path, created exactly once |
| Restart | Unsupported; retained state is inspect-only |
| Writing quality | `NOT_ASSESSED` |
| Evidence | `DRR-V1-CODEX-0158-LIVE-01`, bounded workflow PASS |

The Runtime was selected because the current operational Codex path already has
a dedicated App Server, durable checkpoint, manual completion policy, SessionStart
handoff receipt and resume verifier. The pinned Hermes operational launcher does
not activate its inference agent or transition adapter, so a Hermes implementation
would require a separate Runtime wiring and acceptance effort. This choice does
not rank the Runtimes or transfer Codex Evidence to Hermes.

## Task contract

Configuration binds absolute input paths, one absolute output path, the review
instruction, workspace, Runtime executable, existing credential home and a new
state root. The workspace must be mode 0700, contain only the declared mode-0600
regular input files, and contain no output at preflight. Symlinks, duplicate
inputs, undeclared files and paths outside the workspace are rejected.

The state root is separate from the workspace. It stores the Core journal,
checkpoint, handoff, task ledger and projected Runtime event metadata. Input and
report bodies are not copied into the Evidence ledger. The report itself remains
the task output.

## Observer and assessor

The trusted observer records these values:

- input relative path, byte count and SHA-256;
- instruction SHA-256;
- output existence and SHA-256;
- read completion and count;
- write start, durable completion and Runtime result incorporation;
- active and pending task operations;
- workspace mutation epoch, stamp and declared relevant scope.

The initial read must be incorporated with no active or pending work before the
Controller verifies the boundary. After compaction, the continuation must perform
one fresh read before publishing. Both reads must match the configured input
identities. The report includes a host-generated provenance comment containing
the accepted input and instruction hashes.

The assessor accepts only one successful fresh-read item and one successful
publish item from the continuation turn. It rejects any command, file-change or
MCP item; stale instruction/input/output; missing result incorporation; changed
workspace; duplicate write; or remaining active/pending work. These conditions
establish mechanical completion, not the correctness or editorial quality of the
report text.

## Transition and failure behavior

The accepted sequence is:

```text
real task → verified boundary → checkpoint → Codex manual compact
  → handoff → explicit receipt → fresh workspace observation
  → non-duplicate continuation → RESUME_VERIFIED
```

Codex manual completion still requires the correlated compaction item,
PostCompact Hook and compact turn. RPC acknowledgement is not completion.
SessionStart delivers the durable handoff, and the continuation must emit its
exact receipt marker before task assessment.

`publish_review_report` uses exclusive create, file sync, directory sync and
readback hashing. Once a write starts, any unknown or mismatched result blocks
retry. A completed output makes later preflight fail with `STALE_OUTPUT_PRESENT`.
Compact or continuation uncertainty keeps the run `AMBIGUOUS`; Yohaku does not
blindly resend either operation.

## Evidence boundary

The retained live run used two public Yohaku documents and produced one review
report. It reached `RESUME_VERIFIED`, performed two total reads, one report write,
and ended with active/pending zero. No command, file-change or MCP Runtime item was
observed. A repeated run was refused without changing the output.

This is lab/live-runtime Evidence for one real task. It does not establish Field
Evidence, prose-quality acceptance, arbitrary input formats, external-writer
exclusion, crash recovery, repeated transitions, another Codex version, another
Runtime, general document processing or coding-task coverage. The profile remains
experimental, the release channel remains undeclared, and overall product coverage
remains PARTIAL.
