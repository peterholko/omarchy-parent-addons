pragma Singleton
import QtQml
QtObject {
  function env(name) { return "/usr/share/omarchy" }
  function execDetached(arguments) { throw new Error("No processes may run in the portable UI harness") }
}
