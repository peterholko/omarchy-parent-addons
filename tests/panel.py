"""Load both real plugin entry points with inert Quickshell transport stubs."""
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

SOURCE = Path(__file__).resolve().parents[1]
OUTPUT = SOURCE / 'test-output'
OUTPUT.mkdir(exist_ok=True)
app = QGuiApplication(sys.argv)
errors = []

for feature in ('dns', 'browsing'):
  engine = QQmlApplicationEngine()
  engine.addImportPath(str(SOURCE / 'tests/qml-stubs'))
  engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
  engine.load(QUrl.fromLocalFile(str(SOURCE / 'dist/plugins' / ('io.github.peterholko.parent-' + feature) / 'Panel.qml')))
  assert engine.rootObjects(), errors
  root = engine.rootObjects()[0]
  request = root.findChild(QObject, 'privilegedRequest')
  controls = root.findChild(QObject, 'controlsView')
  root.open('{}')
  QTest.qWait(50)
  windows = root.findChildren(QQuickWindow)
  assert len(windows) == 1, 'Each plugin owns one controls window'
  window = windows[0]
  assert isinstance(root, QQuickItem) and root.window() is None, 'Match the host: the panel Item is outside any visual window'
  assert window.isVisible() and window.isExposed(), 'An opened panel must actually display its window'
  assert window.transientParent() is None, 'The controls window must not wait for an invisible parent'
  assert window.grabWindow().save(str(OUTPUT / ('panel-' + feature + '.png')))
  assert not request.property('running'), 'Opening the plugin may not prompt or start a service'
  root.perform('status', [])
  command = request.property('command').toVariant()
  assert command == ['/usr/bin/pkexec', '/usr/lib/omarchy-parent-addons/control', feature, 'status'], command
  root.receive('Private report fixture')
  request.setProperty('running', False)
  request.exited.emit(0, 0)
  assert controls.property('report') == 'Private report fixture\n'
  assert root.property('response') == ''
  expiry = root.findChild(QObject, 'reportExpiry')
  assert expiry.property('running'), 'A completed report must start its expiry timer'
  expiry.setProperty('interval', 1)
  for tick in range(25):
    QTest.qWait(20)
    if controls.property('report') == '':
      break
  assert controls.property('report') == '', 'Private output must expire automatically'
  root.close()
  assert not window.isVisible(), 'Closing must hide the controls window'
  assert controls.property('report') == ''
  root.open('{}')
  assert window.isVisible(), 'An existing panel must reopen'
  root.perform('status', [])
  root.close()
  root.receive('Must never appear after the window was closed')
  request.setProperty('running', False)
  request.exited.emit(0, 0)
  root.open('{}')
  assert controls.property('report') == ''
  root.perform('status', [])
  request.setProperty('running', False)
  request.exited.emit(126, 0)
  assert controls.property('failed')
  assert controls.property('feedback') == 'Authentication cancelled. Nothing was changed.'
  root.close()
  engine.deleteLater()
  QTest.qWait(20)
  print('PASS real plugin entry point with inert transport:', feature)

if errors:
  raise AssertionError('\n'.join(errors))
