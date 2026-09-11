"""Atomic configuration and shared Firefox policy ownership for two add-ons."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile


def regular(path):
  path = Path(path)
  if path.is_symlink() or (path.exists() and not path.is_file()):
    raise ValueError(f'Refusing non-regular file: {path}')


@contextlib.contextmanager
def locked(path):
  path = Path(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
  try:
    if not stat.S_ISREG(os.fstat(fd).st_mode):
      raise ValueError(f'Refusing non-regular lock: {path}')
    fcntl.flock(fd, fcntl.LOCK_EX)
    yield
  finally:
    os.close(fd)


def write(path, text, mode=0o600):
  path = Path(path)
  regular(path)
  path.parent.mkdir(parents=True, exist_ok=True)
  fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
  try:
    os.fchmod(fd, mode)
    with os.fdopen(fd, 'w') as out:
      out.write(text)
      out.flush()
      os.fsync(out.fileno())
    os.replace(name, path)
  finally:
    if os.path.exists(name):
      os.unlink(name)


def read_json(path, default):
  regular(path)
  return json.loads(path.read_text()) if path.exists() else default


def config_change(path, operation, key, value, comments=()):
  path = Path(path)
  if operation not in ('set', 'document') or not re.fullmatch(r'[a-z][a-z0-9_]*', key):
    raise ValueError('Invalid configuration operation or key')
  if '\n' in value or '\r' in value:
    raise ValueError('Configuration values must be a single line')
  with locked(path.with_name('.' + path.name + '.lock')):
    regular(path)
    text = path.read_text() if path.exists() else '# Standalone Omarchy parent add-ons.\n'
    pattern = re.compile(r'^\s*' + re.escape(key) + r'\s*=.*$', re.M)
    if operation == 'document' and pattern.search(text):
      return
    if pattern.search(text):
      text = pattern.sub(lambda _: key + '=' + value, text)
    else:
      text = text.rstrip() + '\n\n' + ''.join('# ' + c + '\n' for c in comments) + key + '=' + value + '\n'
    write(path, text, 0o644)


def browser_change(path, module, fragment):
  path = Path(path)
  if module not in ('dns', 'browsing') or not isinstance(fragment, dict):
    raise ValueError('Invalid browser policy contribution')
  ledger = path.with_name('.omarchy-parent-addons-policies.json')
  with locked(path.with_name('.omarchy-parent-addons-policies.lock')):
    document = read_json(path, {'policies': {}})
    policy = document.setdefault('policies', {})
    state = read_json(ledger, {'base': {}, 'contributions': {}})
    for key in fragment:
      state['base'].setdefault(key, {'present': key in policy, 'value': policy.get(key)})
    if fragment:
      state['contributions'][module] = fragment
    else:
      state['contributions'].pop(module, None)
    for key, old in state['base'].items():
      if old['present']:
        policy[key] = old['value']
      else:
        policy.pop(key, None)
    for owner in sorted(state['contributions']):
      policy.update(state['contributions'][owner])
    # Ownership is durable before policy replacement, so retrying an
    # interrupted write retains both modules' original baseline.
    write(ledger, json.dumps(state, indent=2) + '\n')
    write(path, json.dumps(document, indent=2) + '\n', 0o644)
    if not state['contributions']:
      ledger.unlink()


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('kind', choices=['config', 'browser'])
  parser.add_argument('path', type=Path)
  parser.add_argument('values', nargs='+')
  args = parser.parse_args()
  if args.kind == 'browser':
    module, fragment = args.values
    browser_change(args.path, module, json.loads(fragment))
  else:
    operation, key, value, *comments = args.values
    config_change(args.path, operation, key, value, comments)


if __name__ == '__main__':
  main()
