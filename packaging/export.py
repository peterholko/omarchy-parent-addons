"""Export the two complete plugin roots without importing Kids or replacing Omarchy."""
import json
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parents[1]
FEATURES = {'dns': ('DNS filtering', 'DNS'), 'browsing': ('Browsing history', 'History')}
BACKEND = 'https://github.com/peterholko/omarchy-parent-addons'


def export(destination):
  destination = Path(destination)
  version = (SOURCE / 'VERSION').read_text().strip()
  for feature, (title, label) in FEATURES.items():
    plugin_id = 'io.github.peterholko.parent-' + feature
    root = destination / plugin_id
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
      'schemaVersion': 1, 'id': plugin_id, 'name': title, 'version': version,
      'author': 'Peter Holko', 'description': title + ' for PR9750 child installations',
      'kinds': ['panel', 'bar-widget'], 'keepLoaded': True,
      'entryPoints': {'panel': 'Panel.qml', 'barWidget': 'BarWidget.qml'},
      'barWidget': {'defaultSection': 'right'},
    }
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for name in ('Panel.qml', 'ControlsView.qml', 'BarWidget.qml'):
      text = (SOURCE / 'ui' / name).read_text().replace('@FEATURE@', feature).replace('@ID@', plugin_id).replace('@LABEL@', label)
      (root / name).write_text(text)
    shutil.copy2(SOURCE / 'LICENSE', root / 'LICENSE')
    shutil.copy2(SOURCE / 'SOURCE.json', root / 'SOURCE.json')
    (root / 'README.md').write_text(f'''# {title}

Omarchy Quattro plugin for a child installation configured by [PR9750](https://github.com/omacom/omarchy/pull/9750). It uses the existing OS parent password through polkit. No password is stored in the plugin.

This repository contains the user interface. Version {version} requires the separately installed `omarchy-parent-addons-{feature}` and `omarchy-parent-addons-core` packages from [backend release v{version}]({BACKEND}/releases/tag/v{version}). The backend does not depend on the Omarchy Kids distribution or replace Omarchy. Linux installation and authentication checks are still pending; see the [validation record]({BACKEND}/blob/v{version}/VALIDATION.md).

## Install

First follow the [backend build and installation instructions]({BACKEND}#build-and-install-on-a-pr9750-child-laptop) as the normal desktop user. Select `./install {feature}` for this feature, or `./install dns browsing` for both. If you already installed the other feature, use `./install --upgrade {feature}` from the matching backend release. The installer requests the existing parent password. No ISO or reinstall is needed.

Then install this interface, still as the normal desktop user:

```bash
omarchy plugin add https://github.com/peterholko/omarchy-parent-{feature}.git --enable
omarchy bar put {plugin_id} --section right
omarchy-shell shell summon {plugin_id}
```

Accept Omarchy's plugin confirmation and select the right bar section when prompted. If you already have a package-based copy with this ID, remove that user interface with `omarchy plugin remove {plugin_id}` before adding the Git copy. This leaves the backend and its settings in place.

## Enable and use

Installing or enabling the plugin does not enable filtering or collection. Use the explicit controls inside its panel. Private reports require parent authentication and clear when the window closes or after two minutes. DNS filtering changes this laptop's resolver, firewall and supported browser policies. Browsing logs are opt-in; tell the child when collection is enabled.

{'DNS requires an already active UFW firewall. It defaults to Cloudflare for Families upstream; Network DNS is available in the controls. Enable Denylist explicitly to begin filtering.' if feature == 'dns' else 'The first collection includes existing history, followed by collection every minute. Supported history databases are Chromium, Chrome, Brave, Edge and Firefox. The collector records URLs and titles; it does not capture every network request or establish time spent watching a video.'}

The [backend README]({BACKEND}#enable-features-explicitly) documents terminal commands, browser support, policy limitations and the manual `apply` step after installing or reinstalling browsers.

## Upgrade

Follow the [backend upgrade steps]({BACKEND}#upgrade) first when a release changes privileged code. Then update this interface:

```bash
omarchy plugin update {plugin_id}
omarchy restart shell
```

A plugin update cannot upgrade its root-owned backend. Package-based UI copies use the backend release's `./plugins install {feature} --upgrade` instead of the Git updater.

## Disable and remove

Disable the backend with `omarchy parent {feature} off{' --user "$(id -un)"' if feature == 'browsing' else ''}`. From the backend source directory, run `./remove {feature}` to restore owned integration files and remove the backend package. Remove this interface with:

```bash
omarchy plugin remove {plugin_id}
```

Logs and settings are retained. Removing only the shell plugin leaves the backend running. See the [complete removal procedure]({BACKEND}#disable-and-remove).

## Source

This interface is generated from the [shared source]({BACKEND}/tree/v{version}/ui) by `packaging/export.py`. Changes should be made there and exported to this repository. Both exported plugin roots pass PR9750's plugin validator. Portable Qt tests use inert Quickshell transport stubs; real Linux runtime validation remains pending.

MIT. Extracted from [Omarchy Kids](https://github.com/peterholko/omarchy-kids) with standalone PR9750 adapters. [SOURCE.json](SOURCE.json) records the original revision and provenance; [LICENSE](LICENSE) retains the original license notice.
''')
  return destination


if __name__ == '__main__':
  print(export(Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE / 'dist/plugins'))
