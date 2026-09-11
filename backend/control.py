"""Root entry point; passwords are handled only by sudo or the OS polkit agent."""
import contextlib
import fcntl
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys

ROOT = Path('/usr/lib/omarchy-parent-addons')
CONFIG = Path('/etc/omarchy-parent-addons')
STATE = Path('/var/lib/omarchy-parent-addons')
OPERATIONS = {
  'dns': {'status', 'denylist', 'allowlist', 'off', 'allow', 'deny', 'remove', 'list', 'log', 'history', 'upstream', 'apply', 'upstreams', 'policies'},
  'browsing': {'status', 'on', 'off', 'videos', 'pages', 'collect', 'policies', 'apply'},
}


def root_owned(path):
  path = Path(path)
  info = path.lstat()
  if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
    raise ValueError(f'Refusing a writable or non-root-owned path: {path}')


def child_install():
  for path in ('/etc/omarchy', '/etc/omarchy/profile', '/etc/sudoers.d/omarchy-parent', '/etc/polkit-1/rules.d/40-omarchy-parent.rules'):
    root_owned(path)
  if Path('/etc/omarchy/profile').read_text().strip() != 'child':
    raise ValueError('These add-ons require an existing PR9750 child installation')
  rules = Path('/etc/sudoers.d/omarchy-parent').read_text()
  if not re.search(r'^Defaults\s+rootpw\s*$', rules, re.M):
    raise ValueError('PR9750 parent authentication is not configured')
  installed = subprocess.check_output(['/usr/bin/pacman', '-Qq'], text=True).splitlines()
  if any(name in installed for name in ('omarchy-kids-core', 'omarchy-parent-core', 'omarchy-kids-base')):
    raise ValueError('Remove or migrate the existing Kids backend before installing these standalone add-ons')
  for name in ('omarchy-kids', 'omarchy-parent-dns', 'omarchy-parent-browsing'):
    if (Path('/usr/share/omarchy/bin') / name).exists():
      raise ValueError('The base runtime already bundles Kids feature commands. Use the PR9750 runtime before adding these packages.')


def clean_environment():
  # Never trust OMARCHY_PATH, BASH_ENV, PYTHONPATH, test roots, caller PATH,
  # locale hooks or user-controlled helpers across the privilege boundary.
  return {'PATH': '/usr/bin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8',
          'ADDONS_PATH': str(ROOT), 'PARENT_ADDONS_STATE_DIR': str(STATE)}


def checked_user(name):
  if not re.fullmatch(r'[a-z_][a-z0-9_-]*[$]?', name):
    raise ValueError('Choose a valid local child account')
  account = pwd.getpwnam(name)
  if account.pw_uid < 1000 or not Path(account.pw_dir).is_absolute():
    raise ValueError('Choose a regular local child account')
  return account.pw_name


def validate(feature, args):
  if feature not in OPERATIONS:
    raise ValueError('Choose dns or browsing')
  args = list(args or ['status'])
  action, *values = args
  if action not in OPERATIONS[feature]:
    raise ValueError(f'Unknown {feature} action: {action}')
  if len(values) > 128 or any(len(value) > 4096 or '\x00' in value for value in values):
    raise ValueError('Too many arguments or an oversized value')
  if feature == 'browsing':
    if '--user' in values:
      index = values.index('--user')
      if values.count('--user') != 1 or index + 1 >= len(values):
        raise ValueError('--user needs one local account name')
      checked_user(values[index + 1])
    elif action in ('on', 'off', 'videos', 'pages'):
      uid = os.environ.get('PKEXEC_UID') or os.environ.get('SUDO_UID')
      if not uid or not uid.isdigit():
        raise ValueError('Supply --user NAME when running directly as root')
      args += ['--user', checked_user(pwd.getpwuid(int(uid)).pw_name)]
  return args


@contextlib.contextmanager
def operation_lock(feature):
  directory = Path('/run/omarchy-parent-addons')
  directory.mkdir(mode=0o755, exist_ok=True)
  root_owned(directory)
  fd = os.open(directory / (feature + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
  try:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
      raise ValueError('Unsafe operation lock')
    fcntl.flock(fd, fcntl.LOCK_EX)
    yield
  finally:
    os.close(fd)


def run(feature, args):
  script = ROOT / (feature + '.sh')
  root_owned(script)
  # DNS's ExecStartPre and the network dispatcher read upstream servers
  # while activation holds the DNS lock. They must not wait on that lock.
  lock = contextlib.nullcontext() if args[0] == 'upstreams' else operation_lock(feature)
  with lock:
    settings = CONFIG / 'settings.conf'
    configured = settings.read_text() if settings.exists() else ''
    dns_was_off = not re.search(r'^\s*dns\s*=\s*(denylist|allowlist)\s*$', configured, re.M)
    newly_enrolled = False
    if feature == 'browsing' and args[0] == 'on':
      username = args[args.index('--user') + 1]
      newly_enrolled = not (STATE / username / 'browsing/enabled').exists()
    if feature == 'dns' and args[0] in ('denylist', 'allowlist'):
      firewall = subprocess.check_output(['/usr/bin/ufw', 'status'], text=True, env=clean_environment())
      if not firewall.startswith('Status: active'):
        raise ValueError('DNS filtering requires your existing UFW firewall to be active. No networking settings were changed.')
    result = subprocess.run(['/bin/bash', '--noprofile', '--norc', str(script), *args],
                            env=clean_environment()).returncode
    if result and feature == 'dns' and args[0] in ('denylist', 'allowlist') and dns_was_off:
      rollback = subprocess.run(['/bin/bash', '--noprofile', '--norc', str(script), 'off'], env=clean_environment())
      print('DNS activation failed. ' + ('The filter was returned to off.' if rollback.returncode == 0 else
            'Restoration also failed; run omarchy parent dns off from the laptop terminal.'), file=sys.stderr)
    if result and newly_enrolled:
      rollback = subprocess.run(['/bin/bash', '--noprofile', '--norc', str(script), 'off', '--user', username], env=clean_environment())
      print('Browsing activation failed. ' + ('The new enrollment was disabled.' if rollback.returncode == 0 else
            'Restoration also failed; run omarchy parent browsing off --user ' + username + '.'), file=sys.stderr)
    return result


def main(argv=None):
  argv = list(sys.argv[1:] if argv is None else argv)
  if not argv or '--help' in argv or '-h' in argv:
    print('Usage: omarchy parent dns <status|denylist|allowlist|off|allow|deny|remove|list|log|history|upstream|apply> [VALUE ...]')
    print('       omarchy parent browsing <status|on|off|pages|videos> [DAYS] [--user NAME]')
    print('Uses the existing PR9750 parent password. Both add-ons start disabled.')
    return 0
  if os.geteuid() != 0:
    raise ValueError('Parent authentication is required; use the plugin or omarchy parent command')
  root_owned(ROOT)
  if argv[0] not in ('cleanup', 'pre-remove'):
    child_install()
  for directory, mode in ((CONFIG, 0o755), (STATE, 0o700)):
    directory.mkdir(mode=mode, exist_ok=True)
    root_owned(directory)
    directory.chmod(mode)
  os.umask(0o077)
  if argv == ['pre-remove']:
    names = set(sys.stdin.read().splitlines())
    for feature in OPERATIONS:
      if 'omarchy-parent-addons-' + feature in names:
        result = run(feature, ['cleanup'])
        if result:
          return result
    return 0
  if argv[0] == 'cleanup' and len(argv) == 2 and argv[1] in OPERATIONS:
    return run(argv[1], ['cleanup'])
  if argv == ['reapply']:
    for feature in OPERATIONS:
      if (ROOT / (feature + '.sh')).exists():
        result = run(feature, ['policies'])
        if result:
          return result
    return 0
  feature = argv[0]
  return run(feature, validate(feature, argv[1:]))


if __name__ == '__main__':
  try:
    raise SystemExit(main())
  except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
    print(f'Parent add-ons: {error}', file=sys.stderr)
    raise SystemExit(1)
