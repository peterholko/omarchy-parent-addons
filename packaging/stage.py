"""Stage each package's complete file ownership without touching the host."""
from pathlib import Path
import shutil
import sys


def stage(source, destination, feature):
  source, destination = Path(source), Path(destination)
  if feature not in ('core', 'dns', 'browsing'):
    raise ValueError('Unknown package')
  mappings = [('LICENSE', 'usr/share/licenses/omarchy-parent-addons-' + feature + '/LICENSE', 0o644)]
  if feature == 'core':
    for name in ('control.py', 'parent.sh', 'files.py', 'control'):
      mappings.append(('backend/' + name, 'usr/lib/omarchy-parent-addons/' + name, 0o755 if name == 'control' else 0o644))
    mappings.append(('packaging/org.omarchy.parentaddons.policy', 'usr/share/polkit-1/actions/org.omarchy.parentaddons.policy', 0o644))
    for name in ('00-omarchy-parent-addons-remove.hook', '95-omarchy-parent-addons-browser.hook'):
      mappings.append(('packaging/' + name, 'usr/share/libalpm/hooks/' + name, 0o644))
  else:
    mappings.append(('backend/' + feature + '.sh', 'usr/lib/omarchy-parent-addons/' + feature + '.sh', 0o644))
    mappings.append(('bin/omarchy-parent-' + feature, 'usr/bin/omarchy-parent-' + feature, 0o755))
    for file in (source / 'backend/default').glob('omarchy-parent-' + feature + '.*'):
      mappings.append((str(file.relative_to(source)), 'usr/lib/omarchy-parent-addons/default/' + file.name, 0o644))
    if feature == 'dns':
      for name in ('dns-public-resolvers.list', 'dns-system.list', 'dns-system.deny'):
        mappings.append(('backend/default/' + name, 'usr/lib/omarchy-parent-addons/default/' + name, 0o644))
    plugin = 'io.github.peterholko.parent-' + feature
    for name in ('manifest.json', 'Panel.qml', 'ControlsView.qml', 'BarWidget.qml', 'README.md', 'LICENSE'):
      mappings.append(('dist/plugins/' + plugin + '/' + name, 'usr/share/omarchy-parent-addons/plugins/' + plugin + '/' + name, 0o644))
  for origin, target, mode in mappings:
    original, target = source / origin, destination / target
    if original.is_symlink() or not original.is_file():
      raise ValueError(f'Refusing an absent or symlinked source: {original}')
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in (target.parent, *target.parent.parents):
      if directory == destination:
        break
      directory.chmod(0o755)
    shutil.copyfile(original, target)
    target.chmod(mode)


if __name__ == '__main__':
  stage(*sys.argv[1:])
