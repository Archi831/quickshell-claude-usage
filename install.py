#!/usr/bin/env python3
"""
Install or uninstall the Claude usage pill for ilyamiro's Quickshell TopBar.
Usage:
  python3 install.py             # install
  python3 install.py --uninstall # remove
"""
import sys, os, shutil, subprocess

TOPBAR    = os.path.expanduser("~/.config/hypr/scripts/quickshell/TopBar.qml")
WATCHER   = os.path.expanduser("~/.config/hypr/scripts/quickshell/watchers/claude_fetch.sh")
HERE      = os.path.dirname(os.path.abspath(__file__))
SRC       = os.path.join(HERE, "claude_fetch.sh")

BEGIN = "// <<claude-usage-widget>>"
END   = "// <</claude-usage-widget>>"

# ── Snippets ─────────────────────────────────────────────────────────────────

PROPS = """\
// <<claude-usage-widget>>
            property real claudeFiveHour: 0
            property real claudeSevenDay: 0
            property string claudeResetIn: ""
            property string claudeSevenDayResetIn: ""
            property color claudeDynamicColor: {
                if (claudeFiveHour >= 90) return mocha.red;
                if (claudeFiveHour >= 70) return mocha.yellow;
                return mocha.teal;
            }
// <</claude-usage-widget>>"""

POLLER = """\
// <<claude-usage-widget>>
            Process {
                id: claudePoller
                command: ["bash", "-c", "~/.config/hypr/scripts/quickshell/watchers/claude_fetch.sh"]
                stdout: StdioCollector {
                    onStreamFinished: {
                        let txt = this.text.trim();
                        if (txt !== "") {
                            try {
                                let data = JSON.parse(txt);
                                barWindow.claudeFiveHour = data.fiveHour || 0;
                                barWindow.claudeSevenDay = data.sevenDay || 0;
                                function fmtReset(iso) {
                                    if (!iso) return "";
                                    let mins = Math.round((new Date(iso) - new Date()) / 60000);
                                    if (mins < 0) return "soon";
                                    if (mins < 60) return mins + "m";
                                    return Math.floor(mins/60) + "h" + String(mins%60).padStart(2,"0") + "m";
                                }
                                barWindow.claudeResetIn = fmtReset(data.fiveHourResetsAt || "");
                                barWindow.claudeSevenDayResetIn = fmtReset(data.sevenDayResetsAt || "");
                            } catch(e) {}
                        }
                    }
                }
            }
            Timer { interval: 180000; running: true; repeat: true; triggeredOnStart: true; onTriggered: { claudePoller.running = false; claudePoller.running = true; } }
// <</claude-usage-widget>>"""

PILL = """\
// <<claude-usage-widget>>
                            Rectangle {
                                id: claudePill
                                property bool isHovered: claudeMouse.containsMouse
                                color: isHovered ? Qt.rgba(mocha.surface1.r, mocha.surface1.g, mocha.surface1.b, 0.6) : Qt.rgba(mocha.surface0.r, mocha.surface0.g, mocha.surface0.b, 0.4)
                                radius: barWindow.s(10); height: sysLayout.pillHeight
                                clip: true

                                Rectangle {
                                    anchors.fill: parent
                                    radius: barWindow.s(10)
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: barWindow.claudeDynamicColor; Behavior on color { ColorAnimation { duration: 600 } } }
                                        GradientStop { position: 1.0; color: Qt.lighter(barWindow.claudeDynamicColor, 1.3); Behavior on color { ColorAnimation { duration: 600 } } }
                                    }
                                }

                                property real targetWidth: claudeRow.implicitWidth + barWindow.s(24)
                                width: targetWidth
                                Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutQuint } }

                                scale: isHovered ? 1.05 : 1.0
                                Behavior on scale { NumberAnimation { duration: 250; easing.type: Easing.OutExpo } }
                                Behavior on color { ColorAnimation { duration: 200 } }

                                property bool initAnimTrigger: false
                                Timer { running: rightContent.showLayout && !claudePill.initAnimTrigger; interval: 175; onTriggered: claudePill.initAnimTrigger = true }
                                opacity: initAnimTrigger ? 1 : 0
                                transform: Translate { y: claudePill.initAnimTrigger ? 0 : barWindow.s(15); Behavior on y { NumberAnimation { duration: 500; easing.type: Easing.OutBack } } }
                                Behavior on opacity { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

                                Row {
                                    id: claudeRow
                                    anchors.centerIn: parent
                                    spacing: barWindow.s(6)
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "󱙺"
                                        font.family: "Iosevka Nerd Font"; font.pixelSize: barWindow.s(15)
                                        color: mocha.base
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: Math.round(barWindow.claudeFiveHour) + "%"
                                        font.family: "JetBrains Mono"; font.pixelSize: barWindow.s(13); font.weight: Font.Black
                                        color: mocha.base
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        visible: claudePill.isHovered
                                        opacity: claudePill.isHovered ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: 200 } }
                                        text: barWindow.claudeResetIn +
                                              "  (" + Math.round(barWindow.claudeSevenDay) + "%)" +
                                              "  " + barWindow.claudeSevenDayResetIn
                                        font.family: "JetBrains Mono"; font.pixelSize: barWindow.s(11)
                                        color: Qt.rgba(mocha.base.r, mocha.base.g, mocha.base.b, 0.8)
                                    }
                                }

                                MouseArea { id: claudeMouse; hoverEnabled: true; anchors.fill: parent; onClicked: Quickshell.execDetached(["xdg-open", "https://claude.ai"]) }
                            }
// <</claude-usage-widget>>"""

# ── Anchors ───────────────────────────────────────────────────────────────────
# Each is a unique line in the original TopBar.qml.
# PROPS and POLLER are inserted AFTER their anchor line.
# PILL is inserted BEFORE its anchor line.

ANCHOR_PROPS  = "                return mocha.text;"          # inside batDynamicColor
ANCHOR_POLLER = "            Timer { interval: 150000;"       # weather poller timer
ANCHOR_PILL   = "                                property bool isHovered: batMouse.containsMouse"

# ── Helpers ───────────────────────────────────────────────────────────────────

def die(msg):
    print(f"error: {msg}", file=sys.stderr); sys.exit(1)

def check_deps():
    missing = [d for d in ("secret-tool", "openssl", "curl") if not shutil.which(d)]
    if missing:
        die(f"missing: {', '.join(missing)}\n  sudo pacman -S libsecret openssl curl")

def reload_qs():
    subprocess.run(
        ["qs", "-p", os.path.expanduser("~/.config/hypr/scripts/quickshell/Shell.qml"),
         "ipc", "call", "topbar", "forceReload"],
        capture_output=True
    )

def patch_after(lines, anchor, snippet):
    """Insert snippet lines after the first line containing anchor."""
    for i, line in enumerate(lines):
        if anchor in line:
            insert_at = i + 1
            if anchor == ANCHOR_PROPS:
                # advance past the closing `}` of batDynamicColor
                for j in range(i+1, min(i+4, len(lines))):
                    if lines[j].strip() == "}":
                        insert_at = j + 1
                        break
            # Only a leading blank — don't add trailing (original file has its own)
            lines[insert_at:insert_at] = [""] + snippet.split("\n")
            return True
    return False

def patch_before(lines, anchor, snippet):
    """Insert snippet lines before the line containing anchor, at the Rectangle { above it."""
    for i, line in enumerate(lines):
        if anchor in line:
            # Walk back to the nearest 'Rectangle {'
            for j in range(i - 1, max(i - 6, 0), -1):
                if "Rectangle {" in lines[j]:
                    lines[j:j] = snippet.split("\n") + [""]
                    return True
    return False

# ── Install ───────────────────────────────────────────────────────────────────

def install():
    check_deps()

    text = open(TOPBAR).read()
    if BEGIN in text:
        die("already installed — run with --uninstall first")

    lines = text.split("\n")

    if not patch_after(lines, ANCHOR_PROPS, PROPS):
        die(f"anchor not found (props):\n  {ANCHOR_PROPS!r}\n\nYour TopBar version may differ from what this was written for.")
    if not patch_after(lines, ANCHOR_POLLER, POLLER):
        die(f"anchor not found (poller):\n  {ANCHOR_POLLER!r}")
    if not patch_before(lines, ANCHOR_PILL, PILL):
        die(f"anchor not found (pill):\n  {ANCHOR_PILL!r}")

    shutil.copy2(TOPBAR, TOPBAR + ".bak")
    open(TOPBAR, "w").write("\n".join(lines))

    os.makedirs(os.path.dirname(WATCHER), exist_ok=True)
    shutil.copy2(SRC, WATCHER)
    os.chmod(WATCHER, 0o755)

    reload_qs()
    print("installed — pill appears in ~10 seconds")

# ── Uninstall ─────────────────────────────────────────────────────────────────

def uninstall():
    text = open(TOPBAR).read()
    if BEGIN not in text:
        print("not installed, nothing to do."); return

    lines = text.split("\n")
    out, skip = [], False
    for line in lines:
        if BEGIN in line:
            skip = True
            if out and out[-1].strip() == "":
                out.pop()
            continue
        if skip and END in line:
            skip = False
            continue
        if not skip:
            out.append(line)

    shutil.copy2(TOPBAR, TOPBAR + ".bak")
    open(TOPBAR, "w").write("\n".join(out))

    if os.path.exists(WATCHER):
        os.remove(WATCHER)

    reload_qs()
    print("uninstalled")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(TOPBAR):
        die(f"TopBar.qml not found:\n  {TOPBAR}")
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
