#!/usr/bin/env bash
# Kernel/initrd live boot test. Bootloader metadata is checked separately.
set -Eeuo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$BASE"
xorriso -indev dist/deepin-lite-amd64.iso -report_el_torito plain 2>&1 | tee dist/boot-layout.txt
grep -q BIOS dist/boot-layout.txt
grep -q UEFI dist/boot-layout.txt
set +e
timeout 480 qemu-system-x86_64 -accel tcg -m 4096 -smp 2 -vga std \
    -kernel .work/iso/live/vmlinuz -initrd .work/iso/live/initrd.img \
    -append 'boot=live components username=live locales=en_US.UTF-8 console=ttyS0 deepin-lite.smoke=1' \
    -cdrom dist/deepin-lite-amd64.iso -boot d -display none -serial stdio -monitor none -no-reboot \
    > dist/qemu-live.log 2>&1 &
vm=$!
set -e
trap 'kill "$vm" 2>/dev/null || true' EXIT
for ((i=0; i<230; i++)); do
    if grep -q DEEPIN_LITE_DESKTOP_READY dist/qemu-live.log; then
        echo 'Live desktop smoke test passed.'
        exit 0
    fi
    if grep -q DEEPIN_LITE_DESKTOP_FAILED dist/qemu-live.log || ! kill -0 "$vm" 2>/dev/null; then break; fi
    sleep 2
done
tail -n 160 dist/qemu-live.log
echo 'Live desktop did not become ready.' >&2
exit 1
