#!/usr/bin/env bash
set -eu
stable=0
failed=false
crash_pattern='Tray Plugin Crashed|plugin is crashed|Failed to create wl_display|Could not (load|find) the Qt platform plugin|no Qt platform plugin could be initialized|segfault at|status=11/SEGV|status=6/ABRT|dumped core'
has_crashes() {
    journalctl --no-pager -b -o cat | grep -Ei "$crash_pattern"
}
desktop_ready() {
    local uid
    uid=$(id -u live) || return 1
    runuser -u live -- env "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus" \
        busctl --user --no-pager introspect com.deepin.dde.desktop \
        /com/deepin/dde/desktop com.deepin.dde.desktop >/dev/null 2>&1
}
check_applications() {
    local uid
    uid=$(id -u live)
    local -a session=(runuser -u live -- env "XDG_RUNTIME_DIR=/run/user/$uid"
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus")
    # The user manager holds DISPLAY/XAUTHORITY imported by dde-session.
    "${session[@]}" systemd-run --user --unit=deepin-lite-terminal /usr/bin/deepin-terminal
    "${session[@]}" systemd-run --user --unit=deepin-lite-file-manager /usr/bin/dde-file-manager /home/live
    "${session[@]}" systemd-run --user --wait --pipe --unit=deepin-lite-window-check \
        /bin/bash -c '
            for ((i=0; i<45; i++)); do
                if xdotool search --onlyvisible --class deepin-terminal >/dev/null 2>&1 &&
                    xdotool search --onlyvisible --class dde-file-manager >/dev/null 2>&1; then
                    sleep 20
                    xdotool search --onlyvisible --class deepin-terminal &&
                        xdotool search --onlyvisible --class dde-file-manager
                    exit $?
                fi
                sleep 2
            done
            echo "Terminal or File Manager failed to present a visible window." >&2
            exit 1
        '
}
for ((i=0; i<210; i++)); do
    if has_crashes; then
        failed=true
        break
    fi
    if id live >/dev/null 2>&1 && systemctl is-active --quiet NetworkManager lightdm &&
        { pgrep -u live -x dde-shell >/dev/null || pgrep -u live -x dshell >/dev/null; } &&
        desktop_ready; then
        ((stable+=1))
        if ((stable >= 60)); then
            if ! check_applications || has_crashes; then
                failed=true
                break
            fi
            journalctl --no-pager -b -n 200
            echo DEEPIN_LITE_DESKTOP_READY
            exit 0
        fi
    else
        stable=0
    fi
    sleep 2
done
if [[ $failed == true ]]; then echo 'Runtime crash detected during live desktop validation.'; fi
systemctl --no-pager status lightdm NetworkManager || true
journalctl --no-pager -b -p warning -n 100 || true
if id live >/dev/null 2>&1; then
    journalctl --no-pager -b _UID="$(id -u live)" -n 150 || true
fi
ps aux
echo DEEPIN_LITE_DESKTOP_FAILED
exit 1
