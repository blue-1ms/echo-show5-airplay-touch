"""Lifecycle regressions, including Linux inter-process locking."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import receiver

class LifecycleTests(unittest.TestCase):
    def test_identity_uses_executable_and_root_not_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc/'123').mkdir()
            (proc/'123'/'stat').write_text('123 (shairport-sync) S ' + '0 '*18 + '987 0')
            with patch.object(receiver, 'PROC', proc), patch.object(receiver.os.path, 'samefile', return_value=True):
                self.assertEqual(receiver.receiver_pids(), [123])
            with patch.object(receiver, 'PROC', proc), patch.object(receiver.os.path, 'samefile', side_effect=[True, False]):
                self.assertEqual(receiver.receiver_pids(), [])

    def test_ensure_does_not_spawn_existing_absolute_path_process(self):
        with patch.object(receiver, 'receiver_lock'), patch.object(receiver, 'receiver_pids', return_value=[123]), patch.object(receiver.subprocess, 'Popen') as spawn:
            receiver.ensure_receiver()
            spawn.assert_not_called()

    def test_stop_timeout_never_launches_replacement(self):
        with patch.object(receiver, 'receiver_pids', return_value=[123]), patch.object(receiver, 'identity', return_value='987'), patch.object(receiver.os, 'kill'), patch.object(receiver.time, 'monotonic', side_effect=[0, 6]), patch.object(receiver.subprocess, 'Popen') as spawn:
            with self.assertRaises(RuntimeError):
                receiver.restart_receiver()
            spawn.assert_not_called()

    def test_reused_pid_is_not_signalled(self):
        with patch.object(receiver, 'receiver_pids', side_effect=[[123], []]), patch.object(receiver, 'identity', side_effect=['old', 'new']), patch.object(receiver.os, 'kill') as kill:
            receiver.stop_receiver()
            kill.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'Linux flock integration')
    def test_independent_lock_handles_serialize_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(receiver, 'LOCK_PATH', Path(directory)/'receiver.lock'):
            with receiver.receiver_lock():
                with self.assertRaises(RuntimeError):
                    with receiver.receiver_lock(timeout=.1):
                        self.fail('Second owner acquired the lock')
            with receiver.receiver_lock(timeout=.1):
                pass

if __name__ == '__main__':
    unittest.main()
