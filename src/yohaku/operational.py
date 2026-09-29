"""Small POSIX operational lifecycle, separate from the transition journal."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import fcntl
import hashlib
import json
from importlib.metadata import distribution
import math
import os
import platform
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from .profiles import CANDIDATE_A, MISSING_TASK, profile


class OperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CredentialIdentity:
    home: tuple[int, ...]
    auth: tuple[int, ...]


def absolute(value):
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts:
        raise OperationError('ABSOLUTE_PATH_REQUIRED')
    for part in (p, *p.parents):
        if part.is_symlink():
            raise OperationError('SYMLINK_PATH_REJECTED')
    return p


def private(path, *, directory=False):
    p = absolute(path)
    s = p.stat()
    if s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise OperationError('PRIVATE_PATH_REQUIRED')
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):
        raise OperationError('WRONG_PATH_TYPE')
    return p


def _private_identity(path, *, directory=False):
    p = private(path, directory=directory)
    s = p.lstat()
    if s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise OperationError('PRIVATE_PATH_REQUIRED')
    if not (stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)):
        raise OperationError('WRONG_PATH_TYPE')
    return p, (s.st_dev, s.st_ino, s.st_uid, stat.S_IMODE(s.st_mode),
               s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def credential_identity(config, expected=None):
    try:
        home, home_before = _private_identity(config.credential_home, directory=True)
    except FileNotFoundError:
        raise OperationError('CODEX_CREDENTIAL_HOME_MISSING') from None
    except OSError:
        raise OperationError('CODEX_CREDENTIAL_HOME_INVALID') from None
    try:
        _, auth = _private_identity(home / 'auth.json')
    except FileNotFoundError:
        raise OperationError('CODEX_AUTH_MISSING') from None
    except OSError:
        raise OperationError('CODEX_AUTH_INVALID') from None
    _, home_after = _private_identity(home, directory=True)
    current = CredentialIdentity(home_after, auth)
    if home_before != home_after or expected is not None and current != expected:
        raise OperationError('CODEX_CREDENTIAL_STATE_CHANGED')
    return current


def read_json(path):
    p = private(path)
    if p.stat().st_size > 65536:
        raise OperationError('RECORD_TOO_LARGE')
    try:
        value = json.loads(p.read_text())
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise OperationError('INVALID_RECORD') from None


def write_json(path, value, *, create=False):
    p = absolute(path)
    private(p.parent, directory=True)
    if p.exists():
        private(p)
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.tmp-', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        if create:
            os.link(name, p)  # exclusive publish: never overwrite a concurrent configure
        else:
            os.replace(name, p)
        d = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@dataclass(frozen=True)
class OperationalConfig:
    profile: str
    runtime_path: str
    workspace: str
    state_dir: str
    dedicated_session: bool
    single_owner: bool
    enabled: bool = False
    stop_timeout: float = 10.0
    schema: int = 1
    task_inputs: tuple[str, ...] = ()
    task_output: str | None = None
    task_instruction: str | None = None
    credential_home: str | None = None

    def __post_init__(self):
        p = profile(self.profile)
        if type(self.schema) is not int or self.schema != 1:
            raise OperationError('CONFIG_SCHEMA_UNSUPPORTED')
        for name in ('enabled', 'dedicated_session', 'single_owner'):
            if type(getattr(self, name)) is not bool:
                raise OperationError('BOOLEAN_REQUIRED')
        for name in ('runtime_path', 'workspace', 'state_dir'):
            if not isinstance(getattr(self, name), str):
                raise OperationError('PATH_STRING_REQUIRED')
            absolute(getattr(self, name))
        if (type(self.stop_timeout) not in (float, int) or not math.isfinite(self.stop_timeout)
                or not 0.1 <= self.stop_timeout <= 60):
            raise OperationError('STOP_TIMEOUT_RANGE_0_1_TO_60')
        w, s = Path(self.workspace), Path(self.state_dir)
        if w == s or w in s.parents or s in w.parents:
            raise OperationError('STATE_AND_WORKSPACE_MUST_BE_SEPARATE')
        task = p.get('task_profile')
        supplied = bool(self.task_inputs or self.task_output or self.task_instruction or self.credential_home)
        if task == 'document-review-report-v1':
            if (not isinstance(self.task_inputs, tuple) or not self.task_inputs
                    or not isinstance(self.task_output, str)
                    or not isinstance(self.task_instruction, str)
                    or not isinstance(self.credential_home, str)):
                raise OperationError('DOCUMENT_REVIEW_TASK_CONTRACT_REQUIRED')
            for value in (*self.task_inputs, self.task_output, self.credential_home):
                if not isinstance(value, str):
                    raise OperationError('PATH_STRING_REQUIRED')
                absolute(value)
        elif supplied:
            raise OperationError('TASK_CONTRACT_NOT_ALLOWED_FOR_PROFILE')


def config_digest(config):
    d = asdict(config)
    d.pop('enabled')
    # Preserve schema-1 lifecycle bindings created before task profiles existed.
    if not d['task_inputs'] and d['task_output'] is None and d['task_instruction'] is None and d['credential_home'] is None:
        for key in ('task_inputs', 'task_output', 'task_instruction', 'credential_home'):
            d.pop(key)
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def package_identity():
    d = distribution('yohaku')
    record = d.read_text('RECORD')
    return dict(version=d.version, python=sys.version.split()[0], platform=sys.platform,
                package_path=str(Path(__file__).parent),
                installed_record_sha256=hashlib.sha256(record.encode()).hexdigest() if record else None)


def configure(path, config):
    p = absolute(path)
    private(p.parent, directory=True)
    root = absolute(config.state_dir)
    if p == root or root in p.parents:
        raise OperationError('CONFIG_MUST_BE_OUTSIDE_STATE')
    if p.exists() or root.exists():
        raise OperationError('CONFIG_OR_STATE_EXISTS')
    root.mkdir(mode=0o700)  # explicit new root; never adopt an existing runtime home
    write_json(root / 'binding.json', {'schema': 1, 'config': str(p), 'digest': config_digest(config)}, create=True)
    write_json(p, asdict(config), create=True)


def load(path):
    p = absolute(path)
    try:
        value = read_json(p)
        if isinstance(value.get('task_inputs'), list):
            value['task_inputs'] = tuple(value['task_inputs'])
        c = OperationalConfig(**value)
    except (TypeError, ValueError):
        raise OperationError('INVALID_CONFIG_OR_PROFILE') from None
    root = private(c.state_dir, directory=True)
    if read_json(root / 'binding.json') != {'schema': 1, 'config': str(p), 'digest': config_digest(c)}:
        raise OperationError('CONFIG_BINDING_MISMATCH')
    return c


@contextmanager
def owner_lock(config):
    root = private(config.state_dir, directory=True)
    p = root / 'owner.lock'
    if p.exists():
        private(p)
    fd = os.open(p, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OperationError('OWNER_BUSY') from None
        yield
    finally:
        os.close(fd)


@contextmanager
def task_workspace_lock(config):
    if profile(config.profile).get('task_profile') != 'document-review-report-v1':
        yield
        return
    root = private(config.workspace, directory=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OperationError('TASK_WORKSPACE_BUSY') from None
        yield
    finally:
        os.close(fd)


def last_run(config):
    p = Path(config.state_dir) / 'last-run.json'
    if not p.exists():
        return None
    d = read_json(p)
    if (d.get('schema') != 1 or d.get('config_digest') != config_digest(config)
            or d.get('state') not in {'STARTING', 'RUNNING', 'STOPPING', 'STOP_INCOMPLETE',
                                      'STOPPED', 'FAILED', 'AMBIGUOUS'}
            or not isinstance(d.get('run_id'), str)):
        raise OperationError('INVALID_LIFECYCLE_RECORD')
    return d


def recovery(config, state=None):
    state = last_run(config) if state is None else state
    task = profile(config.profile).get('task_profile')
    stopped = state is None or state.get('state') == 'STOPPED'
    fresh = state is None if task else stopped
    task_reason = ('TASK_RESTART_UNSUPPORTED; completed or uncertain writes are never retried'
                   if task else MISSING_TASK)
    return dict(fresh_start_allowed=fresh, resume_supported=False,
                reason=('FRESH_TASK_ONLY' if task and state is None else
                        'TASK_COMPLETE_NO_RERUN; ' + task_reason if task and state and state.get('state') == 'STOPPED' else
                        'FRESH_SESSION_ONLY; ' + task_reason) if stopped else
                'RECOVERY_REQUIRED: prior owner did not prove a clean stop; preserve state, inspect runtime',
                transition_reason=None if task else MISSING_TASK,
                saved_data_retained=True)


def command_output(args, *, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           text=True, timeout=10, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    except (OSError, subprocess.TimeoutExpired):
        raise OperationError('RUNTIME_INSPECTION_FAILED') from None
    if r.returncode:
        raise OperationError('RUNTIME_INSPECTION_FAILED')
    return r.stdout.strip()


def _preflight(config):
    p = profile(config.profile)
    errors = []
    actual = None
    if os.name != 'posix' or not Path('/proc/self/stat').exists():
        errors.append('LINUX_REQUIRED')
    if 'microsoft' not in platform.release().lower() or 'wsl2' not in platform.release().lower():
        errors.append('OPERATIONAL_PLATFORM_NOT_MEASURED')
    if platform.python_implementation() != 'CPython' or platform.python_version() != p['operational_python']:
        errors.append('OPERATIONAL_PYTHON_NOT_MEASURED')
    if p['runtime'] == 'codex' and Path('/etc/codex').exists() and any(Path('/etc/codex').iterdir()):
        errors.append('SYSTEM_CODEX_CONFIG_NOT_REVIEWED')
    if not config.dedicated_session or not config.single_owner:
        errors.append('DEDICATED_SESSION_AND_SINGLE_OWNER_ACK_REQUIRED')
    if not Path(config.workspace).is_dir():
        errors.append('WORKSPACE_MISSING')
    if not p['launch_supported']:
        errors.append('OPERATIONAL_PROFILE_UNSUPPORTED')
    task_contract = None
    credential = None
    if p.get('task_profile') == 'document-review-report-v1':
        try:
            from .document_review import DocumentReviewContract
            task_contract = DocumentReviewContract.create(
                workspace=config.workspace, inputs=config.task_inputs,
                output=config.task_output, instruction=config.task_instruction)
            credential = credential_identity(config)
        except OperationError as exc:
            errors.append(str(exc))
    try:
        if p['runtime'] == 'hermes':
            root = Path(config.runtime_path)
            actual = command_output(['git', '-C', str(root), 'rev-parse', 'HEAD'])
            if actual != p.get('source_commit'):
                errors.append('SOURCE_VERSION_MISMATCH')
            if command_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=normal']):
                errors.append('RUNTIME_SOURCE_DIRTY')
            if not (root / 'cli.py').is_file():
                errors.append('NATIVE_HOST_MISSING')
            # Python must already be the host venv: do not spawn a second bridge process.
            if Path(sys.prefix).resolve() != (root / 'venv').resolve():
                errors.append('HERMES_VENV_REQUIRED')
        else:
            actual = command_output([config.runtime_path, '--version'])
            expected = 'codex-cli ' + p['runtime_version'] if p['runtime'] == 'codex' else p['runtime_version']
            if actual != expected:
                errors.append('RUNTIME_VERSION_MISMATCH')
    except OperationError as exc:
        errors.append(str(exc))
    try:
        with owner_lock(config):
            r = recovery(config)
            if not r['fresh_start_allowed']:
                errors.append('RECOVERY_REQUIRED')
    except OperationError as exc:
        errors.append(str(exc))
    is_task = p.get('task_profile') == 'document-review-report-v1'
    task_enabled = task_contract is not None and not errors
    transition_ready = task_enabled and config.enabled
    transition_reason = (None if transition_ready else 'DISABLED' if task_enabled else
                         '; '.join(errors) if is_task and errors else MISSING_TASK)
    report = dict(verdict='PASS' if not errors else 'FAIL', profile=p, package=package_identity(), observed_runtime=actual,
                expected_runtime=p.get('source_commit', p['runtime_version']), errors=errors,
                enabled=config.enabled, inference_enabled=task_enabled,
                work_observation_available=task_enabled, transition_reason=transition_reason,
                task_contract=(dict(profile=p.get('task_profile'),
                    logical_task_id=task_contract.logical_task_id,
                    instruction_sha256=task_contract.instruction_sha256,
                    inputs=[asdict(item) for item in task_contract.initial_inputs],
                    output=str(Path(task_contract.output).relative_to(task_contract.workspace)))
                    if task_contract else None),
                evidence_scope=('task contract and runtime preflight only; no transition acceptance'
                                if p.get('task_profile') else
                                'preflight only; no native startup or transition acceptance'),
                assumptions={'single_owner_acknowledged': config.single_owner,
                             'dedicated_session_acknowledged': config.dedicated_session,
                             'external_clients_excluded_by_lock': False})
    if config.profile in CANDIDATE_A:
        report.update(task_profile_registered=is_task, transition_ready=transition_ready,
                      transition_available=transition_ready)
    else:
        report['transition_available'] = task_enabled
    return report, credential


def preflight(config):
    return _preflight(config)[0]


def set_enabled(path, enabled):
    config = load(path)
    with owner_lock(config), task_workspace_lock(config):
        config = load(path)
        state = last_run(config)
        if (not recovery(config, state)['fresh_start_allowed']
                and not (enabled is False and state and state.get('state') == 'STOPPED')):
            raise OperationError('RECOVERY_REQUIRED_BEFORE_ENABLE_OR_DISABLE')
        write_json(path, asdict(replace(config, enabled=enabled)))
    return dict(enabled=enabled, saved_data_retained=True)


def _query(state, operation, timeout):
    sockpath = absolute(state['socket'])
    private(sockpath.parent, directory=True)
    s = sockpath.stat()
    if not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise OperationError('INVALID_CONTROL_SOCKET')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(timeout)
        client.connect(str(sockpath))
        client.sendall(json.dumps({'operation': operation, 'run_id': state['run_id']}).encode() + b'\n')
        with client.makefile('rb') as stream:
            line = stream.readline(65537)
        if not line.endswith(b'\n') or len(line) > 65536:
            raise OperationError('INVALID_CONTROL_REPLY')
        reply = json.loads(line)
        if reply.get('run_id') != state['run_id']:
            raise OperationError('OWNER_IDENTITY_MISMATCH')
        return reply


def status(config):
    state = last_run(config)
    live = None
    try:
        with owner_lock(config):
            busy = False
    except OperationError as exc:
        if str(exc) != 'OWNER_BUSY':
            raise
        busy = True
    if busy and state and state.get('socket'):
        try:
            live = _query(state, 'status', 1)
        except (OSError, ValueError, OperationError):
            pass
    current = live or state or {'state': 'NEVER_STARTED'}
    if busy and live is None:
        current = dict(current, state='OWNER_UNREACHABLE')
    elif not busy and state and state['state'] != 'STOPPED':
        current = dict(current, state='RECOVERY_REQUIRED')
    elif not busy:
        current = dict(current, runtime_running=False, owner_attached=False)
    result = dict(profile=profile(config.profile), package=package_identity(), enabled=config.enabled,
                  owner_live=live is not None, owner_lock_busy=busy, operational=current,
                  recovery=recovery(config))
    if config.profile in CANDIDATE_A:
        check, _ = _preflight(config)
        result.update(task_profile_registered=check['task_profile_registered'],
                      transition_ready=check['transition_ready'],
                      transition_available=check['transition_ready'],
                      transition_reason=check['transition_reason'])
    else:
        task = profile(config.profile).get('task_profile')
        result.update(transition_available=bool(task),
                      transition_reason=None if task else MISSING_TASK)
    return result


def stop(config):
    state = last_run(config)
    s = status(config)
    if not s['owner_lock_busy']:
        if state is None or state['state'] == 'STOPPED':
            return dict(state='STOPPED', saved_data_retained=True)
        raise OperationError('RECOVERY_REQUIRED; no live owner to stop')
    if state is None or not state.get('socket'):
        raise OperationError('OWNER_STARTING_OR_UNREACHABLE')
    try:
        _query(state, 'stop', 1)
    except (OSError, ValueError):
        raise OperationError('OWNER_UNREACHABLE; stop not confirmed') from None
    deadline = time.monotonic() + config.stop_timeout + 1
    while time.monotonic() < deadline:
        s = status(config)
        if not s['owner_lock_busy']:
            if s['operational']['state'] == 'STOPPED':
                return s
            raise OperationError('STOP_INCOMPLETE; preserve state and inspect runtime')
        if s['operational']['state'] == 'STOP_INCOMPLETE':
            raise OperationError('STOP_TIMEOUT; owner retained; inspect runtime')
        time.sleep(.05)
    raise OperationError('STOP_TIMEOUT; stop not confirmed')


def start(path):
    config = load(path)
    if profile(config.profile).get('task_profile'):
        raise OperationError('USE_RUN_FOR_TASK_PROFILE')
    if not config.enabled:
        raise OperationError('DISABLED')
    check = preflight(config)
    if check['errors']:
        raise OperationError('; '.join(check['errors']))
    with owner_lock(config):
        config = load(path)  # serialize enable/disable and config binding with ownership
        if not config.enabled:
            raise OperationError('DISABLED')
        if not recovery(config)['fresh_start_allowed']:
            raise OperationError('RECOVERY_REQUIRED')
        return _serve(config, check)


def run(path):
    config = load(path)
    if profile(config.profile).get('task_profile') != 'document-review-report-v1':
        raise OperationError('RUN_REQUIRES_DOCUMENT_REVIEW_PROFILE')
    if not config.enabled:
        raise OperationError('DISABLED')
    check, credential = _preflight(config)
    if check['errors']:
        raise OperationError('; '.join(check['errors']))
    with owner_lock(config), task_workspace_lock(config):
        config = load(path)
        if not config.enabled:
            raise OperationError('DISABLED')
        if not recovery(config)['fresh_start_allowed']:
            raise OperationError('RECOVERY_REQUIRED')
        credential_identity(config, credential)
        from .document_review_runtime import run_document_review
        return run_document_review(config, check, credential)


def _serve(config, check):
    from .operational_hosts import CodexOperationalHost, HermesOperationalHost
    root = Path(config.state_dir)
    run_id = uuid4().hex
    runs = absolute(root / 'runs')
    if not runs.exists():
        runs.mkdir(mode=0o700)
    private(runs, directory=True)
    run = runs / run_id
    run.mkdir(mode=0o700)
    state = dict(schema=1, config_digest=config_digest(config), run_id=run_id, state='STARTING',
                 owner_pid=os.getpid(), runtime_running=False, owner_attached=False,
                 transition_available=False, transition_reason=MISSING_TASK,
                 profile=profile(config.profile), package=package_identity(),
                 observed_runtime=check['observed_runtime'], run_dir=str(run), inference_requests=0,
                 owner_kind='operational-only', work_observation_available=False,
                 transition_adapter_attached=False)
    if config.profile in CANDIDATE_A:
        state.update(task_profile_registered=False, transition_ready=False)

    def save():
        write_json(run / 'operation.json', state)
        write_json(root / 'last-run.json', state)

    host = None
    requested = False
    deadline = None
    failed = False
    old_signals = {}

    def request_stop(*_):
        nonlocal requested
        requested = True

    save()
    with tempfile.TemporaryDirectory(prefix='yohaku-op-') as sockets:
        state['socket'] = str(Path(sockets) / 'control.sock')
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(state['socket'])
            os.chmod(state['socket'], 0o600)
            server.listen(4)
            server.settimeout(.05)
            for sig in (signal.SIGINT, signal.SIGTERM):
                old_signals[sig] = signal.signal(sig, request_stop)
            try:
                host = CodexOperationalHost() if check['profile']['runtime'] == 'codex' else HermesOperationalHost()
                try:
                    host.open(config, run)
                    state.update(host.details(), state='RUNNING', owner_attached=True)
                    save()
                    print(json.dumps(state), flush=True)
                except Exception:
                    failed = requested = True
                    state['reason'] = 'HOST_START_FAILED; raw runtime errors are not logged'
                while True:
                    try:
                        host.poll()
                    except Exception:
                        failed = requested = True
                        state['reason'] = 'RUNTIME_OBSERVATION_FAILED'
                    if requested and deadline is None:
                        state['state'] = 'STOPPING'
                        deadline = time.monotonic() + config.stop_timeout
                        host.begin_stop()
                        save()
                    if requested and host.stopped():
                        try:
                            host.close()
                            if not host.clean_stop():
                                failed = True
                                state['reason'] = 'RUNTIME_STOP_NOT_CLEAN'
                        except Exception:
                            failed = True
                            state['reason'] = 'HOST_CLOSE_FAILED'
                        state.update(state='FAILED' if failed else 'STOPPED', runtime_running=False, owner_attached=False)
                        save()
                        break
                    if deadline is not None and time.monotonic() >= deadline and state['state'] != 'STOP_INCOMPLETE':
                        state['state'] = 'STOP_INCOMPLETE'
                        save()  # keep lock, socket and host: a timeout is not completion
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        conn.settimeout(.2)
                        try:
                            with conn.makefile('rb') as stream:
                                line = stream.readline(1025)
                            payload = json.loads(line)
                            if (len(line) > 1024 or set(payload) != {'operation', 'run_id'}
                                    or payload['run_id'] != run_id):
                                continue
                            op = payload['operation']
                            if op == 'stop':
                                requested = True
                            reply = dict(state)
                            if op not in ('status', 'stop'):
                                reply['error'] = MISSING_TASK if op == 'transition' else 'UNSUPPORTED_OPERATION'
                            conn.sendall(json.dumps(reply).encode() + b'\n')
                        except (OSError, ValueError, TypeError):
                            pass
            finally:
                for sig, previous in old_signals.items():
                    signal.signal(sig, previous)
                # Never release ownership and label success if the runtime is still alive.
                if host is not None and host.stopped() and state['state'] not in ('STOPPED', 'FAILED'):
                    host.close()
    return 1 if failed else 0
