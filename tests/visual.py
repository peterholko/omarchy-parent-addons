"""Exercise the real Qt Quick view; this does not emulate Linux authentication."""
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

SOURCE = Path(__file__).resolve().parents[1]
OUTPUT = SOURCE / 'test-output'
OUTPUT.mkdir(exist_ok=True)
app = QGuiApplication(sys.argv)
errors = []


def descendants(obj):
  for child in obj.children():
    yield child
    yield from descendants(child)


def button(root, text):
  for item in descendants(root):
    if item.property('text') == text and hasattr(item, 'clicked'):
      return item
  raise AssertionError('Button missing: ' + text)


def click(view, item):
  point = item.mapToScene(item.boundingRect().center())
  QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
  QTest.qWait(100)


for feature in ('dns', 'browsing'):
  view = QQuickView()
  view.engine().warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
  view.setResizeMode(QQuickView.SizeRootObjectToView)
  view.setSource(QUrl.fromLocalFile(str(SOURCE / 'ui/ControlsView.qml')))
  if view.status() == QQuickView.Error:
    raise AssertionError('\n'.join(e.toString() for e in view.errors()))
  view.resize(760, 770 if feature == 'dns' else 690)
  root = view.rootObject()
  root.setProperty('feature', feature)
  requests = []
  root.requested.connect(lambda action, values: requests.append((action, values.toVariant() if hasattr(values, 'toVariant') else values)))
  view.show()
  QTest.qWait(250)
  assert not requests, 'Opening the panel must not authenticate or enable anything'
  click(view, button(root, 'Check status'))
  assert requests[-1] == ('status', [])
  if feature == 'dns':
    mode = root.findChild(type(root), 'mode')
    mode = next(item for item in descendants(root) if item.objectName() == 'mode')
    mode.setProperty('currentIndex', 2)
    click(view, button(root, 'Apply mode'))
    assert requests[-1] == ('denylist', [])
    entry = next(item for item in descendants(root) if item.objectName() == 'domainEntry')
    entry.setProperty('text', 'youtube.com/shorts')
    click(view, button(root, 'Deny'))
    assert requests[-1] == ('deny', ['youtube.com/shorts'])
    root.setProperty('report', 'Web filter: denylist; upstream Cloudflare for Families.\nResolver: running.\nFirewall: other resolvers closed off.\n\nBrowser policies: Chromium, Firefox\nDenied: youtube.com/shorts\nAllowed: school.example')
  else:
    entry = next(item for item in descendants(root) if item.objectName() == 'accountEntry')
    entry.setProperty('text', 'linnea')
    before = len(requests)
    click(view, button(root, 'Enable collection'))
    assert len(requests) == before, 'Enabling history must wait for explicit confirmation'
    view.grabWindow().save(str(OUTPUT / 'browsing-confirmation.png'))
    click(view, button(root, 'OK'))
    assert requests[-1] == ('on', ['--user', 'linnea'])
    click(view, button(root, 'Pages'))
    assert requests[-1] == ('pages', ['7', '--user', 'linnea'])
    root.setProperty('report', 'Browsing history: on for linnea\n\n2026-09-11 10:10   https://school.example/lesson\n                  Fractions practice\n\n2026-09-11 10:22   https://www.youtube.com/watch?v=example\n                  How plants grow')
  root.setProperty('feedback', 'Done. Parent authentication is required for the next action.')
  QTest.qWait(100)
  view.grabWindow().save(str(OUTPUT / (feature + '.png')))
  root.setProperty('busy', True)
  before = len(requests)
  click(view, button(root, 'Check status'))
  assert len(requests) == before
  root.setProperty('busy', False)
  root.clearPrivate()
  assert root.property('report') == ''
  view.resize(640, 620)
  QTest.qWait(100)
  view.grabWindow().save(str(OUTPUT / (feature + '-compact.png')))
  view.close()
  print('PASS real Qt view:', feature)

if errors:
  raise AssertionError('\n'.join(errors))
print('Screenshots:', OUTPUT)
