"""Optional, deterministic presentation of existing historical task facts."""

import json

from .codec import encode


def build_task_context(document, *, checkpoint=None, constraints=(), archives=()):
    """Render selected facts only; callers own source selection and knownness.

    Constraints are (verbatim text, source reference) pairs. Archives must be
    already selected/loaded ArchiveTurn records referenced by this handoff.
    Nothing here reads storage, assesses work or grants continuation authority.
    """
    recovered = document.recovered

    def quote(value):
        return json.dumps(value, ensure_ascii=False)

    lines = ["Historical task context (source: this handoff's recovered fields)"]

    def section(title, values):
        values = tuple(dict.fromkeys(value for value in values if value))
        if values:
            lines.append(title + ":")
            lines.extend("- " + value for value in values)

    def sourced(value, reference):
        return quote(value) + (" [source: " + quote(reference) + "]" if reference else "")

    section("Goal (goal_summary)", (quote(recovered.goal_summary),)
            if recovered.goal_summary else ())
    if len(constraints) > 16 or len(archives) > 4:
        raise ValueError("select a bounded set of task sources")
    section("Constraints (source wording)", (sourced(value, ref) for value, ref in constraints))
    section("Completed (completed_work)", map(quote, recovered.completed_work))
    section("Unresolved", map(quote, recovered.unresolved))
    verification, decisions, references = [], [], []
    if checkpoint is not None:
        if (checkpoint.checkpoint_id != document.request.checkpoint_id
                or checkpoint.revisions != document.revisions
                or checkpoint.workspace != document.workspace):
            raise ValueError("checkpoint does not belong to historical handoff")
        v = checkpoint.verification
        verification.append(sourced(
            f"profile={v.profile}; verification={v.verification}", v.evidence_ref))
    for archive in archives:
        ident = archive.metadata.archive_id
        if ident not in recovered.archive_ids:
            raise ValueError("archive is not referenced by this handoff")
        ref = "archive:" + ident
        if archive.verification_summary:
            verification.append(sourced(archive.verification_summary, ref + "#verification_summary"))
        decisions.extend(sourced(value, ref + "#decisions") for value in archive.decisions)
        references.extend(sourced(value, ref + "#references") for value in archive.references)
    section("Verification (historical source; not task/resume completion)",
            verification)
    section("Decisions / reasons (source wording)", decisions)
    section("Next action candidate (requires fresh reconciliation)",
            (quote(recovered.next_action_candidate),) if recovered.next_action_candidate else ())
    if recovered.emergency is not None:
        # Keep observations and pending work separate from recorded completion.
        section("Emergency observation (emergency; unverified)",
                (quote(encode(recovered.emergency)),))
    section("References", (
        *(quote(value) for value in recovered.workspace_references),
        *("archive:" + value for value in recovered.archive_ids),
        *references,
    ))
    text = "\n".join(lines)
    legacy = json.dumps(document.storage_payload()["recovered"], ensure_ascii=False)
    # Never truncate a qualification, unresolved item, or constraint mid-sentence.
    # Oversized presentation falls back to the complete existing representation.
    if len(text.encode()) > min(16384, len(legacy.encode()) + 2048):
        raise ValueError("structured task context exceeds presentation budget")
    return text
