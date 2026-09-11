# Shared configuration helpers for the standalone add-ons. The PR9750
# parent.conf and authentication files are deliberately not written here.
PARENT_CONF="$SYSROOT/etc/omarchy-parent-addons/settings.conf"

conf_get() {
  local key="$1" default="$2" value=""
  if [[ -f $PARENT_CONF ]]; then
    value=$(sed -n "s/^[[:space:]]*$key[[:space:]]*=[[:space:]]*//p" "$PARENT_CONF" | tail -1)
    value=${value%"${value##*[![:space:]]}"}
  fi
  printf '%s\n' "${value:-$default}"
}

conf_set() {
  python3 -I "$ADDONS_PATH/files.py" config "$PARENT_CONF" set "$@"
}

conf_document() {
  python3 -I "$ADDONS_PATH/files.py" config "$PARENT_CONF" document "$@"
}
