"""Single-owner receiver lifecycle shared by settings and the watchdog."""
from contextlib import contextmanager
from pathlib import Path
import os
import signal
import subprocess
import time

BINARY = Path('/usr/local/bin/shairport-sync')
PROC = Path('/proc')
LOCK_PATH = Path('/run/echo-airplay/receiver.lock')
LOG_PATH = Path('/run/echo-airplay/shairport-sync.log')

@contextmanager
def receiver_lock(timeout=12):
    import fcntl
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open('a') as lock:
        until = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= until:
                    raise RuntimeError('Receiver is busy. Please try again.')
                time.sleep(.05)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)

def identity(pid):
    item = PROC / str(pid)
    try:
        # Compare the proc magic links directly; argv[0] and host/chroot path
        # spellings are not trustworthy process identities.
        if not os.path.samefile(item / 'exe', BINARY) or not os.path.samefile(item / 'root', '/'):
            return None
        stat = (item / 'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        return stat[19]  # /proc/PID/stat field 22: start time
    except (OSError, ValueError, IndexError):
        return None

def receiver_pids():
    return [int(p.name) for p in PROC.iterdir() if p.name.isdigit() and identity(int(p.name)) is not None]

def stop_receiver(timeout=5):
    targets = {pid: identity(pid) for pid in receiver_pids()}
    for pid, started in targets.items():
        if started is not None and identity(pid) == started:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    until = time.monotonic() + timeout
    while receiver_pids():
        if time.monotonic() >= until:
            raise RuntimeError('Receiver did not stop; no replacement was started.')
        time.sleep(.1)

def start_receiver():
    if receiver_pids():
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('ab') as log:
        # Retain conventional argv[0] for older external diagnostic tools.
        process = subprocess.Popen(['shairport-sync', '-v'], executable=str(BINARY),
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    time.sleep(.3)
    if process.poll() is not None:
        raise RuntimeError('Receiver exited during startup. Check the receiver log.')

def restart_receiver():
    # Caller holds receiver_lock across config write, restart and rollback.
    stop_receiver()
    start_receiver()

def ensure_receiver():
    with receiver_lock():
        if len(receiver_pids()) > 1:
            stop_receiver()
        start_receiver()

if __name__ == '__main__':
    ensure_receiver()
