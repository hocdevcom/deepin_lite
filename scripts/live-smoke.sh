#!/usr/bin/env bash
set -eu
for ((i=0; i<210; i++)); do
    if id live >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager lightdm &&
        pgrep -u live -f '/(dde-shell|dshell)( |$)' >/dev/null &&
        pgrep -u live -f '/dde-desktop( |$)' >/dev/null; then
        echo DEEPIN_LITE_DESKTOP_READY
        exit 0
    fi
    sleep 2
done
systemctl --no-pager status lightdm NetworkManager || true
journalctl --no-pager -b -p warning -n 100 || true
ps aux
echo DEEPIN_LITE_DESKTOP_FAILED
exit 1
