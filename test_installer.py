"""Windows installer guard tests with fake ADB; never connects to a device."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell entry point')
class InstallerGuards(unittest.TestCase):
    def run_case(self, model='cronos', devices=1, mode='upgrade'):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            log = folder / 'calls.jsonl'
            fake = folder / 'fake.py'
            fake.write_text('''import sys, json
from pathlib import Path
args=sys.argv[1:]
with Path(%r).open('a') as f: f.write(json.dumps(args)+'\\n')
s=' '.join(args)
if s=='devices': print('List of devices attached\\n'+''.join('TEST'+str(i)+'\\tdevice\\n' for i in range(%d)))
elif 'ro.product.device' in s: print(%r)
elif 'ro.build.version.sdk' in s: print('30')
elif 'ro.product.cpu.abi' in s: print('armeabi-v7a')
elif 'pm path com.termux' in s: print('package:/test/termux.apk')
elif 'command -v su' in s: print('/system/xbin/su')
elif 'installer-incomplete' in s: print(%r)
elif 'uid' in s or s.endswith("'id'"): print('uid=0(root) gid=0(root)')
else: print('UNEXPECTED MUTATION OR COMMAND: '+s);sys.exit(91)
''' % (str(log), devices, model, mode), encoding='utf-8')
            cmd = folder / 'adb.cmd'
            cmd.write_text('@echo off\r\n"%s" "%s" %%*\r\n' % (sys.executable, fake))
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(ROOT / 'Install.ps1'), '-AdbPath', str(cmd),
                                     '-CheckOnly'], capture_output=True, text=True)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_supported_upgrade_check_does_not_modify_device(self):
        result, calls = self.run_case()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('No device files changed', result.stdout)
        self.assertFalse(any(c[0] in ('push', 'install', 'reboot') or 'mkdir' in ' '.join(c) for c in calls))

    def test_other_models_rejected_before_root(self):
        result, calls = self.run_case(model='checkers')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('su -mm' in ' '.join(c) for c in calls))

    def test_multiple_devices_require_selection(self):
        result, calls = self.run_case(devices=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [['devices']])

    def test_unknown_runtime_is_not_overwritten(self):
        result, calls = self.run_case(mode='unknown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('refusing to overwrite', result.stdout + result.stderr)
        self.assertFalse(any(c[0] in ('push', 'install') for c in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
