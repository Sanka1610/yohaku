"""Native hosts for lifecycle-only profiles. No task or transition dispatch API."""

from contextlib import redirect_stdout, redirect_stderr
import json
from importlib.metadata import version
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

from .operational import OperationError
from .profiles import MISSING_TASK


def deny_task(*args, **kwargs):
    raise OperationError(MISSING_TASK)


class CodexOperationalHost:
    def __init__(self):
        self.process = self.owner = self.host = None
        self.messages = queue.Queue(maxsize=1024)
        self.reader = None
        self.closing = False
        self.sequence = 0

    def open(self, config, run):
        home = run / 'codex-home'
        home.mkdir(mode=0o700)
        # No credentials, inherited plugins or public inference endpoint. This is an
        # operational profile, not the Reference model/provider configuration.
        (home / 'config.toml').write_text('''model = "yohaku-no-inference"
model_provider = "yohaku_disabled"
check_for_update_on_startup = false
web_search = "disabled"
project_root_markers = []
[model_providers.yohaku_disabled]
name = "Yohaku operational only"
base_url = "http://127.0.0.1:9/v1"
wire_api = "responses"
requires_openai_auth = false
[analytics]
enabled = false
[feedback]
enabled = false
[features]
hooks = false
plugins = false
apps = false
memories = false
shell_snapshot = false
''' + '\n[projects.' + json.dumps(config.workspace) + ']\ntrust_level = "untrusted"\n')
        os.chmod(home / 'config.toml', 0o600)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'CODEX_HOME': str(home),
               'LANG': 'C.UTF-8', 'RUST_LOG': 'off'}
        self.process = subprocess.Popen([config.runtime_path, 'app-server', '--stdio'], env=env,
            cwd=home, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, start_new_session=True)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.call('initialize', {'clientInfo': {'name': 'yohaku_operational', 'version': version('yohaku')}})
        self.send({'method': 'initialized'})
        result = self.call('thread/start', {'model': 'yohaku-no-inference', 'cwd': config.workspace,
                                          'approvalPolicy': 'never', 'sandbox': 'read-only'})
        thread = result['thread']
        self.session_id = thread['id']
        if thread.get('turns'):
            raise OperationError('FRESH_THREAD_REQUIRED')
        from .companion import CompanionController
        from .runtime import RuntimeHost
        os.environ['CODEX_HOME'] = str(home)
        self.owner = CompanionController(self.session_id, deny_task, create=True)
        self.host = RuntimeHost(self.owner)

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(1048577)
                if not line:
                    break
                if len(line) > 1048576 or not line.endswith('\n'):
                    break
                self.messages.put(json.loads(line), timeout=1)
        except (OSError, ValueError, queue.Full):
            pass
        finally:
            try:
                self.messages.put(None, timeout=1)
            except queue.Full:
                pass

    def send(self, message):
        if message.get('method') not in ('initialize', 'initialized', 'thread/start'):
            deny_task()
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        self.send({'id': self.sequence, 'method': method, 'params': params})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                msg = self.messages.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if msg is None:
                raise OperationError('RUNTIME_EOF')
            if msg.get('id') == self.sequence:
                if 'error' in msg:
                    raise OperationError('RUNTIME_RPC_REJECTED')
                return msg['result']
            self._validate_event(msg)
        raise OperationError('RUNTIME_START_TIMEOUT')

    def _validate_event(self, message):
        if not isinstance(message, dict):
            raise OperationError('INVALID_RUNTIME_EVENT')
        if 'id' in message or message.get('method', '').startswith(('turn/', 'item/')):
            raise OperationError('UNEXPECTED_RUNTIME_WORK')

    def poll(self):
        for _ in range(256):
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            if message is None:
                if not self.closing:
                    raise OperationError('RUNTIME_EOF')
                break
            self._validate_event(message)
            if self.host:
                self.host.receive(message)
        if self.process and self.process.poll() is not None and not self.closing:
            raise OperationError('RUNTIME_EXITED')

    def details(self):
        return dict(runtime_running=True, runtime_pid=self.process.pid, session_id=self.session_id,
                    native_host_constructed=True, inference_agent_initialized=False,
                    transition_adapter_attached=False, companion_attached=True,
                    work_observation_available=False, hook_registration=False,
                    storage=str(self.owner.store.path))

    def begin_stop(self):
        if not self.closing:
            self.closing = True
            if self.process and self.process.stdin:
                self.process.stdin.close()  # App Server stdio EOF; no forced kill escalation

    def stopped(self):
        return self.process is None or self.process.poll() is not None

    def clean_stop(self):
        return self.process is None or self.process.returncode == 0

    def close(self):
        if self.owner:
            self.owner.close()
        if self.process:
            self.process.wait()
            self.reader.join(timeout=1)
            self.process.stdout.close()


class HermesOperationalHost:
    def __init__(self):
        self.native = self.store = None
        self.closed = False

    def open(self, config, run):
        source = Path(config.runtime_path)
        home = run / 'hermes-home'
        home.mkdir(mode=0o700)
        # Keep the process in its isolated home so optional native relative config
        # and dotenv discovery cannot read the user's task directory.
        os.chdir(home)
        for key in list(os.environ):
            if key not in ('PATH', 'LANG', 'TERM'):
                os.environ.pop(key, None)
        os.environ.update(HOME=str(home), HERMES_HOME=str(home), HERMES_PROFILE=run.name,
                          HERMES_IGNORE_RULES='1', HERMES_SKIP_UPDATE_CHECK='1',
                          HERMES_DISABLE_TELEMETRY='1', TIRITH_ENABLED='false',
                          CODEX_HOME=str(home / 'yohaku-control'))
        (home / 'config.yaml').write_text('''compression:
  enabled: false
memory:
  memory_enabled: false
  user_profile_enabled: false
fallback_model: null
display:
  persistent_output: false
''')
        os.chmod(home / 'config.yaml', 0o600)

        def offline_only(event, args):
            if event == 'socket.__new__' and args[1] in (socket.AF_INET, socket.AF_INET6):
                raise OperationError('INFERENCE_AND_NETWORK_DISABLED')
            if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec', 'os.fork'):
                raise OperationError('NATIVE_CHILD_PROCESS_DISABLED')

        # This foreground process is dedicated to the no-inference host. The audit
        # hook intentionally remains active until exit, including native cleanup.
        sys.addaudithook(offline_only)
        sys.path.insert(0, str(source))  # installed native host, never Yohaku source
        import hermes_cli.env_loader
        hermes_cli.env_loader.load_hermes_dotenv = lambda *args, **kwargs: []
        with open(os.devnull, 'w') as sink, redirect_stdout(sink), redirect_stderr(sink):
            import cli
            if Path(cli.__file__).resolve() != source / 'cli.py':
                raise OperationError('WRONG_NATIVE_HOST_IMPORT')
            self.native = cli.HermesCLI(model='gpt-5.6-luna', provider='openai-codex',
                reasoning='low', toolsets=[], max_turns=1, ignore_rules=True)
        if (self.native.agent is not None or self.native.conversation_history
                or self.native._resumed or self.native._session_db is None):
            raise OperationError('FRESH_IDLE_HERMES_HOST_REQUIRED')
        # Do not initialize the inference agent to fabricate an attached H-CLI-01
        # transition adapter. No real task observer exists in this release.
        self.native.chat = self.native._manual_compress = self.native._init_agent = deny_task
        from .persistence import SessionStore
        self.store = SessionStore(self.native.session_id, create=True)

    def details(self):
        return dict(runtime_running=True, runtime_pid=os.getpid(), session_id=self.native.session_id,
                    native_host_constructed=True, inference_agent_initialized=False,
                    transition_adapter_attached=False, companion_attached=False,
                    work_observation_available=False, hook_registration=False,
                    storage=str(self.store.path))

    def poll(self):
        if self.native and (self.native.agent is not None or self.native.conversation_history):
            raise OperationError('UNEXPECTED_HERMES_WORK')

    def begin_stop(self):
        if self.native and self.native._session_db:
            self.native._session_db.close()
        if self.store:
            self.store.close()
        self.closed = True

    def stopped(self):
        return self.closed

    def clean_stop(self):
        return self.closed

    def close(self):
        pass
