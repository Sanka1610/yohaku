"""Profile configuration and bounded support information."""

from copy import deepcopy
from .hermes import HERMES_SOURCE

MISSING_TASK = 'TASK_PROFILE_REQUIRED: trusted observer and assessor are not installed'
COMMON_LIMITS = [MISSING_TASK, 'No task input, automatic transition or RESUME_VERIFIED in this launcher',
                 'Fresh dedicated sessions only; no existing-session attachment',
                 'Local owner lock does not exclude other runtime clients or external writers']


def _profile(runtime, version, surface, *, launch=False, workflow, limitations=(),
             transition=False, transition_reason=MISSING_TASK, status='experimental', **extra):
    return dict(runtime=runtime, runtime_version=version, surface=surface, status=status,
                tested_environment=dict(os='WSL2 Linux' if runtime != 'claude' else 'Linux',
                    python='3.11.16' if runtime == 'hermes' else '3.14.4' if runtime == 'codex' else 'not recorded'),
                tested_workflow=workflow, launch_supported=launch, transition_available=transition,
                transition_reason=transition_reason,
                known_limitations=([] if transition else COMMON_LIMITS) + list(limitations), **extra)


PROFILES = {
    'codex-document-review-report-v1': _profile('codex', '0.158.0-alpha.2.1',
        'dedicated App Server / dynamic task tools / manual compact',
        status='alpha',
        launch=True,
        workflow='Two public-document inputs, one manual compact, one create-only report: RESUME_VERIFIED',
        task_profile='document-review-report-v1',
        entrypoint='run', transition=True, transition_reason=None,
        limitations=['Only declared UTF-8 Markdown/text inputs and one create-only Markdown output',
                     'Writing quality is NOT_ASSESSED; only mechanical completion is assessed',
                     'One fresh session, one manual compact and one report write; restart unsupported',
                     'A directory lock excludes cooperating launchers; external writers are detected, not prevented',
                     'No coverage for general document tasks, coding, shell, MCP or other Runtimes']),
    'codex-operational-0.158': _profile('codex', '0.158.0-alpha.2.1', 'dedicated App Server / stdio',
        status='alpha',
        launch=True, workflow='Start / status / stop / fresh lifecycle; no inference',
        limitations=['No trusted task hooks or work observer registered; no turn dispatch',
                     'No inference credentials loaded; loopback disabled provider only']),
    'codex-reference-0.155': _profile('codex', '0.155.0-alpha.16.4', 'WSL2 / dedicated App Server',
        workflow='Historical manual scenarios and one native-auto recovery; partial coverage',
        limitations=['Historical reference only; no operational launcher acceptance for this version',
                     'Hook faults can FAIL_OPEN; no runtime-wide atomic freeze',
                     'Native recovery restart UNSUPPORTED; repeated compact and parallel work NOT_RUN']),
    'hermes-operational-h-cli-01': _profile('hermes', '0.21.0', 'pinned native HermesCLI / in-process',
        launch=True, workflow='Native CLI / DB / store lifecycle; no inference',
        source_commit=HERMES_SOURCE,
        limitations=['No inference agent, task tool or transition adapter is activated',
                     'No native chat, compress, tools, background work or provider requests',
                     'Interrupted owner resume UNSUPPORTED; keep native DB and Yohaku records']),
    'hermes-h-cli-01': _profile('hermes', '0.21.0', 'instrumented native HermesCLI',
        source_commit=HERMES_SOURCE,
        workflow='Single fixture tool, one compression, receipt and fresh continuation: RESUME_VERIFIED',
        limitations=['Historical single fixture tool, one manual compression, one fresh owner',
                     'General shell/editing and visible archive collector are not accepted',
                     'Restart, repeated transitions, races and parallel work are not accepted']),
    'claude-c-cli': _profile('claude', '2.1.280', 'claude -p / stream-json / synchronous command Hooks',
        workflow='Subscription manual completion: ROLLOVER_OBSERVED; subscription recovery NOT_RUN',
        limitations=['Manual completion bounded PASS; subscription recovery live acceptance NOT_RUN',
                     'Operational launcher not supplied; not Claude-wide Alpha support']),
    'claude-c-cli-local-nonce': _profile('claude', '2.1.280', 'maintainer / Ollama 0.34.1 / qwen3.5:9b',
        workflow='One bounded host-nonce-v1 fixture recovery: RESUME_VERIFIED',
        limitations=['One bounded nonce receipt recovery PASS; overall PARTIAL',
                     'Fixture-specific assessor; not a general task profile',
                     'Not subscription acceptance, a primary regression gate or Claude-wide Alpha support']),
}


def profile(name):
    if name not in PROFILES:
        raise ValueError('UNKNOWN_PROFILE')
    details = deepcopy(PROFILES[name])
    if details['runtime'] == 'codex' and details['launch_supported']:
        details['task_profile_registered'] = details.pop('transition_available')
    return dict(id=name, **details)
