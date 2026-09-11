import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from test_addons import SOURCE, SHELL, module, installer, plugins

stager = module('addon_stage', 'packaging/stage.py')
exporter = module('addon_export', 'packaging/export.py')


class Packaging(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.root = Path(self.temporary.name)
    exporter.export(SOURCE / 'dist/plugins')

  def tearDown(self):
    self.temporary.cleanup()

  def test_actual_package_recipes_have_disjoint_ownership_outside_omarchy(self):
    ownership = {}
    for feature in ('core', 'dns', 'browsing'):
      destination = self.root / feature
      destination.mkdir()
      env = {**os.environ, 'PARENT_ADDONS_SOURCE': str(SOURCE), 'pkgdir': str(destination)}
      subprocess.run([SHELL, '-euc', 'source "$PARENT_ADDONS_SOURCE/PKGBUILD"; package_omarchy-parent-addons-' + feature], env=env, check=True)
      paths = {str(path.relative_to(destination)) for path in destination.rglob('*') if path.is_file()}
      self.assertTrue(paths)
      for path in paths:
        self.assertNotIn(path, ownership, 'Packages must not own the same file')
        self.assertFalse(path.startswith(('usr/share/omarchy/', 'etc/')), path)
        ownership[path] = feature
      for path in destination.rglob('*'):
        if path.is_file():
          self.assertEqual(path.stat().st_mode & 0o022, 0, str(path))
      if feature != 'core':
        wrapper = destination / ('usr/bin/omarchy-parent-' + feature)
        self.assertTrue(wrapper.stat().st_mode & 0o111)
        plugin = destination / ('usr/share/omarchy-parent-addons/plugins/io.github.peterholko.parent-' + feature)
        manifest = json.loads((plugin / 'manifest.json').read_text())
        self.assertEqual(manifest['kinds'], ['panel'])
        self.assertEqual(manifest['entryPoints'], {'panel': 'Panel.qml'})
        self.assertNotIn('barWidget', manifest)
        self.assertFalse((plugin / 'BarWidget.qml').exists())

  def test_export_removes_obsolete_bar_widgets(self):
    destination = self.root / 'plugins'
    for feature in ('dns', 'browsing'):
      plugin = destination / ('io.github.peterholko.parent-' + feature)
      plugin.mkdir(parents=True)
      (plugin / 'BarWidget.qml').write_text('// Previous release widget\n')
    exporter.export(destination)
    for plugin in destination.iterdir():
      self.assertFalse((plugin / 'BarWidget.qml').exists())
      self.assertEqual(json.loads((plugin / 'manifest.json').read_text())['kinds'], ['panel'])

  def test_no_dependency_replaces_or_upgrades_pr_runtime(self):
    env = {**os.environ, 'PARENT_ADDONS_SOURCE': str(SOURCE), 'pkgdir': str(self.root / 'pkg')}
    for feature in ('core', 'dns', 'browsing'):
      script = 'source "$PARENT_ADDONS_SOURCE/PKGBUILD"; python3() { :; }; package_omarchy-parent-addons-' + feature + '; printf "%s\\n" "${depends[@]}" "${provides[@]}" "${replaces[@]}"'
      dependencies = subprocess.check_output([SHELL, '-ec', script], env=env, text=True)
      for line in dependencies.splitlines():
        self.assertFalse(line.startswith(('omarchy-kids-', 'omarchy-settings', 'omarchy-base')))
        self.assertNotEqual(line, 'omarchy')

  def test_manifest_checksums_reject_corruption_before_install(self):
    packages = {}
    for feature in ('core', 'dns', 'browsing'):
      name = 'omarchy-parent-addons-' + feature
      filename = name + '-0.1.0-1-any.pkg.tar.zst'
      (self.root / filename).write_bytes(b'package fixture')
      packages[name] = {'file': filename, 'sha256': hashlib.sha256(b'package fixture').hexdigest()}
    (self.root / 'release.json').write_text(json.dumps({'schemaVersion': 1, 'version': '0.1.0-1', 'packages': packages}))
    stage = self.root / 'stage'
    stage.mkdir()
    (self.root / packages['omarchy-parent-addons-core']['file']).write_bytes(b'changed')
    with mock.patch.object(installer.subprocess, 'check_output') as verify:
      with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
        installer.copy_verified(self.root, stage, {'core'})
      verify.assert_not_called()

  def test_package_identity_cannot_replace_base(self):
    packages = {}
    for feature in ('core', 'dns', 'browsing'):
      name = 'omarchy-parent-addons-' + feature
      filename = name + '.pkg.tar.zst'
      (self.root / filename).write_bytes(b'package')
      packages[name] = {'file': filename, 'sha256': hashlib.sha256(b'package').hexdigest()}
    (self.root / 'release.json').write_text(json.dumps({'schemaVersion': 1, 'version': '0.1.0-1', 'packages': packages}))
    stage = self.root / 'stage'
    stage.mkdir()
    with mock.patch.object(installer.subprocess, 'check_output', return_value='omarchy 4.0.0\n'):
      with self.assertRaisesRegex(ValueError, 'identity mismatch'):
        installer.copy_verified(self.root, stage, {'core'})

  def test_plugin_upgrade_preserves_local_edits(self):
    source = SOURCE / 'dist/plugins/io.github.peterholko.parent-dns'
    target = self.root / 'plugins/dns'
    with mock.patch.object(plugins.subprocess, 'run'):
      plugins.install(source, target, False)
      (target / 'Panel.qml').write_text('// My custom panel\n')
      with self.assertRaisesRegex(ValueError, 'local changes'):
        plugins.install(source, target, True)
    self.assertEqual((target / 'Panel.qml').read_text(), '// My custom panel\n')

  def test_native_prompt_never_remembers_authorization(self):
    document = ET.parse(SOURCE / 'packaging/org.omarchy.parentaddons.policy')
    self.assertEqual(document.findtext('action/defaults/allow_active'), 'auth_admin')
    self.assertEqual(document.findtext('action/defaults/allow_inactive'), 'no')
    self.assertEqual(document.findtext('action/annotate'), '/usr/lib/omarchy-parent-addons/control')
    for feature in ('dns', 'browsing'):
      self.assertIn('sudo -k --', (SOURCE / 'bin' / ('omarchy-parent-' + feature)).read_text())

  def test_removal_restoration_is_pretransaction_and_fail_closed(self):
    hook = (SOURCE / 'packaging/00-omarchy-parent-addons-remove.hook').read_text()
    self.assertIn('When = PreTransaction', hook)
    self.assertIn('AbortOnFail', hook)
    self.assertIn('NeedsTargets', hook)
    self.assertIn('control pre-remove', hook)

  def test_pr9750_routes_external_command_without_core_edits(self):
    repo = Path(os.environ.get('PR9750_SOURCE', os.environ.get('OMARCHY_PATH', str(SOURCE.parents[1]))))
    if not (repo / 'bin/omarchy').is_file():
      self.skipTest('Set PR9750_SOURCE to the PR9750 checkout or installed runtime')
    binary = self.root / 'omarchy-parent-dns'
    binary.write_text('#!/bin/bash\nprintf "dispatched:%s\\n" "$@"\n')
    binary.chmod(0o755)
    env = {**os.environ, 'OMARCHY_PATH': str(repo), 'PATH': str(self.root) + ':' + str(repo / 'bin') + ':' + os.environ['PATH']}
    result = subprocess.run([SHELL, str(repo / 'bin/omarchy'), 'parent', 'dns', 'status'], env=env, capture_output=True, text=True)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(result.stdout, 'dispatched:status\n')


if __name__ == '__main__':
  unittest.main(verbosity=2)
