
from PySide2 import QtWidgets
from ngsgui.thread import inthread, inmain_decorator

class BaseEditor:
    def __init__(self, filename=None, gui=None):
        self.filename = filename
        self.gui = gui
        self._exec_locals = { "__name__" : "__main__" }
        self._active_thread = None

    @inmain_decorator(True)
    def show_exception(self, e, lineno):
        self.gui.window_tabber.setCurrentWidget(self)
        self.msgbox = QtWidgets.QMessageBox(text = type(e).__name__ + ": " + str(e))
        self.msgbox.setWindowTitle("Exception caught!")
        self.msgbox.show()
        if self.gui._dontCatchExceptions:
            raise e

    def run(self, code=None, reset_locals=True, *args, **kwargs):
        if code is None:
            with open(self.filename,"r") as f:
                code = f.read()
        if reset_locals:
            self._exec_locals = { "__name__" : "__main__" }
        def _run():
            try:
                exec(code,self._exec_locals)
            except Exception as e:
                import sys
                count_frames = 0
                tbc = sys.exc_info()[2]
                while tbc is not None:
                    tb = tbc
                    tbc = tb.tb_next
                self.show_exception(e,tb.tb_frame.f_lineno)
            self._active_thread = None
            if self.gui._have_console:
                self.gui.console.pushVariables(self._exec_locals)
        if self._active_thread:
            self.msgbox = QtWidgets.QMessageBox(text="Already running, please stop the other computation before starting a new one!")
            self.msgbox.setWindowTitle("Multiple computations error")
            self.msgbox.show()
            return
        self._active_thread = inthread(_run)

    def isGLWindow(self):
        return False
