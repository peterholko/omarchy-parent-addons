# Validation record

Development and verification were performed on the Mac against the PR9750 source at `56d2123dc93eafd3f0c5835b05d9019f9cf9748d`. This release has not been installed on Linnea's laptop, the `perilous` server, or a Linux VM.

## Completed

- 36 focused Python/Bash tests pass. They cover real Chromium and Firefox SQLite history extraction, incremental cursors, default-off behavior, isolated configuration, both Firefox policy removal orders, existing UFW rule preservation, failed-activation rollback, inactive-firewall preflight, and removal of a never-enabled filter without restarting networking.
- Version 0.1.2 tests verify that whole-domain denials reach the actual generated Chromium and Firefox policy files, that removing those policies preserves unrelated browser settings, that page exceptions cannot override a whole-domain denial, and that off-state list edits do not activate services. Fixture command traces verify cache flushes after active list edits and reapplication. These traces do not replace live Linux DNS and browser tests.
- The actual three PKGBUILD package functions were executed against scratch staging directories. Their file ownership is disjoint, file modes are not group/world writable, and no package adds files under `/usr/share/omarchy/` or replaces the PR runtime/settings packages.
- Package checksums and embedded package identities are verified before installation. Tests reject corrupted archives and an archive reporting the base runtime's package identity. Existing root-owned code requires an explicit `--upgrade`; plugin upgrades preserve local edits by refusing to overwrite them.
- Both exported plugin roots pass PR9750's stock `omarchy-plugin-validate`. Shell syntax checks pass for every executable wrapper, lifecycle script and extracted Bash module.
- The real PR9750 command router dispatches `omarchy parent dns status` to an independently installed command on PATH, without source changes to the router or `omarchy-parent`.
- Both real Qt Quick controls views were rendered at normal and compact sizes and visually inspected. Interaction tests cover status, DNS mode and list actions, explicit logging consent, per-account reports, busy controls and private-data clearing.
- Both real plugin entry points load in Qt with inert Quickshell transport/theme stubs. Tests check the exact `pkexec` command, no action on panel open, private report expiry, clearing on close, rejection of late output after closing, and cancelled authentication feedback. The harness executes no privileged command.
- Version 0.1.1 adds a regression check for the actual controls window. With the panel Item outside any visual window, as in Omarchy's panel loader, v0.1.0 set `opened` but left the window invisible. Explicitly clearing the transient parent makes the window visible and exposed. The test verifies display, close and reopen, and captures both real panel windows for visual inspection. The earlier tests exercised the controls and lifecycle state without checking whether the panel window appeared.

Preview screenshots use synthetic browser history and status text. They are UI evidence, not laptop/network evidence.

## Linux checks still required

The Mac cannot execute Arch's real package transaction, Linux polkit authentication, systemd, NetworkManager or UFW. Package staging and transport stubs do not establish those behaviors. Perform the following on the new PR9750 laptop or a disposable PR9750 VM before treating this release as validated for daily use.

1. Run `./test` and `./build` as the normal desktop user. Install with `./install dns browsing`. Confirm that pacman proposes only the add-on packages and their ordinary dependencies; the existing `omarchy` and `omarchy-settings` versions must remain unchanged.
2. Install and enable the two plugin interfaces. Opening either panel must not enable anything or prompt for a password. A status/report request must open the system parent prompt. Cancelling must not act; the child's password must fail; the existing parent password must succeed. A second action must prompt again.
3. Before enabling DNS, verify UFW is active. Record a successful query for an allowed domain, enable denylist mode, deny a harmless test domain and verify its lookup is refused. Check that unrelated networking still works. Disable DNS and verify ordinary resolution returns. Repeat after a reboot while enabled. The resolver uses `omarchy-parent-dns.service`.
4. After informing Linnea, explicitly enable browsing for `linnea`, visit a harmless page in a supported browser, wait for a collection or request Pages, and confirm the record. The timer is `omarchy-parent-browsing.timer`. Verify an unprivileged shell cannot read `/var/lib/omarchy-parent-addons/linnea/browsing/`. Disable collection and verify new pages stop being collected; existing logs remain.
5. With both features enabled in a disposable test environment, remove each in turn and verify that the other's settings and service survive. Confirm DNS settings and unrelated Firefox/UFW policies are restored on removal. An injected restoration failure must abort the package removal. Verify the explicit upgrade preserves enablement and history.
6. Exercise the real Quickshell windows, polkit overlay, bar buttons, focus, resizing and report expiry on the laptop. Test browser reinstall followed by the documented `apply` commands, since PR9750's installer can rewrite Firefox policies after pacman's post-transaction hooks.
7. Visit a harmless domain before denying it so the browser and resolver have cached state. Deny the whole domain, verify system lookups fail, then quit and reopen Chromium. Confirm `chrome://policy` shows that domain in `URLBlocklist` with status OK and a fresh navigation to the root, a subdomain and a path is blocked. Repeat with a path-only rule to confirm other paths still work, and check Firefox's equivalent `WebsiteFilter` policy. Existing pages and open video streams are not automatically terminated.

No packages, accounts, firewall rules, networking configuration or running services were changed during the completed local checks.
