"""Exercise the shipped launchers with inert shell and authentication commands."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_addons import SOURCE, SHELL


@unittest.skipIf(os.geteuid() == 0, 'Run launcher tests as the normal desktop user')
class Launchers(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.root = Path(self.temporary.name)
    self.calls = self.root / 'calls'
    self.repo = Path(os.environ.get('PR9750_SOURCE', os.environ.get('OMARCHY_PATH', str(SOURCE.parents[1]))))
    for name in ('sudo', 'control'):
      self.executable(name, 'printf "%s\\n" ' + shlex.quote(name) + ' "$@" >>"$CALL_LOG"\n')
    self.executable('omarchy-shell', 'printf "%s\\n" shell "$@" >>"$CALL_LOG"\nprintf "%s\\n" "$UI_RESULT"\nexit "$UI_STATUS"\n')
    for feature in ('dns', 'browsing'):
      wrapper = (SOURCE / 'bin' / ('omarchy-parent-' + feature)).read_text()
      wrapper = wrapper.replace('/usr/bin/sudo', shlex.quote(str(self.root / 'sudo')))
      wrapper = wrapper.replace('/usr/lib/omarchy-parent-addons/control', shlex.quote(str(self.root / 'control')))
      self.executable('omarchy-parent-' + feature, wrapper, shebang=False)

  def tearDown(self):
    self.temporary.cleanup()

  def executable(self, name, text, shebang=True):
    path = self.root / name
    path.write_text(('#!/bin/bash\n' if shebang else '') + text)
    path.chmod(0o755)

  def invoke(self, feature, args, result='ok', status='0', routed=False):
    self.calls.unlink(missing_ok=True)
    env = {**os.environ, 'CALL_LOG': str(self.calls), 'UI_RESULT': result, 'UI_STATUS': status,
           'OMARCHY_PATH': str(self.repo), 'PATH': str(self.root) + ':' + str(self.repo / 'bin') + ':' + os.environ['PATH']}
    command = [SHELL, str(self.root / ('omarchy-parent-' + feature))]
    if routed:
      command = [SHELL, str(self.repo / 'bin/omarchy'), 'parent', feature]
    output = subprocess.run(command + args, env=env, text=True, capture_output=True)
    calls = self.calls.read_text().splitlines() if self.calls.exists() else []
    return output, calls

  def test_ui_opens_each_panel_without_elevation(self):
    for feature in ('dns', 'browsing'):
      result, calls = self.invoke(feature, ['ui'])
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(calls, ['shell', 'shell', 'summon', 'io.github.peterholko.parent-' + feature])

  def test_ui_reports_disabled_plugins_and_shell_failures(self):
    for feature in ('dns', 'browsing'):
      for response, status in [('unknown', '0'), ('', '0'), ('', '7')]:
        result, calls = self.invoke(feature, ['ui'], result=response, status=status)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('sudo', calls)
        self.assertNotIn('control', calls)
        if status == '0':
          self.assertIn('omarchy plugin enable io.github.peterholko.parent-' + feature, result.stderr)

  def test_ui_rejects_extra_arguments_without_executing_anything(self):
    for feature in ('dns', 'browsing'):
      result, calls = self.invoke(feature, ['ui', '--user', 'linnea'])
      self.assertEqual(result.returncode, 2)
      self.assertIn('Usage:', result.stderr)
      self.assertEqual(calls, [])

  def test_terminal_actions_still_request_fresh_parent_authentication(self):
    for feature in ('dns', 'browsing'):
      result, calls = self.invoke(feature, ['status'])
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(calls, ['sudo', '-k', '--', str(self.root / 'control'), feature, 'status'])

  def test_pr9750_routes_real_ui_commands_without_core_edits(self):
    if not (self.repo / 'bin/omarchy').is_file():
      self.skipTest('Set PR9750_SOURCE to the PR9750 checkout or installed runtime')
    for feature in ('dns', 'browsing'):
      result, calls = self.invoke(feature, ['ui'], routed=True)
      self.assertEqual(result.returncode, 0, result.stderr)
      self.assertEqual(calls, ['shell', 'shell', 'summon', 'io.github.peterholko.parent-' + feature])


if __name__ == '__main__':
  unittest.main(verbosity=2)
