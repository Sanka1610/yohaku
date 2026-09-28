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

from .profiles import MISSING_TASK, profile


class OperationError(RuntimeError):
    pass


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

    def __post_init__(self):
        profile(self.profile)
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


def config_digest(config):
    d = asdict(config)
    d.pop('enabled')
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
        c = OperationalConfig(**read_json(p))
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


def last_run(config):
    p = Path(config.state_dir) / 'last-run.json'
    if not p.exists():
        return None
    d = read_json(p)
    if (d.get('schema') != 1 or d.get('config_digest') != config_digest(config)
            or d.get('state') not in {'STARTING', 'RUNNING', 'STOPPING', 'STOP_INCOMPLETE', 'STOPPED', 'FAILED'}
            or not isinstance(d.get('run_id'), str)):
        raise OperationError('INVALID_LIFECYCLE_RECORD')
    return d


def recovery(config, state=None):
    state = last_run(config) if state is None else state
    stopped = state is None or state.get('state') == 'STOPPED'
    return dict(fresh_start_allowed=stopped, resume_supported=False,
                reason='FRESH_SESSION_ONLY; ' + MISSING_TASK if stopped else
                'RECOVERY_REQUIRED: prior owner did not prove a clean stop; preserve state, inspect runtime',
                transition_reason=MISSING_TASK,
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


def preflight(config):
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
    return dict(verdict='PASS' if not errors else 'FAIL', profile=p, package=package_identity(), observed_runtime=actual,
                expected_runtime=p.get('source_commit', p['runtime_version']), errors=errors,
                enabled=config.enabled, inference_enabled=False, work_observation_available=False,
                transition_available=False, transition_reason=MISSING_TASK,
                evidence_scope='preflight only; no native startup or transition acceptance',
                assumptions={'single_owner_acknowledged': config.single_owner,
                             'dedicated_session_acknowledged': config.dedicated_session,
                             'external_clients_excluded_by_lock': False})


def set_enabled(path, enabled):
    config = load(path)
    with owner_lock(config):
        config = load(path)
        if not recovery(config)['fresh_start_allowed']:
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
    return dict(profile=profile(config.profile), package=package_identity(), enabled=config.enabled, owner_live=live is not None,
                owner_lock_busy=busy, operational=current, recovery=recovery(config),
                transition_available=False, transition_reason=MISSING_TASK)


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
