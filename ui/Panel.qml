import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io
import qs.Commons

Item {
  id: root
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property bool opened: false
  property int generation: 0
  property int requestGeneration: 0
  property string response: ""
  readonly property string feature: "@FEATURE@"

  function open(payloadJson) {
    generation++
    controls.clearPrivate()
    response = ""
    opened = true
    window.requestActivate()
  }
  function close() {
    generation++
    opened = false
    controls.clearPrivate()
    response = ""
    expiry.stop()
  }

  function perform(action, values) {
    if (request.running) return
    requestGeneration = generation
    controls.feedback = "Waiting for parent authentication…"
    controls.failed = false
    response = ""
    request.command = ["/usr/bin/pkexec", "/usr/lib/omarchy-parent-addons/control", feature, action].concat(values)
    request.running = true
  }

  function receive(line) {
    if (opened && requestGeneration === generation && response.length < 200000)
      response += (line + "\n").slice(0, 200000 - response.length)
  }

  Process {
    id: request
    objectName: "privilegedRequest"
    stdout: SplitParser { onRead: function(line) { root.receive(line) } }
    stderr: SplitParser { onRead: function(line) { root.receive(line) } }
    onExited: function(code, status) {
      if (!root.opened || root.requestGeneration !== root.generation) return
      controls.failed = code !== 0
      controls.feedback = code === 0 ? "Done. Parent authentication is required for the next action."
        : (code === 126 ? "Authentication cancelled. Nothing was changed." : "The action did not complete. See details below.")
      controls.report = root.response
      root.response = ""
      expiry.restart()
    }
  }

  Timer {
    id: expiry
    objectName: "reportExpiry"
    interval: 120000
    onTriggered: { controls.clearPrivate(); root.response = "" }
  }

  Window {
    id: window
    visible: root.opened
    width: 760
    height: root.feature === "dns" ? 770 : 690
    minimumWidth: 640
    minimumHeight: 620
    title: root.feature === "dns" ? "Parent • DNS filtering" : "Parent • Browsing history"
    color: controls.surface
    onClosing: function(event) { event.accepted = false; root.close() }
    ControlsView {
      id: controls
      objectName: "controlsView"
      anchors.fill: parent
      feature: root.feature
      busy: request.running
      surface: Color.menu.background
      foreground: Color.menu.text
      onRequested: function(action, values) { root.perform(action, values) }
      onDismissed: root.close()
      Keys.onEscapePressed: root.close()
    }
  }
}
