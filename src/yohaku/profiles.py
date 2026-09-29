"""Reviewed profiles; operational evidence never grants transition authority."""

from copy import deepcopy
from .hermes import HERMES_SOURCE

MISSING_TASK = 'TASK_PROFILE_REQUIRED: trusted observer and assessor are not installed'
COMMON_LIMITS = [MISSING_TASK, 'No task input, automatic transition or RESUME_VERIFIED in this launcher',
                 'Fresh dedicated sessions only; no existing-session attachment',
                 'Local owner lock does not exclude other runtime clients or external writers']


def _profile(runtime, version, surface, *, launch=False, evidence='lab tested / historical synthetic',
             verdict='PARTIAL', limitations=(), transition=False, transition_reason=MISSING_TASK,
             **extra):
    return dict(runtime=runtime, runtime_version=version, surface=surface,
                operational_platform='WSL2 Linux',
                operational_python='3.11.16' if runtime == 'hermes' else '3.14.4',
                reviewed='2026-09-29',
                maturity='experimental', release_channel='undeclared', launch_supported=launch,
                evidence_level=evidence, verdict=verdict, transition_available=transition,
                transition_reason=transition_reason,
                known_limitations=([] if transition else COMMON_LIMITS) + list(limitations), **extra)


PROFILES = {
    'codex-document-review-report-v1': _profile('codex', '0.158.0-alpha.2.1',
        'dedicated App Server / dynamic task tools / manual compact',
        launch=True, evidence='lab / live-runtime / real task', verdict='PASS',
        evidence_scope=('One dedicated workspace, two declared public-document inputs, one manual '
                        'compact and one create-only Markdown report; overall product coverage PARTIAL'),
        evidence_id='DRR-V1-CODEX-0158-LIVE-01', task_profile='document-review-report-v1',
        entrypoint='run', transition=True, transition_reason=None,
        limitations=['Only declared UTF-8 Markdown/text inputs and one create-only Markdown output',
                     'Writing quality is NOT_ASSESSED; only mechanical completion is assessed',
                     'One fresh session, one manual compact and one report write; restart unsupported',
                     'A directory lock excludes cooperating launchers; external writers are detected, not prevented',
                     'No coverage for general document tasks, coding, shell, MCP or other Runtimes']),
    'codex-operational-0.158': _profile('codex', '0.158.0-alpha.2.1', 'dedicated App Server / stdio',
        launch=True, evidence='lab tested / native lifecycle / no inference', verdict='PASS',
        evidence_scope='Operational lifecycle only; real-task transition NOT_RUN',
        evidence_id='S5-OP-CODEX-0158', reference_profile='codex-reference-0.155',
        reference_evidence_applies=False,
        limitations=['No trusted task hooks or work observer registered; no turn dispatch',
                     'No inference credentials loaded; loopback disabled provider only']),
    'codex-reference-0.155': _profile('codex', '0.155.0-alpha.16.4', 'WSL2 / dedicated App Server',
        evidence_id='PHASE14',
        limitations=['Historical reference only; no operational launcher acceptance for this version',
                     'Hook faults can FAIL_OPEN; no runtime-wide atomic freeze',
                     'Native recovery restart UNSUPPORTED; repeated compact and parallel work NOT_RUN']),
    'hermes-operational-h-cli-01': _profile('hermes', '0.21.0', 'pinned native HermesCLI / in-process',
        launch=True, evidence='lab tested / native lifecycle / no inference', verdict='PASS',
        evidence_scope='Native CLI construction and storage lifecycle only; lazy inference agent is not initialized',
        evidence_id='S5-OP-HERMES', source_commit=HERMES_SOURCE,
        reference_profile='hermes-h-cli-01', reference_evidence_applies=False,
        limitations=['No inference agent, task tool or transition adapter is activated',
                     'No native chat, compress, tools, background work or provider requests',
                     'Interrupted owner resume UNSUPPORTED; keep native DB and Yohaku records']),
    'hermes-h-cli-01': _profile('hermes', '0.21.0', 'instrumented native HermesCLI',
        source_commit=HERMES_SOURCE, evidence_id='H-CLI-01-STAGE4',
        limitations=['Historical single fixture tool, one manual compression, one fresh owner',
                     'General shell/editing and visible archive collector are not accepted',
                     'Restart, repeated transitions, races and parallel work are not accepted']),
    'claude-c-cli': _profile('claude', '2.1.280', 'claude -p / stream-json / synchronous command Hooks',
        evidence='external / live-runtime / synthetic', evidence_id='C-CLI-COMPLETION',
        limitations=['Manual completion bounded PASS; subscription recovery live acceptance NOT_RUN',
                     'Operational launcher not supplied; not Claude-wide Alpha support']),
    'claude-c-cli-local-nonce': _profile('claude', '2.1.280', 'maintainer / Ollama 0.34.1 / qwen3.5:9b',
        evidence='maintainer / local-live / synthetic', evidence_id='C-CLI-NONCE-QWEN35-9B',
        limitations=['One bounded nonce receipt recovery PASS; overall PARTIAL',
                     'Fixture-specific assessor; not a general task profile',
                     'Not subscription acceptance, a primary regression gate or Claude-wide Alpha support']),
}

_CANDIDATE_A = {'codex-operational-0.158', 'codex-document-review-report-v1'}


def profile(name):
    if name not in PROFILES:
        raise ValueError('UNKNOWN_PROFILE')
    details = deepcopy(PROFILES[name])
    if name in _CANDIDATE_A:
        details['task_profile_registered'] = details.pop('transition_available')
    return dict(id=name, **details)
