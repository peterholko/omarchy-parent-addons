import QtQuick
import Quickshell

Item {
  id: root
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null
  property var pluginRegistry: null
  property var barWidgetRegistry: null
  implicitWidth: label.implicitWidth + 20
  implicitHeight: 28
  Text {
    id: label
    anchors.centerIn: parent
    text: "@LABEL@"
    color: "#c8d8f5"
    font.pixelSize: 13
    font.bold: true
  }
  MouseArea {
    anchors.fill: parent
    cursorShape: Qt.PointingHandCursor
    onClicked: Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-shell", "shell", "summon", "@ID@", "{}"])
  }
}
