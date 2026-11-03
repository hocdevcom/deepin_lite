#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C.UTF-8
export DEBIAN_FRONTEND=noninteractive
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$BASE"
MODE=${1:-all}
PROJECT=${2:-}
case "$MODE" in
    all|image) ;;
    source)
        case "$PROJECT" in
            deepin-desktop-base|dde-api|dde-daemon|dde-session|dde-file-manager|dde-control-center|dde-session-shell|dde-session-ui) ;;
            *) echo 'Choose a locked source project.' >&2; exit 1 ;;
        esac ;;
    *) echo 'Usage: build.sh [all|source PROJECT|image]' >&2; exit 1 ;;
esac
if [[ $MODE == image && ! -d incoming/source-debs ]]; then
    echo 'Image assembly requires incoming/source-debs and incoming/sources artifacts.' >&2
    exit 1
fi
[[ $EUID == 0 ]] || { echo 'Run with sudo on Ubuntu 24.04 amd64.' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'Only amd64 supported.' >&2; exit 1; }
for tool in debootstrap gpg gpgv mksquashfs grub-mkrescue xorriso python3 curl; do
    command -v "$tool" >/dev/null || { echo "Missing host tool: $tool" >&2; exit 1; }
done
WORK="$BASE/.work"
ROOT="$WORK/rootfs"
BUILDER="$WORK/builder"
ISO="$WORK/iso"
DIST="$BASE/dist"
[[ ! -e $WORK && ! -e $DIST ]] || { echo 'Use a fresh checkout: .work/ and dist/ must not exist.' >&2; exit 1; }
mkdir -p "$WORK" "$DIST" "$ISO/live" "$ISO/boot/grub"
cleanup() {
    local dir
    for dir in "$BUILDER" "$ROOT"; do
        if mountpoint -q "$dir/run"; then umount -R "$dir/run" || true; fi
        if mountpoint -q "$dir/sys"; then umount -R "$dir/sys" || true; fi
        if mountpoint -q "$dir/proc"; then umount "$dir/proc" || true; fi
        if mountpoint -q "$dir/dev"; then umount -R "$dir/dev" || true; fi
    done
}
trap cleanup EXIT
mount_chroot() {
    local dir=$1
    mkdir -p "$dir"/{dev,proc,sys,run}
    mount --rbind /dev "$dir/dev"
    mount --make-rslave "$dir/dev"
    mount -t proc proc "$dir/proc"
    mount --rbind /sys "$dir/sys"
    mount --make-rslave "$dir/sys"
    mount -t tmpfs tmpfs "$dir/run"
    cp -L /etc/resolv.conf "$dir/etc/resolv.conf"
    printf '#!/bin/sh\nexit 101\n' > "$dir/usr/sbin/policy-rc.d"
    chmod +x "$dir/usr/sbin/policy-rc.d"
}
python3 scripts/policy.py validate
readarray -t settings < <(python3 - <<'PY'
import json
d=json.load(open('config/upstream.lock.json'))
print(d['mirror']); print(d['suite']); print(' '.join(d['components']))
PY
)
MIRROR=${settings[0]}
SUITE=${settings[1]}
COMPONENTS=${settings[2]}
export GNUPGHOME="$WORK/gnupg"
mkdir -m 700 "$GNUPGHOME"
python3 - <<'PY'
import hashlib,json,pathlib
for name,digest in json.load(open('config/upstream.lock.json'))['keyring_source']['files'].items():
    assert hashlib.sha256((pathlib.Path('keys')/name).read_bytes()).hexdigest()==digest, name
PY
gpg --batch --import keys/*.gpg
gpg --batch --export > "$WORK/deepin-archive.gpg"
curl --fail --location --retry 4 "$MIRROR/dists/$SUITE/InRelease" -o "$DIST/upstream.InRelease"
gpgv --keyring "$WORK/deepin-archive.gpg" "$DIST/upstream.InRelease"
# Deepin's suite is not included in Ubuntu's debootstrap scripts. Use the
# Debian common bootstrap logic explicitly, with Deepin's signed Release.
debootstrap --arch=amd64 --variant=minbase --components=main --include=ca-certificates \
    --keyring="$WORK/deepin-archive.gpg" "$SUITE" "$ROOT" "$MIRROR" \
    /usr/share/debootstrap/scripts/bookworm
install -Dm644 "$WORK/deepin-archive.gpg" "$ROOT/usr/share/keyrings/deepin-lite-archive.gpg"
printf 'deb [signed-by=/usr/share/keyrings/deepin-lite-archive.gpg] %s %s %s\n' \
    "$MIRROR" "$SUITE" "$COMPONENTS" > "$ROOT/etc/apt/sources.list"
mkdir -p "$ROOT/etc/apt/apt.conf.d"
printf 'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\nAcquire::Languages "none";\n' \
    > "$ROOT/etc/apt/apt.conf.d/99deepin-lite"
install -Dm644 config/dpkg-path-excludes "$ROOT/etc/dpkg/dpkg.cfg.d/01deepin-lite-prune"

if [[ $MODE != image ]]; then
# Source build dependencies live in a separate chroot and never enter the ISO.
cp -a --reflink=auto "$ROOT" "$BUILDER"
# The builder needs full documentation/locale fixtures for upstream tests.
rm -f "$BUILDER/etc/dpkg/dpkg.cfg.d/01deepin-lite-prune"
mount_chroot "$BUILDER"
python3 scripts/prepare-sources.py "$BUILDER/build"
chroot "$BUILDER" apt-get update
chroot "$BUILDER" apt-get install -y --no-install-recommends \
    build-essential devscripts equivs fakeroot ca-certificates dbus-x11 xvfb xauth locales \
    deepin-desktop-base grub-common librsvg2-bin fonts-unifont bc x11-xserver-utils
install -Dm755 scripts/build-session.sh "$BUILDER/usr/local/lib/deepin-lite/build-session.sh"
# Upstream desktop-base supplies /etc/os-version for tests. The runtime gets
# these files from our rebuilt desktop-base DEB through dpkg, not manual copies.
# Desktop tests need a private session bus and virtual X display. These test
# dependencies stay in the builder chroot and are not added to the image.
chroot "$BUILDER" dbus-uuidgen --ensure=/etc/machine-id
chroot "$BUILDER" useradd --create-home --shell /bin/bash builder
chroot "$BUILDER" chown builder:builder /build
projects=(deepin-desktop-base dde-api dde-daemon dde-session dde-file-manager dde-control-center dde-session-shell dde-session-ui)
if [[ $MODE == source ]]; then projects=("$PROJECT"); fi
for project in "${projects[@]}"; do
    # shellcheck disable=SC2016 # Expanded by the shell inside the builder.
    chroot "$BUILDER" /bin/bash -euc '
        mkdir -p "/build/deps-$1"
        cd "/build/deps-$1"
        mk-build-deps --install --remove --tool "apt-get -y --no-install-recommends" "/build/$1/debian/control"
        cd "/build/$1"
        chown -R builder:builder "/build/$1"
        install -d -m 700 -o builder -g builder /run/deepin-lite-build
        runuser --user builder -- env HOME=/home/builder XDG_RUNTIME_DIR=/run/deepin-lite-build \
            dbus-run-session -- xvfb-run --auto-servernum \
            --server-args="-screen 0 1280x720x24 -nolisten tcp -noreset" \
            /usr/local/lib/deepin-lite/build-session.sh \
            dpkg-buildpackage -rfakeroot --build=full --no-sign -j2
    ' -- "$project" 2>&1 | tee "$DIST/source-build-$project.log"
done
mkdir "$ROOT/local-debs"
python3 - "$BUILDER/build" "$ROOT/local-debs" <<'PY'
import pathlib,shutil,subprocess,sys
sys.path.insert(0,'scripts')
from policy import forbidden,lines
patterns=lines('config/deny-packages.txt')
for deb in pathlib.Path(sys.argv[1]).glob('*.deb'):
    package=subprocess.check_output(['dpkg-deb','-f',str(deb),'Package'],text=True).strip()
    if not forbidden(package,patterns):
        shutil.copy2(deb,sys.argv[2])
PY
mkdir -p "$DIST/source-debs"
cp "$ROOT"/local-debs/*.deb "$DIST/source-debs/"
mkdir -p "$DIST/sources"
find "$BUILDER/build" -maxdepth 1 -type f \( -name '*.dsc' -o -name '*.tar.*' -o -name '*.diff.gz' \) \
    -exec cp -t "$DIST/sources" -- {} +
else
    mkdir -p "$ROOT/local-debs" "$DIST/source-debs" "$DIST/sources"
    cp incoming/source-debs/*.deb "$ROOT/local-debs/"
    cp incoming/source-debs/*.deb "$DIST/source-debs/"
    cp incoming/sources/* "$DIST/sources/"
fi
if [[ $MODE == source ]]; then
    python3 scripts/verify-debs.py "$ROOT/local-debs" --source "$PROJECT" --report "$DIST/deb-audit.txt"
    echo "Source package and payload audit completed: $PROJECT"
    exit 0
fi
python3 scripts/verify-debs.py "$ROOT/local-debs" --report "$DIST/deb-audit.txt"
# Preserve rebuilt packages after upgrade so deleted integrations stay absent.
mkdir -p "$ROOT/etc/apt/preferences.d"
python3 - "$ROOT/local-debs" > "$ROOT/etc/apt/preferences.d/98deepin-lite-source" <<'PY'
import pathlib,subprocess,sys
names=[subprocess.check_output(['dpkg-deb','-f',str(p),'Package'],text=True).strip()
       for p in sorted(pathlib.Path(sys.argv[1]).glob('*.deb'))]
if not names: raise SystemExit('No rebuilt runtime packages found')
import json
revision=json.load(open('config/upstream.lock.json'))['local_revision']
print('Package: '+' '.join(names)+'\nPin: version *+'+revision+'\nPin-Priority: 1001\n')
PY
mount_chroot "$ROOT"
chroot "$ROOT" apt-get update
mapfile -t packages < <(sed -e 's/#.*//' -e '/^[[:space:]]*$/d' config/packages.txt)
# Install all together so the local API satisfies startdde without CJK fonts.
local_debs=()
for deb in "$ROOT"/local-debs/*.deb; do local_debs+=("/local-debs/${deb##*/}"); done
chroot "$ROOT" apt-get install -y --no-install-recommends "${local_debs[@]}" "${packages[@]}"
# Purge actual packages and conffiles; no negative pins or activation blocks.
# If a mandatory dependency removes the desktop, the required-package audit fails.
# shellcheck disable=SC2016
chroot "$ROOT" dpkg-query -W '-f=${binary:Package}\n' > "$WORK/before-purge.txt"
python3 scripts/policy.py purge-list --manifest "$WORK/before-purge.txt" > "$WORK/purge.txt"
mapfile -t purge < <(sed '/^$/d' "$WORK/purge.txt")
if ((${#purge[@]})); then
    chroot "$ROOT" apt-get purge -y --auto-remove "${purge[@]}"
fi
cp "$WORK/purge.txt" "$DIST/purged-packages.txt"
chroot "$ROOT" apt-get check
chroot "$ROOT" dpkg --audit
install -m755 scripts/configure-root.sh "$ROOT/tmp/configure-root.sh"
install -Dm755 scripts/live-smoke.sh "$ROOT/usr/local/lib/deepin-lite/live-smoke.sh"
install -Dm644 config/deepin-lite-smoke.service "$ROOT/etc/systemd/system/deepin-lite-smoke.service"
mkdir -p "$ROOT/etc/systemd/system/multi-user.target.wants"
ln -s ../deepin-lite-smoke.service "$ROOT/etc/systemd/system/multi-user.target.wants/"
chroot "$ROOT" /bin/bash /tmp/configure-root.sh
# shellcheck disable=SC2016 # dpkg-query owns these format placeholders.
chroot "$ROOT" dpkg-query -W '-f=${db:Status-Status}\t${binary:Package}\t${Version}\t${Installed-Size}\n' \
    | awk -F '\t' '$1 == "installed" {print $2 "\t" $3 "\t" $4}' > "$DIST/packages.tsv"
python3 scripts/policy.py audit --manifest "$DIST/packages.tsv" --require config/packages.txt | tee "$DIST/policy-audit.txt"
awk '{print $1 " " $2}' "$DIST/packages.tsv" > "$ISO/live/filesystem.packages"
cp config/upstream.lock.json "$DIST/"
cp config/deny-packages.txt "$DIST/"
du -x -h --max-depth=2 "$ROOT/usr" | sort -h > "$DIST/size-report.txt"
find "$ROOT/usr/lib" -path '*systemd*' -name '*.service' -printf '%P\n' | sort > "$DIST/services.txt"
find "$ROOT/usr/share/applications" -name '*.desktop' -printf '%f\n' | sort > "$DIST/applications.txt"
kernel=$(find "$ROOT/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -n1)
[[ -n $kernel ]] || { echo 'No kernel installed.' >&2; exit 1; }
version=${kernel##*/vmlinuz-}
[[ -s "$ROOT/boot/initrd.img-$version" ]]
cp "$kernel" "$ISO/live/vmlinuz"
cp "$ROOT/boot/initrd.img-$version" "$ISO/live/initrd.img"
cp config/grub.cfg "$ISO/boot/grub/grub.cfg"
rm -rf "$ROOT/local-debs"
python3 scripts/image_cleanup.py "$ROOT" --report "$DIST/removal-audit.txt"
rm -f "$ROOT/usr/sbin/policy-rc.d" "$ROOT/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$ROOT/etc/resolv.conf"
cleanup
for directory in dev proc sys run; do
    if mountpoint -q "$ROOT/$directory"; then
        echo "Refusing to pack a mounted runtime directory: $ROOT/$directory" >&2
        exit 1
    fi
done
printf '%s\n' "$(du -sx --block-size=1 "$ROOT" | cut -f1)" > "$ISO/live/filesystem.size"
mksquashfs "$ROOT" "$ISO/live/filesystem.squashfs" -noappend -comp xz \
    -b 1M -Xbcj x86 -processors 2 -mem 2G -no-progress
grub-mkrescue -o "$DIST/deepin-lite-amd64.iso" "$ISO" -- -volid DEEPIN_LITE
(
    cd "$DIST"
    sha256sum deepin-lite-amd64.iso source-debs/*.deb sources/* > SHA256SUMS
)
echo "ISO built: $DIST/deepin-lite-amd64.iso"
