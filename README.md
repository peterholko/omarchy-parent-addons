# Standalone parent web add-ons for PR9750

DNS filtering and browsing history, extracted from Omarchy Kids for an existing Omarchy Quattro child installation configured by PR9750. These add-ons use the laptop's existing parent/root password. They do not replace `omarchy`, `omarchy-settings`, the desktop, the account configuration, PAM or sudoers.

This is an initial source release. Build the Arch packages on the laptop; no new ISO or reinstall is needed. The extraction targets PR9750 at `56d2123dc93eafd3f0c5835b05d9019f9cf9748d`. It is separate from the full Omarchy Kids distribution and refuses an installed Kids backend. Automated checks pass; real Arch installation, parent authentication and networking still need the checks in [VALIDATION.md](VALIDATION.md).

## Repositories

- [Shared backend and release source](https://github.com/peterholko/omarchy-parent-addons) — this repository owns the packages and exports both interfaces.
- [DNS filtering plugin](https://github.com/peterholko/omarchy-parent-dns) — installable with `omarchy plugin add` after the DNS backend.
- [Browsing history plugin](https://github.com/peterholko/omarchy-parent-browsing) — installable with `omarchy plugin add` after the browsing backend.

The plugin repositories contain the user interface only. Installing either plugin does not install or upgrade privileged code. Each plugin README links back to the backend installation and lifecycle steps here.

## Packages and plugins

| Package | Purpose |
| --- | --- |
| `omarchy-parent-addons-core` | Shared configuration helpers, privilege entry point and lifecycle hooks |
| `omarchy-parent-addons-dns` | DNS filter, lists, firewall integration and DNS plugin |
| `omarchy-parent-addons-browsing` | History collector, timer, reports and browsing plugin |

The two optional packages depend only on the small shared package and ordinary system dependencies. DNS needs dnsmasq, UFW, NetworkManager, systemd and jq; browsing uses Python's built-in SQLite support and util-linux. The Quickshell plugin IDs are `io.github.peterholko.parent-dns` and `io.github.peterholko.parent-browsing`.

Both modules start disabled. Installing a package or enabling its shell plugin does not change DNS or start history collection. Existing enablement is preserved during an explicit upgrade.

## Build and install on a PR9750 child laptop

Run these in a terminal as the normal desktop user (for example, `linnea`), without starting a root shell. Package installation will request the existing parent password:

```bash
omarchy pkg add base-devel python
git clone --branch v0.1.2 --depth 1 https://github.com/peterholko/omarchy-parent-addons.git
cd omarchy-parent-addons
./test && ./build
```

`./test` runs only isolated fixtures. `./build` produces three `.pkg.tar.zst` archives and a checksummed manifest under `dist/packages`; it installs nothing. It also exports both complete plugin directories under `dist/plugins` and validates them with Omarchy's plugin validator.

Install the two backends, using the existing parent password when prompted:

```bash
./install dns browsing
```

The installer verifies package checksums and names before one pacman transaction. It only selects the three add-on package names above. To install one feature, pass only `dns` or `browsing`. It rejects a non-child installation rather than changing the account or authentication rules.

Still as the normal desktop user, install the user interfaces from their repositories:

```bash
omarchy plugin add https://github.com/peterholko/omarchy-parent-dns.git --enable
omarchy plugin add https://github.com/peterholko/omarchy-parent-browsing.git --enable
omarchy bar put io.github.peterholko.parent-dns --section right
omarchy bar put io.github.peterholko.parent-browsing --section right
```

Only use the corresponding lines if you installed one feature. Accept Omarchy's plugin confirmation and select the right bar section when prompted. The final two commands ensure the buttons are placed there. The bar buttons open the controls. You can also open them directly:

```bash
omarchy-shell shell summon io.github.peterholko.parent-dns
omarchy-shell shell summon io.github.peterholko.parent-browsing
```

The menus offer settings, status and reports. Each action opens the system parent authentication dialog. No password is collected or stored by these plugins. The interface clears reports when closed or after two minutes; an action already authorized continues independently of the panel.

## Enable features explicitly

Use the plugin controls or these terminal commands:

```bash
omarchy parent dns denylist
omarchy parent browsing on --user "$(id -un)"
```

DNS changes this laptop's resolver, adds its own marked blocks to the existing UFW rules, and installs managed browser policies. It requires UFW to be active before it changes DNS; it does not enable the firewall for you. The default upstream is Cloudflare for Families. Choose Network DNS in the plugin, or run `omarchy parent dns upstream auto`, when the local network's resolver is needed. Enabling allowlist mode requires choosing that mode explicitly.

Adding a domain to a list does not turn filtering on. In the DNS panel, choose **Denylist** under **Change mode**, then **Apply mode**, or use the command above. When filtering is on, a denied domain such as `youtube.com` is refused by DNS and added to the supported browsers' URL block policies, including its subdomains and paths. An entry such as `youtube.com/shorts` goes only to the browser policy because DNS cannot distinguish paths. Page exceptions do not override a whole-domain denial.

List changes clear the system resolver cache. Quit and reopen the browser after browser policy changes; the add-on does not close already loaded pages, ongoing video streams or existing browser connections. In Chromium, check `chrome://policy` and use **Reload policies**; `URLBlocklist` should contain the denied domain or path with status **OK**. In Firefox, check `about:policies`. The backend status lists policy files on disk; it cannot prove that a running browser has loaded them.

Browsing is opt-in. Tell the child when collection is enabled. The initial collection includes existing browser history; the timer then collects once a minute. Chromium, Google Chrome, Brave, Edge and Firefox history databases are supported. Firefox and Zen policies are supported, but Zen history discovery is not included in this extraction. The collector records URLs, titles and observed YouTube window titles; it is not a complete network capture or proof of time spent watching a video. Private browser windows are restricted by the supported browsers' managed policies. Alternate browsers, profiles or transport mechanisms can fall outside those policies.

Useful commands:

```bash
omarchy parent dns status
omarchy parent dns deny example.com
omarchy parent dns allow school.example
omarchy parent dns list
omarchy parent dns history 7
omarchy parent browsing status
omarchy parent browsing pages 7 --user "$(id -un)"
omarchy parent browsing videos 7 --user "$(id -un)"
```

Terminal commands use `sudo -k` for the action, so they do not reuse or leave a sudo credential cache. Graphical actions use a dedicated polkit action with `auth_admin`, which does not retain authorization. PR9750's existing admin rule identifies root as the parent.

## Browser installation and updates

The package hook reapplies enabled policies after supported browser package upgrades. PR9750's explicit browser installer can rewrite Firefox's policy file after the package transaction. After installing or reinstalling a browser, run these for the installed features, then restart the browser:

```bash
omarchy parent dns apply
omarchy parent browsing apply
```

These commands leave disabled modules disabled. Shared Firefox policy ownership preserves unrelated keys and the other add-on when a feature is disabled. Chromium policies have separate feature-owned files.

## Upgrade

Version 0.1.2 adds whole-domain denials to browser policies and clears the system resolver cache when lists change. **This requires the backend upgrade; updating only the shell plugin cannot apply it.** From an existing Git checkout of this backend, run as the normal desktop user:

```bash
git fetch origin tag v0.1.2
git switch --detach v0.1.2
./test && ./build && ./install --upgrade
```

The package upgrade reapplies an enabled DNS filter using its existing lists. An off filter stays off. Quit and reopen the browser afterward and verify `URLBlocklist` in `chrome://policy` or `WebsiteFilter` in `about:policies`. Existing v0.1.1 plugin interfaces work with this backend, so a plugin update is optional for this fix.

Version 0.1.1 fixes DNS and History panels staying invisible when opened from the bar. If you already have the v0.1.0 backend and installed the Git plugins, update just the interfaces; no backend rebuild is needed for this fix:

```bash
omarchy plugin update io.github.peterholko.parent-dns
omarchy plugin update io.github.peterholko.parent-browsing
omarchy restart shell
```

Download the next published backend source release into a new directory, review its release notes, then run there:

```bash
./test && ./build && ./install --upgrade
omarchy plugin update io.github.peterholko.parent-dns
omarchy plugin update io.github.peterholko.parent-browsing
omarchy restart shell
```

The backend installer updates the shared package and all previously installed features together. It requires the explicit `--upgrade` flag before replacing existing backend code. To add the second feature later, use `./install --upgrade browsing` or `./install --upgrade dns`. Settings, lists, enrollment and history survive.

Update only the plugins you have installed. The Git plugin updater presents changes for review. A plugin update changes only the user interface; the parent-authorized backend upgrade is separate.

### Alternative: install plugins from the backend package

For offline use or to keep the UI pinned to the exact backend release, run `./plugins install dns browsing` instead of the two `omarchy plugin add` commands, then enable each installed plugin with `omarchy plugin enable <id>`. These copies come from the root-owned package payload. Upgrade them with `./plugins install dns browsing --upgrade` after upgrading the backend. The installer refuses to overwrite local edits.

Use one UI installation method per plugin. Package copies are not Git checkouts and cannot use `omarchy plugin update`. To switch an existing package copy to its Git repository, run `omarchy plugin remove <id>`, then the corresponding `omarchy plugin add` command above. This switch leaves the installed backend and its settings in place.

## Disable and remove

Disable either feature without deleting its data:

```bash
omarchy parent dns off
omarchy parent browsing off --user "$(id -un)"
```

Remove a feature's backend package with:

```bash
./remove dns
./remove browsing
```

The package manager's pre-removal hook restores the module's owned settings and stops its service/timer. Its `AbortOnFail` setting leaves the package installed if restoration fails; repair the reported issue and retry. This also protects direct package-manager removal. [Arch hook semantics](https://man.archlinux.org/man/alpm-hooks.5.en)

Remove the corresponding user interface with:

```bash
omarchy plugin remove io.github.peterholko.parent-dns
omarchy plugin remove io.github.peterholko.parent-browsing
```

Removing or disabling only a shell plugin leaves the backend enforcing its existing settings. Removing DNS preserves browsing policy and logs; removing browsing preserves DNS. The shared core can be removed after both feature packages are gone with `omarchy pkg drop omarchy-parent-addons-core`.

Settings, allow/deny lists and collected history are deliberately retained. There is no automatic data purge.

## Installed paths

| Path | Ownership and purpose |
| --- | --- |
| `/usr/lib/omarchy-parent-addons/` | Package-owned backend code and service templates; root writable only |
| `/usr/bin/omarchy-parent-dns`, `/usr/bin/omarchy-parent-browsing` | Fixed wrappers that dispatch through parent authentication |
| `/etc/omarchy-parent-addons/` | Separate settings and lists; no writes to PR9750's `parent.conf` |
| `/var/lib/omarchy-parent-addons/USER/browsing/` | Root-only history, enrollment and cursors |
| `/run/omarchy-parent-addons/` | Runtime operation locks and DNS upstream state |
| `/etc/systemd/system/omarchy-parent-*` | Generated module units while enabled |
| `/usr/share/omarchy-parent-addons/plugins/` | Root-owned copies of the two plugin interfaces |
| `~/.config/omarchy/plugins/io.github.peterholko.parent-*` | User-owned, independently removable plugin copies |

The privileged entry point discards caller-controlled paths, interpreter hooks and test environment variables. It only dispatches fixed feature scripts and validates account names. It does not use the user-controlled plugin directory or an `OMARCHY_PATH` checkout to execute privileged code. DNS enforcement and history collection run through systemd independently of Quickshell.

## Validation

See [VALIDATION.md](VALIDATION.md) for completed checks and the remaining Linux installation checks. The portable Qt tests exercise the real views and plugin entry points, with inert Quickshell transport stubs for the latter. They do not establish that polkit, systemd, NetworkManager or UFW work on the laptop. No laptop, server or existing service was modified during development.

```bash
./test
# Optional on a development machine with PySide6 already installed:
QT_QPA_PLATFORM=offscreen python3 tests/visual.py
QT_QPA_PLATFORM=offscreen python3 tests/panel.py
```

MIT. Original source and exact revision are recorded in [SOURCE.json](SOURCE.json). The original license notice is retained in [LICENSE](LICENSE).
