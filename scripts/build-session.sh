#!/usr/bin/env bash
# Runs inside the builder's private D-Bus/Xvfb session, as user builder.
set -Eeuo pipefail
output=$(xrandr --query | awk '$2 == "connected" {print $1; exit}')
if [[ -z $output ]]; then
    echo 'No connected RandR output in the virtual test display.' >&2
    exit 1
fi
# Xvfb exposes an output but does not choose a primary by default. drandr's
# GetPrimary integration test expects a normal desktop with a primary output.
xrandr --output "$output" --primary
xrandr --query | awk '
    $2 == "connected" && $3 == "primary" {found = 1}
    END {exit !found}
'
exec "$@"
