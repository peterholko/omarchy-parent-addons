import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
  id: root
  property string feature: "dns"
  property bool busy: false
  property string report: ""
  property string feedback: "Choose an action. The system will ask for the parent password."
  property bool failed: false
  property color surface: "#171b23"
  property color foreground: "#eef1f7"
  property color accent: "#95b9ff"
  signal requested(string action, var values)
  signal dismissed()
  padding: 0
  background: Rectangle { color: root.surface }

  function clearPrivate() {
    report = ""
    account.text = ""
    entry.text = ""
    feedback = "Choose an action. The system will ask for the parent password."
    failed = false
  }

  function perform(action, values) {
    if (busy) return
    var args = values || []
    if (feature === "browsing" && account.text.trim())
      args = args.concat(["--user", account.text.trim()])
    report = ""
    requested(action, args)
  }

  function changeMode() {
    if (mode.currentIndex === 3) {
      confirmation.text = "Only your allowlist and the built-in system domains will resolve. This can interrupt access to websites until their supporting domains are allowed."
      confirmation.action = "allowlist"
      confirmation.open()
    } else {
      perform(mode.currentIndex === 2 ? "denylist" : "off", [])
    }
  }

  palette.window: root.surface
  palette.windowText: root.foreground
  palette.text: root.foreground
  palette.buttonText: root.foreground
  palette.base: Qt.darker(root.surface, 1.12)
  palette.button: Qt.lighter(root.surface, 1.4)
  palette.highlight: root.accent
  palette.highlightedText: "#101724"

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 24
    spacing: 16

    RowLayout {
      Layout.fillWidth: true
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 5
        Label {
          Layout.fillWidth: true
          text: root.feature === "dns" ? "DNS filtering" : "Browsing history"
          font.pixelSize: 26
          font.bold: true
          color: root.foreground
        }
        Label {
          Layout.fillWidth: true
          text: "Parent controls"
          font.pixelSize: 14
          color: root.accent
        }
      }
      BusyIndicator { running: root.busy; visible: root.busy; implicitWidth: 32; implicitHeight: 32 }
      Button { text: "Close"; onClicked: root.dismissed() }
    }

    Label {
      Layout.fillWidth: true
      text: root.feature === "dns"
        ? "Filter domains across the laptop. Domain paths are handled by supported browser policies."
        : "Keep supported browsers' URLs and titles in a private parent log. Tell your child when collection is enabled."
      wrapMode: Text.WordWrap
      color: root.foreground
      font.pixelSize: 14
    }

    ColumnLayout {
      visible: root.feature === "dns"
      Layout.fillWidth: true
      enabled: !root.busy
      spacing: 10
      RowLayout {
        Layout.fillWidth: true
        Label { text: "Change mode"; color: root.foreground; Layout.preferredWidth: 110 }
        ComboBox { id: mode; objectName: "mode"; model: ["Choose mode…", "Off", "Denylist", "Allowlist"]; Layout.fillWidth: true }
        Button { text: "Apply mode"; enabled: mode.currentIndex > 0; onClicked: root.changeMode() }
      }
      RowLayout {
        Layout.fillWidth: true
        Label { text: "Resolver"; color: root.foreground; Layout.preferredWidth: 110 }
        ComboBox { id: upstream; model: ["Choose resolver…", "Cloudflare for Families", "Network DNS"]; Layout.fillWidth: true }
        Button { text: "Save resolver"; enabled: upstream.currentIndex > 0; onClicked: root.perform("upstream", [upstream.currentIndex === 1 ? "family" : "auto"]) }
      }
      TextField {
        id: entry
        objectName: "domainEntry"
        Layout.fillWidth: true
        placeholderText: "example.com or example.com/section"
        placeholderTextColor: Qt.darker(root.foreground, 1.65)
        selectByMouse: true
        maximumLength: 2048
      }
      Flow {
        Layout.fillWidth: true
        spacing: 8
        Button { text: "Allow"; enabled: entry.text.trim().length > 0; onClicked: root.perform("allow", [entry.text.trim()]) }
        Button { text: "Deny"; enabled: entry.text.trim().length > 0; onClicked: root.perform("deny", [entry.text.trim()]) }
        Button { text: "Remove entry"; enabled: entry.text.trim().length > 0; onClicked: root.perform("remove", [entry.text.trim()]) }
        Button { text: "View lists"; onClicked: root.perform("list", []) }
      }
    }

    ColumnLayout {
      visible: root.feature === "browsing"
      enabled: !root.busy
      Layout.fillWidth: true
      spacing: 10
      TextField {
        id: account
        objectName: "accountEntry"
        Layout.fillWidth: true
        placeholderText: "Child account (blank uses this session's account)"
        placeholderTextColor: Qt.darker(root.foreground, 1.65)
        selectByMouse: true
        maximumLength: 64
      }
      RowLayout {
        Button {
          text: "Enable collection"
          onClicked: {
            confirmation.text = "Collect existing and future browser history for this account, then keep collecting once a minute. Supported browsers will show managed policies and have private browsing restricted. Tell your child that history is being kept."
            confirmation.action = "on"
            confirmation.open()
          }
        }
        Button { text: "Disable collection"; onClicked: root.perform("off", []) }
      }
    }

    RowLayout {
      Layout.fillWidth: true
      enabled: !root.busy
      Button { text: "Check status"; onClicked: root.perform("status", []) }
      Item { Layout.fillWidth: true }
      Label { text: "Days"; color: root.foreground }
      SpinBox { id: days; from: 1; to: 365; value: 7; editable: true; Layout.preferredWidth: 105 }
      Button {
        text: root.feature === "dns" ? "Lookup history" : "Pages"
        onClicked: root.perform(root.feature === "dns" ? "history" : "pages", [String(days.value)])
      }
      Button { visible: root.feature === "browsing"; text: "Videos"; onClicked: root.perform("videos", [String(days.value)]) }
    }

    Label {
      Layout.fillWidth: true
      text: root.feedback
      textFormat: Text.PlainText
      wrapMode: Text.Wrap
      color: root.failed ? "#ffb7b0" : root.accent
      font.pixelSize: 13
    }

    ScrollView {
      Layout.fillWidth: true
      Layout.fillHeight: true
      Layout.minimumHeight: 120
      clip: true
      TextArea {
        objectName: "report"
        text: root.report
        textFormat: TextEdit.PlainText
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        color: root.foreground
        font.family: "monospace"
        font.pixelSize: 13
        placeholderText: "Results appear here after parent authentication."
        placeholderTextColor: Qt.darker(root.foreground, 1.65)
      }
    }
    Label {
      Layout.fillWidth: true
      text: "Reports clear when closed or after two minutes. Closing this panel does not stop enabled controls."
      font.pixelSize: 12
      color: Qt.darker(root.foreground, 1.35)
      wrapMode: Text.WordWrap
    }
  }

  Dialog {
    id: confirmation
    property string text: ""
    property string action: ""
    anchors.centerIn: parent
    width: Math.min(root.width - 48, 450)
    title: "Parent approval"
    palette: root.palette
    background: Rectangle { color: Qt.lighter(root.surface, 1.3); border.color: root.accent; radius: 8 }
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    header: Label { text: confirmation.title; color: root.foreground; font.bold: true; padding: 14 }
    contentItem: Label { text: confirmation.text; color: root.foreground; wrapMode: Text.WordWrap; textFormat: Text.PlainText }
    onAccepted: root.perform(action, [])
  }
}
