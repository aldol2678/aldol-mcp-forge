"""Local subprocess verifier. Linux user+mount+network+PID namespaces when available.

Do not use to execute arbitrary untrusted code. It is not a complete sandbox.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _limits():
    if os.name == 'posix':
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (3, 4))
        resource.setrlimit(resource.RLIMIT_AS, (192 * 1024 * 1024, 192 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def namespace_ready():
    if os.name != 'posix' or not (shutil.which('unshare') and shutil.which('mount')):
        return False
    try:
        p = subprocess.run(['unshare', '--user', '--map-root-user', '--net', '--mount', '--pid', '--fork',
                            'true'], timeout=3, capture_output=True)
        return p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_command(directory: Path, command, payload: str, isolation='auto', use_native_deps=False):
    if isolation not in ('auto', 'strict'):
        raise ValueError('isolation must be auto or strict')
    directory = directory.resolve(strict=True)
    namespace = namespace_ready()
    if isolation == 'strict' and not namespace:
        raise RuntimeError('Linux namespace isolation unavailable; strict mode fails closed')
    if namespace:
        script = ('set -eu; mount --bind "$1" "$1"; '
                  'mount -o remount,bind,ro "$1"; '
                  'shift; exec "$@"')
        command = [shutil.which('unshare'), '--user', '--map-root-user', '--net', '--mount',
                   '--pid', '--fork', '--', 'sh', '-c', script, '_', str(directory), *command]
    try:
        process = subprocess.run(command, input=payload, text=True, capture_output=True,
                                 timeout=12 if use_native_deps else 6, cwd=directory,
                                 preexec_fn=_limits if os.name == 'posix' else None,
                                 env={'PATH': '/usr/bin:/bin', 'PYTHONNOUSERSITE': '1',
                                      'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'})
    except subprocess.TimeoutExpired as e:
        raise RuntimeError('Verification timed out') from e
    if process.returncode or (process.stderr and not use_native_deps):
        raise RuntimeError(f'Verification failed: rc={process.returncode} {process.stderr[:400]}')
    return process.stdout, ('linux-user-net-mount-pid-namespace-project-readonly' if namespace
                            else 'resource-limited-process-NOT-network-isolated')


def run_server(directory: Path, payload: str, isolation='auto'):
    directory = directory.resolve(strict=True)
    command = [sys.executable, '-S', '-B', str(directory / 'server.py'), '--compat-smoke-test']
    return run_command(directory, command, payload, isolation=isolation)
