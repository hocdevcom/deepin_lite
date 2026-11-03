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

# Online integrations are removed from rebuilt sources and the image payload.
# No D-Bus deny configuration or systemd masking is used as a substitute.
mkdir -p /etc/apt/apt.conf.d
cat > /etc/apt/apt.conf.d/99deepin-lite <<'EOF'
APT::Install-Recommends "false";
APT::Install-Suggests "false";
Acquire::Languages "none";
EOF
apt-get clean
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/* /tmp/* /var/tmp/*
# Documentation/locale pruning is handled by dpkg path filters at install time.
find /var/log -type f -exec truncate -s 0 {} +
rm -f /etc/machine-id /var/lib/dbus/machine-id /etc/ssh/ssh_host_*
touch /etc/machine-id
update-initramfs -u -k all
