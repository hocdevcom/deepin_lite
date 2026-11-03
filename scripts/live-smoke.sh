#!/usr/bin/env bash
set -eu
stable=0
desktop_ready() {
    local uid
    uid=$(id -u live) || return 1
    runuser -u live -- env "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" \
        busctl --user --no-pager introspect com.deepin.dde.desktop \
        /com/deepin/dde/desktop com.deepin.dde.desktop >/dev/null 2>&1
}
for ((i=0; i<210; i++)); do
    if id live >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager lightdm &&
        { pgrep -u live -x dde-shell >/dev/null || pgrep -u live -x dshell >/dev/null; } &&
        desktop_ready; then
        ((stable+=1))
        if ((stable >= 15)); then
            echo DEEPIN_LITE_DESKTOP_READY
            exit 0
        fi
    else
        stable=0
    fi
    sleep 2
done
systemctl --no-pager status lightdm NetworkManager || true
journalctl --no-pager -b -p warning -n 100 || true
if id live >/dev/null 2>&1; then
    journalctl --no-pager -b _UID="$(id -u live)" -n 150 || true
fi
ps aux
echo DEEPIN_LITE_DESKTOP_FAILED
exit 1
