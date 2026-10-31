"""Offline Avahi recovery regressions; no D-Bus installation or device required."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('discovery_server', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'dbus': Mock()}):
    spec.loader.exec_module(server)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.avahi = Mock()
        self.avahi.GetState.return_value = 2
        self.interface = patch.object(server.dbus, 'Interface', return_value=self.avahi)
        self.bus = patch.object(server, 'system_bus', return_value=Mock())
        self.publish = patch.object(server, 'publish_pair_service', return_value=Mock())
        self.interface.start()
        self.bus.start()
        self.publisher = self.publish.start()
        self.addCleanup(self.interface.stop)
        self.addCleanup(self.bus.stop)
        self.addCleanup(self.publish.stop)

    def test_valid_registration_is_not_repeated(self):
        for state in (1, 2):
            group = Mock()
            group.GetState.return_value = state
            self.assertIs(server.maintain_pair_service(group), group)
            group.Free.assert_not_called()
        self.publisher.assert_not_called()

    def test_uncommitted_collision_and_failure_are_republished(self):
        for state in (0, 3, 4):
            with self.subTest(state=state):
                self.publisher.reset_mock()
                group = Mock()
                group.GetState.return_value = state
                self.assertIs(server.maintain_pair_service(group), self.publisher.return_value)
                group.Free.assert_called_once()
                self.publisher.assert_called_once()

    def test_daemon_restart_releases_stale_group(self):
        group = Mock()
        group.GetState.side_effect = RuntimeError('old daemon disappeared')
        group.Free.side_effect = RuntimeError('old object disappeared')
        self.assertIs(server.maintain_pair_service(group), self.publisher.return_value)

    def test_waits_for_host_registration_after_collision(self):
        self.avahi.GetState.return_value = 1
        self.assertIsNone(server.maintain_pair_service(None))
        self.publisher.assert_not_called()
        self.avahi.GetState.return_value = 2
        self.assertIs(server.maintain_pair_service(None), self.publisher.return_value)


if __name__ == '__main__':
    unittest.main(verbosity=2)
