"""Copy reviewed plugin interfaces into the current desktop user's plugin directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

INSTALLED = Path('/usr/share/omarchy-parent-addons/plugins')


def hashes(directory):
  result = {}
  for file in directory.rglob('*'):
    if file.is_symlink():
      raise ValueError(f'Refusing a symlink in {directory}')
    if file.is_file() and file.name != '.parent-addons-files.json':
      result[str(file.relative_to(directory))] = hashlib.sha256(file.read_bytes()).hexdigest()
  return result


def install(source, target, upgrade):
  if target.is_symlink():
    raise ValueError(f'Refusing a symlink: {target}')
  if target.exists():
    if not upgrade:
      raise ValueError(f'{target.name} already exists; use --upgrade after reviewing the new release')
    manifest = target / '.parent-addons-files.json'
    if not manifest.is_file() or json.loads(manifest.read_text()) != hashes(target):
      raise ValueError(f'{target.name} contains local changes. Back it up and remove it explicitly before replacing it.')
  target.parent.mkdir(parents=True, exist_ok=True)
  hashes(source)
  with tempfile.TemporaryDirectory(prefix='.parent-addons-', dir=target.parent) as scratch:
    stage = Path(scratch) / target.name
    shutil.copytree(source, stage)
    (stage / '.parent-addons-files.json').write_text(json.dumps(hashes(stage), indent=2) + '\n')
    subprocess.run(['omarchy-plugin-validate', str(stage)], check=True)
    backup = Path(scratch) / 'previous'
    if target.exists():
      target.rename(backup)
    try:
      stage.rename(target)
    except BaseException:
      if backup.exists():
        backup.rename(target)
      raise


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('action', choices=['install'])
  parser.add_argument('modules', nargs='+', choices=['dns', 'browsing'])
  parser.add_argument('--upgrade', action='store_true')
  args = parser.parse_args()
  if os.geteuid() == 0:
    parser.error('Run ./plugins as the child desktop user, without sudo')
  config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
  for feature in args.modules:
    plugin_id = 'io.github.peterholko.parent-' + feature
    source = INSTALLED / plugin_id
    if not source.is_dir():
      raise ValueError(f'Install the {feature} backend package first')
    install(source, config / 'omarchy/plugins' / plugin_id, args.upgrade)
    print('Installed ' + plugin_id + '. Enable it with: omarchy plugin enable ' + plugin_id)
    print('Open with: omarchy parent ' + feature + ' ui')
  subprocess.run(['omarchy-shell', 'shell', 'rescanPlugins'], check=True)
  print('After upgrading an already loaded plugin, run: omarchy restart shell')


if __name__ == '__main__':
  try:
    main()
  except (ValueError, OSError, subprocess.CalledProcessError) as error:
    raise SystemExit(str(error))
