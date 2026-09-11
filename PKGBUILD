pkgbase=omarchy-parent-addons
pkgname=(omarchy-parent-addons-core omarchy-parent-addons-dns omarchy-parent-addons-browsing)
pkgver=0.1.0
pkgrel=1
arch=(any)
url='https://github.com/peterholko/omarchy-parent-addons'
license=(MIT)
makedepends=(python)
source=()
sha256sums=()
PKGEXT='.pkg.tar.zst'
: "${PARENT_ADDONS_SOURCE:?Build using ./build from the standalone release}"

package_omarchy-parent-addons-core() {
  pkgdesc='Shared helpers for standalone PR9750 parent add-ons'
  depends=(python bash sudo polkit util-linux)
  conflicts=(omarchy-kids-core omarchy-parent-core)
  python3 "$PARENT_ADDONS_SOURCE/packaging/stage.py" "$PARENT_ADDONS_SOURCE" "$pkgdir" core
}

_feature() {
  python3 "$PARENT_ADDONS_SOURCE/packaging/stage.py" "$PARENT_ADDONS_SOURCE" "$pkgdir" "$1"
}

package_omarchy-parent-addons-dns() {
  pkgdesc='Independent parent DNS filtering for a PR9750 child laptop'
  depends=("omarchy-parent-addons-core=$pkgver-$pkgrel" dnsmasq ufw networkmanager systemd jq)
  conflicts=(omarchy-kids-dns omarchy-parent-dns)
  install=dns.install
  _feature dns
}

package_omarchy-parent-addons-browsing() {
  pkgdesc='Independent parent browsing reports for a PR9750 child laptop'
  depends=("omarchy-parent-addons-core=$pkgver-$pkgrel" systemd)
  conflicts=(omarchy-kids-browsing omarchy-parent-browsing)
  install=browsing.install
  _feature browsing
}
