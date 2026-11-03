#!/usr/bin/env bash
# Run in the live user's real X11 session, with its imported display environment.
set -Eeuo pipefail
diagnostics() {
    echo 'Application interaction test failed.' >&2
    wmctrl -lpGx || true
    free -m || true
    ps -eo pid,comm,pcpu,pmem,rss,state --sort=-rss | head -n 25 || true
    journalctl --user --no-pager -b -n 150 || true
}
trap diagnostics ERR

windows() {
    xdotool search --onlyvisible --class "^$1$" 2>/dev/null || true
}
wait_visible() {
    local class=$1 deadline=$((SECONDS + 90))
    while ((SECONDS < deadline)); do
        if [[ -n $(windows "$class") ]]; then return 0; fi
        sleep 1
    done
    echo "No visible $class window within 90 seconds." >&2
    return 1
}
wait_closed() {
    local class=$1 deadline=$((SECONDS + 20))
    while ((SECONDS < deadline)); do
        if [[ -z $(windows "$class") ]]; then return 0; fi
        sleep 1
    done
    echo "$class did not respond to a graceful close within 20 seconds." >&2
    return 1
}
launch() {
    local class=$1 cycle=$2
    shift 2
    systemd-run --user --collect --unit="deepin-lite-$class-$cycle" "$@"
}

classes=(deepin-terminal dde-file-manager dde-control-center)
free -m
for cycle in 1 2; do
    launch deepin-terminal "$cycle" /usr/bin/deepin-terminal
    launch dde-file-manager "$cycle" /usr/bin/dde-file-manager /home/live
    launch dde-control-center "$cycle" /usr/bin/dde-control-center --show
    for class in "${classes[@]}"; do wait_visible "$class"; done
    sleep 5

    # Prove that the window receives real input and its shell executes it.
    terminal=$(windows deepin-terminal | head -n 1)
    marker="$XDG_RUNTIME_DIR/deepin-lite-input-$cycle"
    timeout 15 xdotool windowactivate --sync "$terminal"
    xdotool type --clearmodifiers --delay 5 "printf ready > '$marker'"
    xdotool key --clearmodifiers Return
    deadline=$((SECONDS + 20))
    while [[ ! -s $marker ]] && ((SECONDS < deadline)); do sleep 1; done
    grep -qx ready "$marker"
    echo "PASS: terminal input round $cycle"

    # EWMH requests let each application run its normal close handler.
    # Do not kill processes or destroy X windows to manufacture a passing test.
    for class in "${classes[@]}"; do
        start=$SECONDS
        for window in $(windows "$class"); do
            timeout 10 wmctrl -ic "$(printf '0x%x' "$window")"
        done
        wait_closed "$class"
        echo "PASS: $class graceful close round $cycle in $((SECONDS - start)) seconds"
    done
    echo "PASS: application open/close round $cycle"
done
free -m
echo 'DEEPIN_LITE_APPLICATION_LIFECYCLE_READY'
