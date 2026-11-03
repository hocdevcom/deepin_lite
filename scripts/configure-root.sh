#!/usr/bin/env bash
# Runs INSIDE the newly built image, never on the host.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
echo 'deepin-lite' > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 deepin-lite\n' > /etc/hosts
printf 'en_US.UTF-8 UTF-8\nvi_VN.UTF-8 UTF-8\n' > /etc/locale.gen
locale-gen
update-locale LANG=en_US.UTF-8
ln -sf /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime
mkdir -p /etc/lightdm/lightdm.conf.d /etc/skel/Desktop
cat > /etc/lightdm/lightdm.conf.d/50-deepin-lite.conf <<'EOF'
[Seat:*]
greeter-session=lightdm-gtk-greeter
user-session=dde-x11
EOF
# live-config creates the live user and grants sudo on boot.
mkdir -p /etc/live/config.conf.d
cat > /etc/live/config.conf.d/10-deepin-lite.conf <<'EOF'
LIVE_USERNAME="live"
LIVE_USER_FULLNAME="Deepin Lite Live"
LIVE_HOSTNAME="deepin-lite"
LIVE_LOCALES="en_US.UTF-8"
LIVE_TIMEZONE="Asia/Ho_Chi_Minh"
EOF
passwd -l root
systemctl enable NetworkManager.service lightdm.service
systemctl set-default graphical.target

# Keep local Linux accounts. Deny cloud/AI D-Bus activation (including
# functionality embedded in DDE) without breaking the local account daemon.
mkdir -p /etc/dbus-1/session.d /etc/dbus-1/system.d
for bus in session system; do
    cat > "/etc/dbus-1/$bus.d/99-deepin-lite-privacy.conf" <<'EOF'
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy context="mandatory">
    <deny own_prefix="com.deepin.sync"/>
    <deny send_destination_prefix="com.deepin.sync"/>
    <deny own_prefix="org.deepin.dde.Sync"/>
    <deny send_destination_prefix="org.deepin.dde.Sync"/>
    <deny own_prefix="com.deepin.unionid"/>
    <deny send_destination_prefix="com.deepin.unionid"/>
    <deny own_prefix="org.deepin.dde.UnionID"/>
    <deny send_destination_prefix="org.deepin.dde.UnionID"/>
    <deny own_prefix="com.deepin.aiassistant"/>
    <deny send_destination_prefix="com.deepin.aiassistant"/>
    <deny own_prefix="org.deepin.ai"/>
    <deny send_destination_prefix="org.deepin.ai"/>
    <deny own_prefix="com.uniontech.ai"/>
    <deny send_destination_prefix="com.uniontech.ai"/>
  </policy>
</busconfig>
EOF
done

# Mask any matching unit that happens to be shipped inside a core package.
while IFS= read -r -d '' unit; do
    name=$(basename "$unit")
    case "${name,,}" in
        *aiassistant*|*uos-ai*|*deepin-sync*|*deepin-cloud*|*unionid*|*user-experience*|*telemetry*|*feedback*)
            if [[ $unit == */systemd/user/* ]]; then target=/etc/systemd/user; else target=/etc/systemd/system; fi
            mkdir -p "$target"
            ln -sf /dev/null "$target/$name"
            ;;
    esac
done < <(find /usr/lib/systemd /lib/systemd -type f \( -name '*.service' -o -name '*.timer' -o -name '*.socket' \) -print0 2>/dev/null)

mkdir -p /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/99deepin-lite <<'EOF'
APT::Install-Recommends "false";
APT::Install-Suggests "false";
Acquire::Languages "none";
EOF
apt-get clean
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*
# Retain licenses, copyright and configuration files.
find /usr/share/doc -type f ! -name copyright ! -iname '*license*' ! -iname '*copying*' -delete
rm -rf /usr/share/man /usr/share/info /usr/share/gtk-doc
if [[ -d /usr/share/locale ]]; then
    find /usr/share/locale -mindepth 1 -maxdepth 1 -type d ! -name en ! -name en_US ! -name vi ! -name vi_VN -exec rm -rf -- {} +
fi
find /var/log -type f -exec truncate -s 0 {} +
rm -f /etc/machine-id /var/lib/dbus/machine-id /etc/ssh/ssh_host_*
touch /etc/machine-id
update-initramfs -u -k all
