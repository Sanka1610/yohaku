"""Offline release-claim consistency check, deliberately limited to Candidate A.

No Runtime invocation, private material ingestion, or Capability Verdict scoring.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from yohaku.profiles import CANDIDATE_A, PROFILES  # noqa: E402

BASE = '84b34f8eff42d5b2a46b9ce1b38913a35bd8f25b'
ACCEPTED = '76c086cc4381af9488fb511a191b899d7279f0af'
OP_SOURCE = '92a82de662672240ca3b57bc8e498eeaf250a5f2'
DATA = 'docs/release'
IDS = ['codex-operational-0.158', 'codex-document-review-report-v1']
EXCLUDED = ['codex-reference-0.155', 'hermes-operational-h-cli-01',
            'hermes-h-cli-01', 'claude-c-cli', 'claude-c-cli-local-nonce']
LIMITS = ['no-runtime-family-support', 'no-field-evidence', 'no-other-runtime-os-provider',
          'no-general-parallel-background-external-work', 'no-strong-transition-assurance']
OP_LIMITS = LIMITS + ['no-inference-or-task-transition', 'no-reference-evidence-inheritance']
DRR_LIMITS = LIMITS + ['one-fresh-session-one-manual-compact-one-report',
                     'no-restart-or-repeated-transition', 'quality-not-assessed',
                     'no-general-document-coding-shell-mcp', 'external-writers-not-prevented']
REGISTRY_LIMITS = [
    '661d3dbbab36b40c9e43c0558a6f5a5a22fb43f66e6f589f3fa597fae9b795f1',
    '1b743f492ea437e6986b2874c029f407e9a6c8d56bd71c6a96bb4a47ec218856',
]
HASH = '<sha256>'
LICENSE_SHA256 = 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'
DOCS = ['docs/runtime-support.md', 'docs/runtime-mapping.md', 'docs/runtimes/codex.md']
TASK_DOC = 'docs/task-profiles/document-review-report-v1.md'
POLICY = 'SUPPORT_POLICY.md'
TRACKED = [
    'src/yohaku/document_review.py', 'src/yohaku/document_review_runtime.py',
    'src/yohaku/recovery.py', 'src/yohaku/operational.py', 'src/yohaku/cli.py',
    'src/yohaku/profiles.py', 'tests/test_document_review.py',
    'tests/test_document_review_runtime.py', 'README.md', 'SUPPORT_POLICY.md',
    'docs/architecture.md', 'docs/operations.md', 'docs/runtime-support.md',
    'docs/reference/document-review-report-v1.md',
]
# Dependencies outside the original task manifest, reviewed against its source commit.
DEPENDENCIES = [f'src/yohaku/{name}.py' for name in (
    '__init__', '__main__', 'codex', 'companion', 'completion', 'config', 'controller',
    'codec', 'hook', 'manual', 'model', 'native', 'operational_hosts', 'persistence',
    'runtime', 'work')]


class Invalid(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise Invalid(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_bytes(root, commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=root,
                                   stderr=subprocess.DEVNULL)


def public_shape(value, expected):
    """Closed keys and literal values; only SHA-256 fields accept variable text.

    Never include rejected values, field names, or exception bodies in diagnostics.
    """
    if expected == HASH:
        require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'PUBLIC_HASH')
    elif isinstance(expected, dict):
        require(type(value) is dict and value.keys() == expected.keys(), 'PUBLIC_FIELDS')
        for key in expected:
            public_shape(value[key], expected[key])
    elif isinstance(expected, list):
        require(type(value) is list and len(value) == len(expected), 'PUBLIC_LIST')
        for actual, wanted in zip(value, expected):
            public_shape(actual, wanted)
    else:
        require(type(value) is type(expected) and value == expected, 'PUBLIC_VALUE')


def claims():
    return [dict(mapping_key=key, support_profile_id=pid, runtime_family='codex',
                 runtime_exact_version='0.158.0-alpha.2.1', surface=surface,
                 task_profile_id=task, operational_launcher_support=True,
                 task_runner_support=bool(task), maturity='experimental',
                 release_channel='undeclared', accepted_endpoint=endpoint,
                 evidence_record_id=eid, known_exclusions=limits)
            for key, pid, surface, task, endpoint, eid, limits in [
                ('C-OP', IDS[0], 'dedicated App Server / stdio', None,
                 'native-start-status-stop-fresh-lifecycle', 'S5-OP-CODEX-0158', OP_LIMITS),
                ('C-DRR', IDS[1], 'dedicated App Server / dynamic task tools / manual compact',
                 'document-review-report-v1', 'RESUME_VERIFIED',
                 'DRR-V1-CODEX-0158-LIVE-01', DRR_LIMITS)]]


def scope_template():
    return dict(schema=1, release_candidate_id='yohaku-0.1.0a1-rc2',
                status='review-input-not-release-approval', source_review_commit=BASE,
                alpha_scope_profile_ids=IDS, excluded_profile_ids=EXCLUDED,
                excluded_runtime_families=['hermes', 'claude'],
                maturity='experimental', release_channel='undeclared', profiles=claims(),
                evidence_index='candidate-a-evidence.json',
                source_drift_review='stage1-source-drift.json',
                required_artifact_checks=[
                    'candidate-a-drift', 'public-safe-allowlist', 'retained-evidence-hashes',
                    'reviewed-source-association', 'release-artifact-source-association',
                    'release-artifact-content-review', 'release-artifact-installation'],
                release_artifact_status='NOT_CREATED',
                known_exclusions=LIMITS)


def index_template():
    records = []
    for claim, source, execution, workload, summary in zip(
            claims(), [OP_SOURCE, ACCEPTED], ['native-lifecycle-no-inference', 'live-runtime'],
            ['lifecycle-only', 'nonfixture-real-task'],
            ['docs/release/candidate-a.md#c-op', 'docs/release/candidate-a.md#c-drr']):
        records.append(dict(**claim, private_source_ref=claim['evidence_record_id'],
                            sanitized_source='not public', source_manifest_sha256=HASH,
                            artifacts={k: HASH for k in ['retained-wheel', 'result', 'acceptance']},
                            source_commit=source, producer='maintainer', execution=execution,
                            workload=workload, reviewer_result='retained-bounded-PASS',
                            public_summary=summary, relates_to=['STAGE1-SOURCE-DRIFT-84B34F8'],
                            supersedes=[]))
    return dict(schema=1, purpose='release-claim-index-only', records=records)


def classifications(path, changed):
    if not changed:
        return []
    reviewed = {
        'src/yohaku/document_review_runtime.py': ['credential admission', 'operator status'],
        'src/yohaku/operational.py': ['credential admission', 'operator status'],
        'src/yohaku/cli.py': ['CLI wording', 'operator status'],
        'src/yohaku/profiles.py': ['registry wording'],
    }
    if path in reviewed:
        return reviewed[path]
    require(not path.startswith('src/'), 'SEMANTIC_REVIEW_REQUIRED')
    return ['tests only'] if path.startswith('tests/') else ['docs only']


def drift_template(root):
    files = []
    for path in TRACKED:
        old, current = (sha(git_bytes(root, commit, path)) for commit in [ACCEPTED, BASE])
        files.append(dict(file=path, old_sha256=old, current_sha256=current,
                          status='MATCH' if old == current else 'CHANGED',
                          classifications=classifications(path, old != current)))
    dependencies = []
    for path in DEPENDENCIES:
        old, current = (sha(git_bytes(root, commit, path)) for commit in [ACCEPTED, BASE])
        require(old == current, 'DEPENDENCY_REVIEW_REQUIRED')
        dependencies.append(dict(file=path, old_sha256=old, current_sha256=current, status='MATCH'))
    return dict(schema=1, record_id='STAGE1-SOURCE-DRIFT-84B34F8',
                baseline_evidence_record_id='DRR-V1-CODEX-0158-LIVE-01',
                baseline_source_commit=ACCEPTED, baseline_source_manifest_sha256=HASH,
                current_commit=BASE, reviewer='codex-source-review',
                review_result='NO_ACCEPTED_SEMANTIC_CHANGE',
                provider_acceptance='NOT_RUN', decision='NO_NEW_PROVIDER_ACCEPTANCE_REQUIRED',
                classification_vocabulary=['credential admission', 'operator status', 'CLI wording',
                                          'registry wording', 'tests only', 'docs only',
                                          'accepted semantic change'],
                semantic_areas={area: 'UNCHANGED' for area in [
                    'transition authority / dispatch', 'completion predicate', 'handoff',
                    'receipt', 'fresh observation', 'write path', 'Task Assessor', 'continuation']},
                rationale='docs/release/candidate-a.md#stage1-source-review',
                relates_to=['S5-OP-CODEX-0158', 'DRR-V1-CODEX-0158-LIVE-01'],
                supersedes=[], files=files, supporting_source=dependencies)


def cell(value):
    if isinstance(value, list):
        return ', '.join(value)
    return {None: 'none', True: 'true', False: 'false'}.get(value, str(value))


def projection(rows):
    return {field: [cell(row[field]) for row in rows] for field in rows[0]}


def policy_projection(scope):
    return {key: [cell(scope[key])] for key in [
        'release_candidate_id', 'alpha_scope_profile_ids', 'excluded_profile_ids',
        'excluded_runtime_families', 'maturity', 'release_channel', 'known_exclusions']}


def read_table(text):
    start, end = '<!-- candidate-a:start -->', '<!-- candidate-a:end -->'
    require(text.count(start) == text.count(end) == 1, 'CANONICAL_BLOCK')
    block = text.split(start)[1].split(end)[0]
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    require(len(lines) >= 3 and all(line.startswith('|') and line.endswith('|')
                                  for line in lines), 'CANONICAL_TABLE')
    result = {}
    for line in lines[2:]:
        key, *values = [part.strip().strip('`') for part in line.strip('|').split('|')]
        require(key not in result, 'CANONICAL_DUPLICATE')
        result[key] = values
    return result


def load_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, 'DUPLICATE_JSON_KEY')
            obj[key] = value
        return obj
    return json.loads(path.read_text(), object_pairs_hook=unique)


def validate(root=ROOT, *, scope=None, index=None, drift=None, profiles=None, documents=None):
    scope = load_json(root / DATA / 'candidate-a-scope.json') if scope is None else scope
    index = load_json(root / DATA / 'candidate-a-evidence.json') if index is None else index
    drift = load_json(root / DATA / 'stage1-source-drift.json') if drift is None else drift
    public_shape(scope, scope_template())
    public_shape(index, index_template())
    public_shape(drift, drift_template(root))
    require(drift['baseline_source_manifest_sha256'] ==
            index['records'][1]['source_manifest_sha256'], 'MANIFEST_LINK')
    profiles = PROFILES if profiles is None else profiles
    require(set(CANDIDATE_A) == set(IDS), 'ALPHA_SCOPE')
    require(set(profiles) - set(IDS) == set(EXCLUDED), 'EXCLUDED_SCOPE_REVIEW')
    for claim, limits_hash in zip(scope['profiles'], REGISTRY_LIMITS):
        p = profiles[claim['support_profile_id']]
        for field, key in [('runtime_family', 'runtime'), ('runtime_exact_version', 'runtime_version'),
                           ('surface', 'surface'), ('maturity', 'maturity'),
                           ('release_channel', 'release_channel'),
                           ('operational_launcher_support', 'launch_supported'),
                           ('task_profile_id', 'task_profile'), ('evidence_record_id', 'evidence_id')]:
            require(claim[field] == p.get(key), 'REGISTRY_DRIFT')
        require(claim['task_runner_support'] == (p.get('entrypoint') == 'run'), 'RUNNER_DRIFT')
        require(sha(json.dumps(p['known_limitations'], ensure_ascii=True,
                               sort_keys=True).encode()) == limits_hash, 'EXCLUSION_DRIFT')
    expected_tables = {path: projection(scope['profiles']) for path in DOCS}
    expected_tables[TASK_DOC] = projection(scope['profiles'][1:])
    expected_tables[POLICY] = policy_projection(scope)
    for path, expected in expected_tables.items():
        text = (root / path).read_text() if documents is None else documents[path]
        require(read_table(text) == expected, 'CANONICAL_DRIFT')
    project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
    require(project['version'] == '0.1.0a1', 'PACKAGE_VERSION_DRIFT')
    require(project.get('license') == 'Apache-2.0'
            and project.get('license-files') == ['LICENSE'], 'PACKAGE_LICENSE_DRIFT')
    require(sha((root / 'LICENSE').read_bytes()) == LICENSE_SHA256, 'LICENSE_TEXT_DRIFT')
    # Hash changes trigger review, not an automatic instruction to rerun live acceptance.
    for row in drift['files'] + drift['supporting_source']:
        if row['file'].startswith('src/'):
            current = (root / row['file']).read_bytes()
            # RC1 review allows only package identity lookup in initialize clientInfo.
            # Keep the historical Stage 1 hashes and reject all other source changes.
            if row['file'] in ('src/yohaku/operational_hosts.py',
                               'src/yohaku/document_review_runtime.py'):
                baseline = git_bytes(root, BASE, row['file'])
                expected = baseline.replace(b'import json\n',
                    b'import json\nfrom importlib.metadata import version\n', 1)
                expected = expected.replace(b"'version': '0.1.0'", b"'version': version('yohaku')")
                expected = expected.replace(b'"version": "0.1.0"', b'"version": version("yohaku")')
                require(current == expected, 'SOURCE_REVIEW_REQUIRED')
            else:
                require(sha(current) == row['current_sha256'], 'SOURCE_REVIEW_REQUIRED')
    return 'PASS: Candidate A static drift / public-safe checks; release approval NOT_ASSESSED'


def main():
    try:
        print(validate())
        return 0
    except Exception:
        # A malformed input may itself be private; no input-derived diagnostics.
        print('FAIL: Candidate A validation; review scope, public fields, and source association')
        return 1


if __name__ == '__main__':
    sys.exit(main())
