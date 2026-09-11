import hashlib
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1]
SHELL = os.environ.get('BASH_BIN') or shutil.which('bash')


def module(name, path):
  spec = importlib.util.spec_from_file_location(name, SOURCE / path)
  value = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(value)
  return value


files = module('addon_files', 'backend/files.py')
control = module('addon_control', 'backend/control.py')
installer = module('addon_installer', 'packaging/install.py')
plugins = module('addon_plugins', 'packaging/plugins.py')


class Scratch(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.root = Path(self.temporary.name)
    self.config = self.root / 'etc/omarchy-parent-addons'
    self.config.mkdir(parents=True)

  def tearDown(self):
    self.temporary.cleanup()

  def shell(self, feature, command, check=True, extra_env=None):
    content = (SOURCE / 'backend' / (feature + '.sh')).read_text()
    delimiter = '# --- end filter ---' if feature == 'dns' else '# --- end browsing ---'
    script = content.split(delimiter)[0]
    env = {**os.environ, 'ADDONS_PATH': str(SOURCE / 'backend'), 'PARENT_ADDONS_SYSROOT': str(self.root),
           'PARENT_ADDONS_STATE_DIR': str(self.root / 'state')}
    env.update(extra_env or {})
    result = subprocess.run([SHELL, '-c', 'umask 077\n' + script + '\n' + command], env=env, text=True, capture_output=True)
    if check:
      self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    return result


class SharedFiles(Scratch):
  def test_config_preserves_pr_and_other_keys(self):
    path = self.config / 'settings.conf'
    path.write_text('# Parent choices\ndns=off\nother=keep\n')
    files.config_change(path, 'document', 'dns', 'denylist')
    self.assertIn('dns=off', path.read_text())
    files.config_change(path, 'set', 'dns', 'allowlist')
    self.assertIn('other=keep', path.read_text())
    self.assertEqual(path.stat().st_mode & 0o777, 0o644)
    self.assertFalse((self.root / 'etc/omarchy/parent.conf').exists())

  def test_rejects_injected_keys_and_values(self):
    for key, value in [('dns\nevil', 'on'), ('dns', 'on\nother=yes')]:
      with self.assertRaises(ValueError):
        files.config_change(self.config / 'settings.conf', 'set', key, value)

  def test_symlink_is_not_followed(self):
    original = self.root / 'original'
    original.write_text('keep')
    link = self.config / 'settings.conf'
    link.symlink_to(original)
    with self.assertRaises(ValueError):
      files.config_change(link, 'set', 'dns', 'off')
    self.assertEqual(original.read_text(), 'keep')

  def test_independent_policy_removal_and_original_restoration(self):
    path = self.root / 'policies.json'
    baseline = {'policies': {'Homepage': {'URL': 'https://school.example'}, 'DNSOverHTTPS': {'Enabled': True}}}
    for first, second in (('dns', 'browsing'), ('browsing', 'dns')):
      with self.subTest(first=first):
        path.write_text(json.dumps(baseline))
        files.browser_change(path, 'dns', {'DNSOverHTTPS': {'Enabled': False, 'Locked': True}})
        files.browser_change(path, 'browsing', {'DisablePrivateBrowsing': True})
        files.browser_change(path, first, {})
        remaining = json.loads(path.read_text())['policies']
        if second == 'browsing':
          self.assertTrue(remaining['DisablePrivateBrowsing'])
          self.assertEqual(remaining['DNSOverHTTPS'], {'Enabled': True})
        else:
          self.assertNotIn('DisablePrivateBrowsing', remaining)
          self.assertEqual(remaining['DNSOverHTTPS'], {'Enabled': False, 'Locked': True})
        files.browser_change(path, second, {})
        self.assertEqual(json.loads(path.read_text()), baseline)
        self.assertFalse(path.with_name('.omarchy-parent-addons-policies.json').exists())

  def test_new_baseline_after_disabled_policy_is_edited(self):
    path = self.root / 'policies.json'
    path.write_text('{"policies": {}}')
    files.browser_change(path, 'browsing', {'DisablePrivateBrowsing': True})
    files.browser_change(path, 'browsing', {})
    path.write_text('{"policies": {"DisablePrivateBrowsing": false}}')
    files.browser_change(path, 'browsing', {'DisablePrivateBrowsing': True})
    files.browser_change(path, 'browsing', {})
    self.assertIs(json.loads(path.read_text())['policies']['DisablePrivateBrowsing'], False)

  def test_reapply_preserves_later_unrelated_browser_settings(self):
    path = self.root / 'policies.json'
    path.write_text('{"policies": {}}')
    files.browser_change(path, 'dns', {'DNSOverHTTPS': {'Enabled': False}})
    document = json.loads(path.read_text())
    document['policies']['Homepage'] = 'https://example.org'
    path.write_text(json.dumps(document))
    files.browser_change(path, 'dns', {'DNSOverHTTPS': {'Enabled': False}})
    self.assertEqual(json.loads(path.read_text())['policies']['Homepage'], 'https://example.org')


class DNS(Scratch):
  def test_removing_never_enabled_filter_does_not_restart_networking(self):
    result = self.shell('dns', 'systemctl() { echo UNEXPECTED-SERVICE; return 1; }; nmcli() { echo UNEXPECTED-NETWORK; return 1; }; turn_off')
    self.assertNotIn('UNEXPECTED', result.stdout)

  def test_disabled_by_default_and_apply_does_not_enable(self):
    result = self.shell('dns', 'dns_mode; apply; dns_mode')
    self.assertTrue(result.stdout.startswith('off\n'))
    self.assertTrue(result.stdout.endswith('off\n'))
    self.assertFalse((self.root / 'etc/systemd').exists())

  def test_lists_normalize_urls_and_reject_shell_fragments(self):
    self.shell('dns', 'edit_lists deny https://www.Example.com/shorts; edit_lists allow school.example; show_lists')
    self.assertIn('example.com/shorts', (self.config / 'dns.deny').read_text())
    bad = self.shell('dns', "edit_lists deny 'example.com;touch /tmp/bad'", check=False)
    self.assertNotEqual(bad.returncode, 0)

  def test_allowlist_has_system_exceptions_and_deny_precedence(self):
    result = self.shell('dns', 'ensure_lists; list_add "$ALLOW_FILE" school.example; list_add "$DENY_FILE" bad.school.example; dnsmasq_conf allowlist family')
    self.assertIn('school.example', result.stdout)
    self.assertIn('archlinux.org', result.stdout)
    self.assertIn('address=/bad.school.example/', result.stdout)
    self.assertIn('address=/#/', result.stdout)

  def test_url_paths_are_browser_policy_not_dns_names(self):
    result = self.shell('dns', 'ensure_lists; list_add "$DENY_FILE" youtube.com/shorts; chromium_policy_json; dnsmasq_conf denylist family')
    self.assertIn('youtube.com/shorts', result.stdout)
    self.assertNotIn('address=/youtube.com/shorts', result.stdout)

  def test_whole_domain_denials_reach_browser_policies(self):
    chromium = self.root / 'etc/chromium/policies/managed'
    chromium.mkdir(parents=True)
    firefox = self.root / 'usr/lib/firefox/distribution/policies.json'
    firefox.parent.mkdir(parents=True)
    baseline = {'policies': {'DisablePrivateBrowsing': True, 'Homepage': {'URL': 'https://school.example'}}}
    firefox.write_text(json.dumps(baseline))
    self.shell('dns', 'ensure_lists; list_add "$DENY_FILE" youtube.com; list_add "$DENY_FILE" example.org/shorts; install_browser_policies')
    policy = json.loads((chromium / 'omarchy-parent-dns.json').read_text())
    self.assertEqual(policy['URLBlocklist'], ['youtube.com', 'example.org/shorts'])
    rules = json.loads(firefox.read_text())['policies']
    self.assertEqual(rules['WebsiteFilter']['Block'], ['*://youtube.com/*', '*://*.youtube.com/*', '*://example.org/shorts*', '*://*.example.org/shorts*'])
    self.assertTrue(rules['DisablePrivateBrowsing'])
    self.shell('dns', 'remove_browser_policies')
    self.assertFalse((chromium / 'omarchy-parent-dns.json').exists())
    self.assertEqual(json.loads(firefox.read_text()), baseline)

  def test_page_exceptions_cannot_override_whole_domain_denials(self):
    result = self.shell('dns', 'ensure_lists; list_add "$DENY_FILE" youtube.com; list_add "$ALLOW_FILE" youtube.com/school; list_add "$ALLOW_FILE" www.youtube.com/school; list_add "$ALLOW_FILE" notyoutube.com/school; list_add "$ALLOW_FILE" school.example/lesson; chromium_policy_json')
    self.assertEqual(json.loads(result.stdout)['URLAllowlist'], ['notyoutube.com/school', 'school.example/lesson'])

  def test_saving_denial_while_off_reports_that_filtering_is_disabled(self):
    result = self.shell('dns', 'systemctl() { echo UNEXPECTED-SERVICE; return 1; }; resolvectl() { echo UNEXPECTED-CACHE; return 1; }; edit_lists deny youtube.com')
    self.assertIn('filtering is not enabled', result.stdout)
    self.assertIn('omarchy parent dns denylist', result.stdout)
    self.assertNotIn('UNEXPECTED', result.stdout)
    self.assertNotIn('policies updated', result.stdout)
    self.assertIn('youtube.com', (self.config / 'dns.deny').read_text())

  def test_active_list_edits_flush_the_downstream_resolver_cache(self):
    result = self.shell('dns', '''
conf_set dns denylist
systemctl() { printf 'systemctl %s\\n' "$*" >>"$SYSROOT/calls"; }
resolvectl() { printf 'resolvectl %s\\n' "$*" >>"$SYSROOT/calls"; }
edit_lists deny youtube.com
''')
    self.assertEqual((self.root / 'calls').read_text().splitlines(), ['systemctl restart omarchy-parent-dns.service', 'resolvectl flush-caches'])
    self.assertIn('address=/youtube.com/', (self.config / 'dnsmasq.conf').read_text())
    self.assertIn('Resolver cache cleared and browser policies updated', result.stdout)

  def test_reapply_flushes_old_cached_answers(self):
    self.shell('dns', '''
conf_set dns denylist
systemd_running() { return 0; }
firewall_closed() { return 0; }
systemctl() { printf 'systemctl %s\\n' "$*" >>"$SYSROOT/calls"; }
resolvectl() { printf 'resolvectl %s\\n' "$*" >>"$SYSROOT/calls"; }
status() { echo "Fixture status"; }
apply
''')
    self.assertEqual((self.root / 'calls').read_text().splitlines()[-2:], ['systemctl restart omarchy-parent-dns.service', 'resolvectl flush-caches'])

  def test_firewall_restores_other_rules(self):
    directory = self.root / 'etc/ufw'
    directory.mkdir(parents=True)
    baseline = '# Existing application rules\n*filter\nCOMMIT\n'
    for name in ('after.rules', 'after6.rules'):
      (directory / name).write_text(baseline)
    self.shell('dns', 'ufw() { echo "Status: inactive"; }; install_firewall_block; install_firewall_block; remove_firewall_block')
    for name in ('after.rules', 'after6.rules'):
      self.assertEqual((directory / name).read_text(), baseline)


class Browsing(Scratch):
  def database(self, kind):
    path = self.root / (kind + '.sqlite')
    con = sqlite3.connect(path)
    if kind == 'chromium':
      con.executescript('CREATE TABLE urls(id INTEGER, url TEXT, title TEXT); CREATE TABLE visits(url INTEGER, visit_time INTEGER);')
      con.execute('INSERT INTO urls VALUES(1, ?, ?)', ('https://school.example/lesson', 'A lesson'))
      con.execute('INSERT INTO visits VALUES(1, ?)', ((1700000000 + 11644473600) * 1000000,))
    else:
      con.executescript('CREATE TABLE moz_places(id INTEGER, url TEXT, title TEXT); CREATE TABLE moz_historyvisits(place_id INTEGER, visit_date INTEGER);')
      con.execute('INSERT INTO moz_places VALUES(1, ?, ?)', ('https://school.example/lesson', 'A lesson'))
      con.execute('INSERT INTO moz_historyvisits VALUES(1, ?)', (1700000000 * 1000000,))
    con.commit()
    con.close()
    return path

  def test_real_chromium_and_firefox_histories(self):
    for kind in ('chromium', 'firefox'):
      path = self.database(kind)
      result = self.shell('browsing', 'extract_visits "$HISTORY_TEST" "$HISTORY_KIND" 0', extra_env={'HISTORY_TEST': str(path), 'HISTORY_KIND': kind})
      self.assertIn('1700000000\thttps://school.example/lesson\tA lesson', result.stdout)
      cursor = result.stderr.strip()
      again = self.shell('browsing', 'extract_visits "$HISTORY_TEST" "$HISTORY_KIND" "$CURSOR"', extra_env={'HISTORY_TEST': str(path), 'HISTORY_KIND': kind, 'CURSOR': cursor})
      self.assertEqual(again.stdout, '')

  def test_turn_off_preserves_history(self):
    directory = self.root / 'state/linnea/browsing'
    directory.mkdir(parents=True)
    (directory / 'enabled').touch()
    (directory / 'visits.tsv').write_text('1700000000\thttps://school.example\tLesson\n')
    self.shell('browsing', 'systemd_running() { return 1; }; turn_off linnea')
    self.assertFalse((directory / 'enabled').exists())
    self.assertIn('school.example', (directory / 'visits.tsv').read_text())


class Boundary(unittest.TestCase):
  def test_failed_browsing_activation_removes_only_new_enrollment(self):
    with tempfile.TemporaryDirectory() as directory:
      with mock.patch.object(control, 'CONFIG', Path(directory)), mock.patch.object(control, 'STATE', Path(directory)), \
           mock.patch.object(control, 'root_owned'), mock.patch.object(control, 'operation_lock', return_value=contextlib.nullcontext()), \
           mock.patch.object(control.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]) as run, \
           contextlib.redirect_stderr(io.StringIO()):
        self.assertEqual(control.run('browsing', ['on', '--user', 'linnea']), 1)
        self.assertEqual(run.call_args_list[-1].args[0][-3:], ['off', '--user', 'linnea'])

  def test_failed_fresh_dns_activation_rolls_back(self):
    with tempfile.TemporaryDirectory() as directory:
      with mock.patch.object(control, 'CONFIG', Path(directory)), mock.patch.object(control, 'root_owned'), \
           mock.patch.object(control, 'operation_lock', return_value=contextlib.nullcontext()), \
           mock.patch.object(control.subprocess, 'check_output', return_value='Status: active\n'), \
           mock.patch.object(control.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]) as run, \
           contextlib.redirect_stderr(io.StringIO()):
        self.assertEqual(control.run('dns', ['denylist']), 1)
        self.assertEqual(run.call_args_list[-1].args[0][-1], 'off')

  def test_inactive_firewall_fails_before_changing_dns(self):
    with tempfile.TemporaryDirectory() as directory:
      with mock.patch.object(control, 'CONFIG', Path(directory)), mock.patch.object(control, 'root_owned'), \
           mock.patch.object(control, 'operation_lock', return_value=contextlib.nullcontext()), \
           mock.patch.object(control.subprocess, 'check_output', return_value='Status: inactive\n'), \
           mock.patch.object(control.subprocess, 'run') as run:
        with self.assertRaisesRegex(ValueError, 'firewall'):
          control.run('dns', ['denylist'])
        run.assert_not_called()

  def test_unprivileged_reports_are_refused(self):
    with mock.patch.object(control.os, 'geteuid', return_value=1000), mock.patch.object(control, 'run') as run:
      with self.assertRaisesRegex(ValueError, 'authentication'):
        control.main(['browsing', 'pages', '--user', 'linnea'])
      run.assert_not_called()

  def test_control_ignores_caller_environment(self):
    with mock.patch.dict(os.environ, {'PATH': '/tmp/evil', 'BASH_ENV': '/tmp/evil', 'OMARCHY_PATH': '/tmp/evil', 'PARENT_ADDONS_SYSROOT': '/tmp/evil', 'PYTHONPATH': '/tmp/evil'}):
      env = control.clean_environment()
      self.assertEqual(env['PATH'], '/usr/bin:/bin')
      for name in ('BASH_ENV', 'OMARCHY_PATH', 'PARENT_ADDONS_SYSROOT', 'PYTHONPATH'):
        self.assertNotIn(name, env)

  def test_user_names_cannot_select_paths(self):
    for value in ('../../root', '/etc', 'root', 'bad\nname'):
      with self.assertRaises((ValueError, KeyError)):
        control.checked_user(value)

  def test_existing_root_password_files_are_read_only_inputs(self):
    source = (SOURCE / 'backend/control.py').read_text()
    self.assertIn('Defaults\\s+rootpw', source)
    for path in SOURCE.rglob('*'):
      if path.suffix in ('.sh', '.py') and 'tests' not in path.parts and path.is_file():
        self.assertNotIn('chpasswd', path.read_text())

  def test_root_backend_upgrade_requires_explicit_flag(self):
    with self.assertRaises(ValueError):
      installer.selection(['dns'], {'omarchy-parent-addons-core'}, False)
    self.assertEqual(installer.selection([], {'omarchy-parent-addons-core', 'omarchy-parent-addons-dns'}, True), {'core', 'dns'})

  def test_requesting_browsing_preserves_installed_dns(self):
    self.assertEqual(installer.selection(['browsing'], {'omarchy-parent-addons-dns'}, True), {'core', 'dns', 'browsing'})


if __name__ == '__main__':
  unittest.main(verbosity=2)
