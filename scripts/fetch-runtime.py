#!/usr/bin/env python3
"""Fetch the explicitly locked local-authentication and installer runtimes, without a repo enable."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from image_cleanup import audit


def patch_installer(root: Path):
    ctrl_path = root / "DEBIAN" / "control"
    if ctrl_path.exists():
        text = ctrl_path.read_text(encoding="utf-8")
        text = re.sub(r",?\s*uos-license-content\s*\([^)]*\)", "", text)
        text = re.sub(r",?\s*usec-boot-crypt", "", text)
        text = re.sub(r"(?m)^Version:\s*(.*)$", r"Version: \1+lite3", text)
        ctrl_path.write_text(text, encoding="utf-8")

    postinst_path = root / "DEBIAN" / "postinst"
    if postinst_path.exists():
        text = postinst_path.read_text(encoding="utf-8")
        text = text.replace("generate_extral_locales\n", "")
        text = re.sub(r"(?ms)generate_extral_locales\(\) \{.*?^\}\n", "", text)
        postinst_path.write_text(text, encoding="utf-8")

    live_conf = root / "etc" / "live" / "config.conf.d" / "deepin-installer-live.conf"
    if live_conf.exists():
        live_conf.write_text(
            'LIVE_HOSTNAME="deepin-lite"\n'
            'LIVE_USERNAME="live"\n'
            'LIVE_USER_FULLNAME="Deepin Lite Live"\n'
            'LIVE_TIMEZONE="Asia/Ho_Chi_Minh"\n'
            'LIVE_LOCALES="en_US.UTF-8"\n',
            encoding="utf-8"
        )

    plugins_path = root / "usr" / "share" / "deepin-installer" / "configs" / "settings" / "deepin_installer_plugins.json"
    if plugins_path.exists():
        data = json.loads(plugins_path.read_text(encoding="utf-8"))
        for mode in data:
            mode["plugins"] = [p for p in mode.get("plugins", []) if p.get("name") != "InstallApplication"]
        plugins_path.write_text(json.dumps(data, indent=4), encoding="utf-8")

    installer_live = root / "usr" / "share" / "deepin-installer" / "configs" / "live-config" / "deepin-installer-live"
    if installer_live.exists():
        text = installer_live.read_text(encoding="utf-8")
        desktop_hook = (
            '    if [ -n "$DISPLAY" ]; then\n'
            '        exec "$DI_INSTALL_TOOLS_DIR_ENV/deepin-installer-core" "deepin-installer"\n'
            '    fi\n'
        )
        if desktop_hook not in text:
            text = text.replace("main () {\n", "main () {\n" + desktop_hook)
            installer_live.write_text(text, encoding="utf-8")

    preinit = root / "usr" / "share" / "deepin-installer" / "tools" / "deepin-installer-preinit"
    if preinit.exists():
        text = preinit.read_text(encoding="utf-8")
        text = text.replace('init_lightdm "deepin-installer-live-config"', '# init_lightdm kept for standard dde session')
        preinit.write_text(text, encoding="utf-8")

    for desktop_name in ("deepin-installer.desktop", "deepin-installer_deepin.desktop"):
        desktop_path = root / "usr" / "share" / "deepin-installer" / "configs" / "live-config" / desktop_name
        if desktop_path.exists():
            text = desktop_path.read_text(encoding="utf-8")
            if "Name[vi]=" not in text:
                text = text.replace("Name=Install deepin\n", "Name=Install Deepin Lite\nName[vi]=Cài đặt Deepin Lite\n")
                text = text.replace("Name=Install UOS\n", "Name=Install Deepin Lite\nName[vi]=Cài đặt Deepin Lite\n")
            if "Comment[vi]=" not in text:
                text = text.replace("Comment=Installer for Linux deepin\n", "Comment=Installer for Deepin Lite\nComment[vi]=Trình cài đặt hệ điều hành Deepin Lite\n")
                text = text.replace("Comment=Installer for UOS\n", "Comment=Installer for Deepin Lite\nComment[vi]=Trình cài đặt hệ điều hành Deepin Lite\n")
            desktop_path.write_text(text, encoding="utf-8")


base = Path(__file__).resolve().parent.parent
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
for item in json.loads((base / "config/required-runtime.json").read_text()):
    path = out / (item["package"] + ".deb")
    with urllib.request.urlopen(item["url"], timeout=180) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit("Runtime checksum mismatch: " + item["package"])
    path.write_bytes(data)

    with tempfile.TemporaryDirectory(prefix="deepin-runtime-audit-") as tmp:
        root = Path(tmp)
        subprocess.run(["dpkg-deb", "-x", str(path), tmp], check=True)
        subprocess.run(["dpkg-deb", "-e", str(path), str(root / "DEBIAN")], check=True)

        if item.get("patch") == "deepin-installer":
            patch_installer(root)
            subprocess.run(["dpkg-deb", "-b", str(root), str(path)], check=True)

        hits = audit(root)
        if hits:
            raise SystemExit("Required local runtime failed online-integration audit: " + "; ".join(hits))

    for field in ("package", "version"):
        actual = subprocess.check_output(["dpkg-deb", "-f", str(path), field.title()], text=True).strip()
        expected = item[field]
        if field == "version" and item.get("patch"):
            expected_versions = {expected, expected + "+lite3"}
            if actual not in expected_versions:
                raise SystemExit("Unexpected patched runtime version: " + actual)
        elif actual != expected:
            raise SystemExit("Unexpected runtime " + field + ": " + actual)

    print("Verified local runtime: " + item["package"] + " " + item["version"])
