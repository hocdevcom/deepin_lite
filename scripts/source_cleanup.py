"""Delete known online integrations from the exact source revisions in the lock.

These edits remove implementation and registration, not runtime deny rules.
Unexpected upstream layouts fail rather than silently shipping the original code.
"""
import json
from pathlib import Path
import re
import shutil


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


def replace(path, old, new, count=1):
    text = path.read_text(encoding="utf-8")
    if text.count(old) != count:
        raise RuntimeError(f"Source layout changed: {path}: {old[:70]!r}")
    write(path, text.replace(old, new))


def remove(root, relative):
    target = root / relative
    if not target.exists():
        raise RuntimeError(f"Expected source component missing: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def clean_daemon(root):
    # dh-golang may expose its private build GOPATH to `go env GOPATH`.
    # This Makefile builds directly against Debian's packaged Go sources;
    # its commands already prepend the local project gopath themselves.
    replace(root / "Makefile", "export GOPATH=$(shell go env GOPATH)",
            "export GOPATH = /usr/share/gocode")
    replace(root / "debian/rules", "\tdh $@\n", "\tdh $@ --buildsystem=makefile\n")
    replace(root / "accounts1/user_ifc.go", '''	// set password from UnionID
	if password == "" {
		err := u.setPwdWithUnionID(sender)
		if err != nil {
			return dbusutil.ToError(err)
		} else {
			return nil
		}
	}
''', '''	if password == "" {
		return dbusutil.ToError(fmt.Errorf("empty password is unsupported"))
	}
''')
    # The upstream cloud file also contains a LOCAL keyring helper. Preserve
    # that helper, while deleting the online dialog/process implementation.
    cloud_file = root / "accounts1/user_chpwd_union_id.go"
    cloud_text = cloud_file.read_text()
    local_helper = cloud_text.split("func removeLoginKeyring", 1)[1]
    write(root / "accounts1/local_keyring.go",
          cloud_text.split("package accounts", 1)[0] + 'package accounts\nimport "os"\n'
          + "func removeLoginKeyring" + local_helper)
    remove(root, "accounts1/user_chpwd_union_id.go")
    manager = root / "accounts1/manager.go"
    text, count = re.subn(r'(?ms)^\t_, _ = m.login1Manager.ConnectPrepareForSleep\(func\(before bool\) \{.*?^\t}\)\n', '', manager.read_text())
    if count != 1:
        raise RuntimeError("Expected online password-dialog suspend handler")
    write(manager, text)
    remove(root, "bin/dde-system-daemon/network.go")
    remove(root, "bin/dde-system-daemon/network_test.go")
    path = root / "bin/dde-system-daemon/exported_methods_auto.go"
    text, count = re.subn(r'(?m)^\t\t\{\n\t\t\tName:\s+"Network(?:Get|Set)Connections",\n.*?^\t\t},\n', '', path.read_text(), flags=re.DOTALL)
    if count != 2:
        raise RuntimeError("Expected two network cloud-sync export bindings")
    write(path, text)
    # ScreenSaver has a second D-Bus endpoint used solely by cloud sync.
    path = root / "screensaver1/module.go"
    text = path.read_text()
    start = text.index('\tm.syncConfig = dsync.NewConfig(')
    end = text.index('\n\treturn nil', start)
    text = text[:start] + text[end:]
    start = text.index('\terr = service.ReleaseName(dScreenSaverServiceName)')
    end = text.index('\n\treturn nil', start)
    # Close the local X connection before releasing the local object.
    text = text[:start] + text[end:]
    text = text.replace('\tm.sSaver.destroy()\n', '\tif m.sSaver.xConn != nil {\n\t\tm.sSaver.xConn.Close()\n\t}\n\tm.sSaver.destroy()\n')
    write(path, text)
    removed_modules = ("common/dsync", "session/eventlog")
    for relative in removed_modules:
        remove(root, relative)
    removed_sync_files = list(root.rglob("sync_config.go"))
    if len(removed_sync_files) != 7:
        raise RuntimeError(f"Expected seven cloud sync adapters, got {len(removed_sync_files)}")
    for path in removed_sync_files:
        path.unlink()
        test = path.with_name("sync_config_test.go")
        if test.exists():
            test.unlink()
    for path in root.rglob("*.go"):
        text = original = path.read_text(encoding="utf-8")
        # Remove imports, fields, setup, registration, export and teardown.
        text = re.sub(r'(?m)^\s*(?:_ )?"github.com/linuxdeepin/dde-daemon/(?:common/dsync|session/eventlog)"\n', '', text)
        text = re.sub(r'(?m)^\t+syncConfig\s+\*dsync.Config\n', '', text)
        text = re.sub(r'(?m)^\t+\w+\.syncConfig = dsync.NewConfig\([^\n]*(?:\n\t+[^\n]*)?\)\n', '', text)
        text = re.sub(r'(?m)^(\t+)err (?::=|=) [\w.]+\.syncConfig.Register\(\)\n\1if err != nil \{\n.*?^\1}\n', '', text, flags=re.DOTALL)
        text = re.sub(r'(?m)^(\t+)err = service.StopExport\([\w.]+\.syncConfig\)\n\1if err != nil \{\n.*?^\1}\n', '', text, flags=re.DOTALL)
        text = re.sub(r', [\w.]+\.syncConfig\b', '', text)
        text = re.sub(r'(?m)^\t+[\w.]+\.syncConfig.Destroy\(\)\n', '', text)
        if text != original:
            write(path, text)
    makefile = root / "Makefile"
    text = makefile.read_text()
    text = '\n'.join(line for line in text.split('\n') if not any('/' + m + ' ' in line for m in removed_modules))
    write(makefile, text)
    path = root / "misc/dsg-configs/org.deepin.dde.daemon.loader.json"
    data = json.loads(path.read_text())
    for key in list(data["contents"]):
        if any(s in key.lower() for s in ("eventlog",)):
            del data["contents"][key]
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    path = root / "misc/dde-daemon/keybinding/system_actions.json"
    data = json.loads(path.read_text())
    data["Actions"] = [a for a in data["Actions"] if "iflytek" not in a.get("Action", "").lower()]
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    clean_package_store(root)
    # Fail if any implementation references survive in compiled Go files.
    for path in root.rglob("*.go"):
        if re.search(r'\bdsync\b|\.syncConfig\b|setPwdWithUnionID|com\.deepin\.sync|org\.deepin\.dde\.eventlog', path.read_text(), flags=re.I):
            raise RuntimeError(f"Cloud integration still present: {path}")


def clean_package_store(root):
    # APT provides updates; omit Deepin's store backend and session integration.
    remove(root, "lastore1")
    remove(root, "misc/services/org.deepin.dde.LastoreSessionHelper1.service")
    replace(root / "debian/control", " lastore-daemon,\n", "")
    replace(root / "debian/control", """Breaks:
 lastore-daemon(<< 0.9.64),
Replaces:
 lastore-daemon(<< 0.9.64),
Conflicts:
 dde-workspace,
 lastore-daemon-migration,
Provides:
 lastore-daemon-migration,
""", """Conflicts:
 dde-workspace,
""")
    replace(root / "bin/dde-session-daemon/module.go",
            '\t_ "github.com/linuxdeepin/dde-daemon/lastore1"\n', '')
    replace(root / "bin/dde-session-daemon/daemon.go", '\t\t"lastore",\n', '')
    path = root / "Makefile"
    text, count = re.subn(r'(?m)^.*\$\{GOPKG_PREFIX\}/lastore1 \\\n', '', path.read_text())
    if count != 1:
        raise RuntimeError("Expected Lastore module build target")
    write(path, text)
    path = root / "misc/dsg-configs/org.deepin.dde.daemon.loader.json"
    data = json.loads(path.read_text())
    del data["contents"]["lastore"]
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    # Keep local locale generation and queries, remove automatic store installs.
    path = root / "langselector1/locale.go"
    text = path.read_text()
    start = text.index('\t// send notification\n', text.index('func (lang *LangSelector) setLocale('))
    end = text.index('\t// generate locale\n', start)
    text = text[:start] + '\tsendNotify(localeIconStart, "", notifyTxtStart)\n\n' + text[end:]
    text = text.replace('\terr = lang.generateLocale(locale)\n', '\terr := lang.generateLocale(locale)\n')
    start = text.index('\t// install language support packages\n')
    end = text.index('\tsendNotify(localeIconFinished', start)
    text = text[:start] + text[end:]
    for function in ('installLangSupportPackages', 'installPackages'):
        text, count = re.subn(r'(?ms)^func \(lang \*LangSelector\) ' + function + r'\(.*?^}\n', '', text)
        if count != 1:
            raise RuntimeError("Expected store installation function: " + function)
    text, count = re.subn(r'(?ms)^func isNetworkEnable\(.*?^}\n', '', text)
    if count != 1:
        raise RuntimeError("Expected language-download network check")
    text, count = re.subn(r'(?m)^\t+notifyTxtStartWithInstall[^\n]*\n', '', text)
    if count != 2:
        raise RuntimeError("Expected store language-install notification")
    text = re.sub(r'(?m)^\t(?:lastore|libnetwork) "github.com/linuxdeepin/go-dbus-factory/[^\n]+\n', '', text)
    write(path, text)


def clean_control_center(root):
    cmake = root / "CMakeLists.txt"
    replace(cmake, "set(BUILD_DCC_OLD ON)", "set(BUILD_DCC_OLD OFF)")
    remove(root, "dcc-old")
    # The old UI embeds UnionID/reset-password code. Qt6 plugins below embed
    # account/cloud sync, online ID, user-experience collection and updater UI.
    for plugin in ("accounts", "deepinid", "commoninfo", "systeminfo", "update"):
        replace(cmake, f"add_subdirectory(src/plugin-{plugin})\n", "")
        remove(root, f"src/plugin-{plugin}")
    # The pure Qt6 build does not produce the compatibility library.
    # Broad library install patterns still collect its frame and QML plugin.


def clean_file_manager(root):
    # Upstream forces -j8 even when dpkg-buildpackage requests -j2. Keep the
    # memory limit predictable on standard hosted runners for Qt/C++ builds.
    replace(root / "debian/rules", "\tdh_auto_build -- -j8", "\tdh_auto_build -- -j2")
    # The old dde-dock SDK is absent from the chosen archive. This image uses
    # dde-shell; retain its plugin and remove the legacy dock component/package.
    replace(root / "debian/control", " dde-dock-dev (>=4.8.4.1),\n", "")
    control = root / "debian/control"
    text, count = re.subn(r'(?ms)^Package: dde-disk-mount-plugin\n.*?(?=^Package:)', '', control.read_text())
    if count != 1:
        raise RuntimeError("Expected legacy dock plugin package")
    write(control, text)
    for relative in ("src/external/CMakeLists.txt", "tests/external/CMakeLists.txt"):
        replace(root / relative, "add_subdirectory(dde-dock-plugins)\n", "")
    remove(root, "debian/dde-disk-mount-plugin.install")
    remove(root, "src/external/dde-dock-plugins")
    remove(root, "tests/external/dde-dock-plugins")
    path = root / "src/dfm-base/utils/sysinfoutils.cpp"
    text = path.read_text()
    start = text.index("bool SysInfoUtils::isDeveloperModeEnabled()")
    end = text.index("\nbool SysInfoUtils::isProfessional()", start)
    # No external cloud-helper lookup remains. Developer mode is an optional
    # vendor mode, independent of ordinary local file management.
    text = text[:start] + "bool SysInfoUtils::isDeveloperModeEnabled()\n{\n    return false;\n}\n" + text[end:]
    write(path, text)


def clean_desktop_base(root):
    replace(root / "debian/control", " eject, fonts-noto, fonts-symbola", " eject")
    replace(root / "debian/control", "Provides: deepin-appstore-config\n", "")
    for relative in ("Makefile", "debian/deepin-desktop-base.install"):
        path = root / relative
        text = path.read_text()
        write(path, "\n".join(line for line in text.split("\n") if "appstore" not in line))
    remove(root, "files/appstore.json")
    remove(root, "files/appstore_loongson.json")


def clean_api(root):
    # Listing prepare next to the binaries does not order those prerequisites
    # under make -j. Each Go binary must wait for its GOPATH symlink to exist.
    replace(root / "Makefile", "out/bin/%:\n", "out/bin/%: | prepare\n")
    replace(root / "Makefile", "prepare:\n", ".PHONY: prepare\nprepare:\n")


def clean_session_shell(root):
    for stem, class_name in (("auth_password", "AuthPassword"), ("auth_single", "AuthSingle")):
        path = root / f"src/session-widgets/{stem}.cpp"
        text, count = re.subn(r'(?ms)^bool ' + class_name + r'::isUserAccountBinded\(\)\n\{.*?^}\n', '', path.read_text())
        if count != 1:
            raise RuntimeError("Expected online account lookup: " + stem)
        write(path, text)
        replace(root / f"src/session-widgets/{stem}.h", "    bool isUserAccountBinded();\n", "")


def clean_session_ui(root):
    replace(root / "CMakeLists.txt", 'add_subdirectory("reset-password-dialog")\n', "")
    replace(root / "CMakeLists.txt", "pkg_check_modules(DdeDockInterface REQUIRED dde-dock)\n", "")
    replace(root / "debian/control", " dde-dock-dev,\n", "")
    remove(root, "reset-password-dialog")
    write(root / "debian/postinst", "#!/bin/sh\nset -e\n#DEBHELPER#\nexit 0\n")


def clean_appearance(root):
    relative_paths = ("impl/appearancesyncconfig.h", "impl/appearancesyncconfig.cpp",
                      "modules/api/syncconfig.h", "modules/api/syncconfig.cpp")
    cmake = root / "src/service/CMakeLists.txt"
    for relative in relative_paths:
        replace(cmake, "    ./" + relative + "\n", "")
        remove(root, "src/service/" + relative)
    path = root / "src/service/impl/appearancemanager.cpp"
    text = path.read_text().replace('#include "appearancesyncconfig.h"\n', '')
    text, count = re.subn(r'(?m)^\s*new (?:ThemeFont|Background)SyncConfig\([^\n]+\n', '', text)
    if count != 2:
        raise RuntimeError("Expected two appearance sync registrations")
    write(path, text)
    path = root / "src/service/modules/common/commondefine.h"
    text, count = re.subn(r'(?m)^#define SYNCSERVICE[^\n]*\n', '', path.read_text())
    if count != 3:
        raise RuntimeError("Expected appearance cloud endpoint constants")
    write(path, text)


def clean_dbus_factory(root):
    files = [p for p in (root / "xml").glob("*.xml") if any(
        word in p.name.lower() for word in ("iflytek", "deepinid", "sync.daemon", "appstore", "lastore"))]
    if len(files) != 15:
        raise RuntimeError("Expected 15 AI/cloud/store D-Bus binding definitions")
    for path in files:
        path.unlink()


def clean_dtk_widget(root):
    path = root / "src/widgets/dlineedit.cpp"
    text = path.read_text()
    start = text.index('        auto msg = QDBusMessage::createMethodCall("com.iflytek.aiassistant"')
    end = text.index('        //FIXME:', start)
    text = text[:start] + text[end:]
    text = text.replace('le->echoMode() == QLineEdit::Password ||\n'
                        '                (!textToSpeechIsEnabled() && !textToTranslateIsEnabled() && !speechToTextIsEnabled())',
                        'le->echoMode() == QLineEdit::Password')
    write(path, text)
    path = root / "src/widgets/dtextedit.cpp"
    text, count = re.subn(r'(?ms)^void DTextEdit::contextMenuEvent\(QContextMenuEvent \*e\)\n\{.*?^}\n',
                         'void DTextEdit::contextMenuEvent(QContextMenuEvent *e)\n{\n    QTextEdit::contextMenuEvent(e);\n}\n',
                         path.read_text())
    if count != 1:
        raise RuntimeError("Expected text edit AI context menu implementation")
    write(path, text)
    path = root / "src/widgets/dsearchedit.cpp"
    text = path.read_text()
    text, count = re.subn(r'(?ms)^bool DSearchEdit::isVoiceInput\(\) const\n\{.*?^}\n',
                         'bool DSearchEdit::isVoiceInput() const\n{\n    return false;\n}\n', text)
    if count != 1:
        raise RuntimeError("Expected voice input ABI query")
    text, count = re.subn(r'(?ms)^void DSearchEditPrivate::_q_onVoiceActionTrigger\(bool checked\)\n\{.*?^}\n', '', text)
    if count != 1:
        raise RuntimeError("Expected private AI voice handler")
    text, count = re.subn(r'(?ms)^#ifdef ENABLE_AI\n.*?^#endif[^\n]*\n', '', text)
    if count != 4:
        raise RuntimeError("Expected four search-edit AI implementation blocks")
    text = text.replace('#undef ENABLE_AI\n', '').replace('#include "dsearchedit.moc"\n', '')
    write(path, text)
    path = root / "src/widgets/private/dsearchedit_p.h"
    text, count = re.subn(r'(?ms)^#ifdef ENABLE_AI\n.*?^#endif[^\n]*\n', '', path.read_text())
    if count != 1:
        raise RuntimeError("Expected private voice backend fields")
    text = text.replace('class VoiceDevice;\n', '').replace('    void _q_onVoiceActionTrigger(bool checked);\n', '')
    write(path, text)
    replace(root / "include/widgets/dsearchedit.h", '    D_PRIVATE_SLOT(void _q_onVoiceActionTrigger(bool))\n', '')
    for path in (root / "src").rglob("*.cpp"):
        if "com.iflytek" in path.read_text():
            raise RuntimeError("AI implementation remains: " + str(path))


def clean_api_proxy(root):
    replace(root / "debian/control", " lastore-daemon (>= 6.0.2),\n", "")
    path = root / "src/dbus-proxy/v1/CMakeLists.txt"
    text, count = re.subn(r'(?m)^qt5_add_dbus_proxy_interface_fix\([^\n]*Lastore[^\n]*\n', '', path.read_text())
    if count != 3:
        raise RuntimeError("Expected three Lastore proxy generators")
    write(path, text)
    path = root / "src/dbus-proxy/v1/system/systemdbusproxymanager.hpp"
    text = path.read_text().replace('#include "org_deepin_dde_Lastore1_Manager.hpp"\n', '')
    text, count = re.subn(r'(?ms)^        m_dbusProxyFactory.push_back\(\[this\]\{\n            return new SystemLastore1ManagerProxy.*?^        }\);\n', '', text)
    if count != 1:
        raise RuntimeError("Expected Lastore proxy registration")
    write(path, text)
    for directory in ("src", "file", "misc", "toolGenerate"):
        for path in (root / directory).rglob("*"):
            if path.is_file() and "lastore" in path.name.lower():
                path.unlink()


def clean_tray_loader(root):
    replace(root / "debian/control", " lastore-daemon (>=5.2.9),\n", "")
    path = root / "plugins/dde-dock/shutdown/shutdownplugin.cpp"
    text = path.read_text()
    text, count = re.subn(r'(?m)^    , m_lastoreDConfig\([^\n]*\n', '', text)
    if count != 1:
        raise RuntimeError("Expected tray store configuration initialization")
    start = text.index('    // ', text.index('    items.reserve(6);'))
    end = text.index('    QMap<QString, QVariant> shutdown;', start)
    if 'm_lastoreDConfig' not in text[start:end]:
        raise RuntimeError("Expected store upgrade-state handling")
    text = text[:start] + text[end:]
    for action in ("SHUTDOWN", "REBOOT"):
        text, count = re.subn(r'(?ms)^    if \(show\w+ && contextMenu.contains\(MENU_UPDATE_' + action + r'\)\) \{.*?^    }\n', '', text)
        if count != 1:
            raise RuntimeError("Expected update power-menu action: " + action)
    text = re.sub(r'(?m)^const QString MENU_UPDATE_[^\n]*\n', '', text)
    text = re.sub(r'(?m)^// lastore-daemon[^\n]*\n|^const int (?:CAN_UPGRADE|DISABLE_UPDATE|FORCE_UPDATE)[^\n]*\n', '', text)
    write(path, text)
    replace(root / "plugins/dde-dock/shutdown/shutdownplugin.h", '    DConfig *m_lastoreDConfig;\n', '')


def clean_source(name, root):
    handlers = {"deepin-desktop-base": clean_desktop_base, "dde-api": clean_api,
                "dde-daemon": clean_daemon, "dde-control-center": clean_control_center,
                "dde-file-manager": clean_file_manager,
                "dde-session-shell": clean_session_shell, "dde-session-ui": clean_session_ui,
                "dde-appearance": clean_appearance, "dde-qt-dbus-factory": clean_dbus_factory,
                "dtkwidget": clean_dtk_widget, "dtk6widget": clean_dtk_widget,
                "dde-api-proxy": clean_api_proxy, "dde-tray-loader": clean_tray_loader}
    if name in handlers:
        handlers[name](Path(root))
