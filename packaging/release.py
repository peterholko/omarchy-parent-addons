"""Record the exact built artifacts, without selecting arbitrary package files."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['omarchy-parent-addons-' + feature for feature in ('core', 'dns', 'browsing')]


def main():
  version = (ROOT / 'VERSION').read_text().strip() + '-1'
  packages = {}
  for name in NAMES:
    path = ROOT / 'dist/packages' / (name + '-' + version + '-any.pkg.tar.zst')
    info = subprocess.check_output(['pacman', '-Qp', str(path)], text=True).strip()
    if info != name + ' ' + version:
      raise ValueError(f'Unexpected package identity: {info}')
    packages[name] = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
  document = {'schemaVersion': 1, 'version': version, 'packages': packages}
  (ROOT / 'dist/packages/release.json').write_text(json.dumps(document, indent=2) + '\n')
  print('Built three standalone packages in dist/packages. No packages were installed.')


if __name__ == '__main__':
  main()
