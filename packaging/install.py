"""Install only standalone add-on packages; never replace the PR9750 runtime."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
PREFIX = 'omarchy-parent-addons-'
MODULES = ('dns', 'browsing')


def selection(requested, installed, upgrade):
  existing = {name[len(PREFIX):] for name in installed if name in {PREFIX + m for m in MODULES}}
  if any(name.startswith(PREFIX) for name in installed) and not upgrade:
    raise ValueError('Add-ons are already installed. Use --upgrade to explicitly update the root-owned backend.')
  return {'core'} | existing | set(requested or (existing if upgrade else MODULES))


def copy_verified(directory, stage, selected):
  release = json.loads((directory / 'release.json').read_text())
  if release.get('schemaVersion') != 1:
    raise ValueError('Unsupported release manifest')
  wanted = {PREFIX + name for name in selected}
  allowed = {PREFIX + name for name in ('core', *MODULES)}
  if set(release['packages']) != allowed or not wanted <= allowed:
    raise ValueError('Release contains missing or unexpected package names')
  output = []
  for name in sorted(wanted):
    item = release['packages'][name]
    filename = item['file']
    if Path(filename).name != filename or not filename.endswith('.pkg.tar.zst'):
      raise ValueError('Unsafe package filename')
    source = directory / filename
    if source.is_symlink():
      raise ValueError('Package archives must be regular files')
    target = stage / filename
    shutil.copyfile(source, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != item['sha256']:
      raise ValueError(f'Checksum mismatch: {filename}')
    identity = subprocess.check_output(['/usr/bin/pacman', '-Qp', str(target)], text=True).strip()
    if identity != name + ' ' + release['version']:
      raise ValueError(f'Package identity mismatch: {filename}')
    output.append(target)
  return output


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('modules', nargs='*', choices=MODULES)
  parser.add_argument('--upgrade', action='store_true')
  parser.add_argument('--packages', type=Path, default=SOURCE / 'dist/packages')
  args = parser.parse_args()
  if os.geteuid() != 0 or os.uname().sysname != 'Linux':
    parser.error('Run ./install from the Omarchy laptop, using the parent password')
  spec = importlib.util.spec_from_file_location('parent_control_preflight', SOURCE / 'backend/control.py')
  control = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(control)
  control.child_install()
  installed = set(subprocess.check_output(['/usr/bin/pacman', '-Qq'], text=True).splitlines())
  selected = selection(args.modules, installed, args.upgrade)
  os.umask(0o077)
  with tempfile.TemporaryDirectory(prefix='parent-addons-') as scratch:
    archives = copy_verified(args.packages, Path(scratch), selected)
    print('Installing only: ' + ', '.join(sorted(PREFIX + m for m in selected)), flush=True)
    subprocess.run(['/usr/bin/pacman', '-U', *map(str, archives)], check=True)
  print('Backend installed. New modules are disabled. Existing enablement was preserved.')
  print('Install or update the user interfaces as your normal desktop user:')
  print('https://github.com/peterholko/omarchy-parent-addons#build-and-install-on-a-pr9750-child-laptop')
  print('For package-based UI copies, see the alternative installation method in README.md.')


if __name__ == '__main__':
  try:
    main()
  except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
    raise SystemExit(f'Installation stopped: {error}')
