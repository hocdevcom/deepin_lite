#!/usr/bin/env bash
# Boot the actual ISO via BIOS and UEFI, including GRUB and the live initramfs.
set -Eeuo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$BASE"
xorriso -indev dist/deepin-lite-amd64.iso -report_el_torito plain 2>&1 | tee dist/boot-layout.txt
grep -q BIOS dist/boot-layout.txt
grep -q UEFI dist/boot-layout.txt
vm=''
stop_vm() {
    if [[ -n $vm ]]; then
        kill "$vm" 2>/dev/null || true
        wait "$vm" 2>/dev/null || true
        vm=''
    fi
}
trap stop_vm EXIT
for firmware in bios uefi; do
    args=()
    if [[ $firmware == uefi ]]; then
        code=/usr/share/OVMF/OVMF_CODE_4M.fd
        vars=/usr/share/OVMF/OVMF_VARS_4M.fd
        [[ -s $code && -s $vars ]] || { echo 'Missing OVMF firmware.' >&2; exit 1; }
        cp "$vars" .work/OVMF_VARS-test.fd
        args=(-drive "if=pflash,format=raw,readonly=on,file=$code"
              -drive 'if=pflash,format=raw,file=.work/OVMF_VARS-test.fd')
    fi
    log="dist/qemu-$firmware.log"
    timeout 600 qemu-system-x86_64 -accel tcg -m 4096 -smp 2 -vga std \
        "${args[@]}" -cdrom dist/deepin-lite-amd64.iso -boot d \
        -display none -serial stdio -monitor none -no-reboot > "$log" 2>&1 &
    vm=$!
    ready=false
    for ((i=0; i<290; i++)); do
        if grep -q DEEPIN_LITE_DESKTOP_READY "$log"; then ready=true; break; fi
        if grep -q DEEPIN_LITE_DESKTOP_FAILED "$log" || ! kill -0 "$vm" 2>/dev/null; then break; fi
        sleep 2
    done
    stop_vm
    if [[ $ready != true ]]; then
        tail -n 160 "$log"
        echo "Live desktop failed to boot through $firmware firmware and GRUB." >&2
        exit 1
    fi
    echo "PASS: real ISO $firmware boot reached the live DDE desktop." | tee -a dist/boot-tests.txt
done
