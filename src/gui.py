
from . import glwindow
from . import code_editor
from . widgets import ArrangeV
from .thread import inthread, inmain_decorator

import sys, textwrap, inspect, time, re, pkgutil, ngsolve, ngui

from PySide2 import QtWidgets, QtCore, QtGui

from jupyter_client.multikernelmanager import MultiKernelManager
from qtconsole.inprocess import QtInProcessRichJupyterWidget
from traitlets import DottedObjectName

import os
os.environ['Qt_API'] = 'pyside2'
from IPython.lib import guisupport

class MultiQtKernelManager(MultiKernelManager):
    kernel_manager_class = DottedObjectName("qtconsole.inprocess.QtInProcessKernelManager",
                                            config = True,
                                            help = """kernel manager class""")

def createMenu(self, name):
    menu = self.addMenu(name)
    menu._dict = {}
    self._dict[name] = menu
    return menu
QtWidgets.QMenu.createMenu = createMenu

def getitem(self, index):
    if index not in self._dict:
        return self.createMenu(index)
    return self._dict[index]

QtWidgets.QMenu.__getitem__ = getitem

import inspect
class MenuBarWithDict(QtWidgets.QMenuBar):
    def __init__(self,*args, **kwargs):
        super().__init__(*args,**kwargs)
        self._dict = {}

    @inmain_decorator(wait_for_return=True)
    def createMenu(self, name, *args, **kwargs):
        menu = super().addMenu(name,*args,**kwargs)
        menu._dict = {}
        self._dict[name] = menu
        return menu

    def __getitem__(self, index):
        if index not in self._dict:
            return self.createMenu(index)
        return self._dict[index]

class Receiver(QtCore.QObject):
    received = QtCore.Signal(str)

    def __init__(self,pipe, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pipe = pipe
        self.ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        self.kill = False

    def SetKill(self):
        self.kill = True
        print("killme")

    def run(self):
        while not self.kill:
            self.received.emit(self.ansi_escape.sub("",os.read(self.pipe,1024).decode("ascii")))
        self.kill = False

class OutputBuffer(QtWidgets.QTextEdit):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setReadOnly(True)

    def append_text(self, text):
        self.moveCursor(QtGui.QTextCursor.End)
        self.insertPlainText(text)


class MainWindow(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.last = time.time()

    @inmain_decorator(wait_for_return=True)
    def redraw(self, blocking = True):
        if time.time() - self.last < 0.02:
            return
        for window in (self.window_tabber.widget(index) for index in range(self.window_tabber.count())):
            if window.isGLWindow():
                if blocking:
                    self.glWidget.redraw_mutex.lock()
                    self.glWidget.redraw_signal.emit()
                    self.glWidget.redraw_update_done.wait(self.glWidget.redraw_mutex)
                    self.glWidget.redraw_mutex.unlock()
                else:
                    self.glWidget.redraw_signal.emit()
        self.last = time.time()

    def keyPressEvent(self, event):
        if event.key() == 16777216:
            self.close()

class SettingsToolBox(QtWidgets.QToolBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.settings = []

    @inmain_decorator(wait_for_return=False)
    def addSettings(self, sett):
        self.settings.append(sett)
        widget = QtWidgets.QWidget()
        widget.setLayout(ArrangeV(*sett.getQtWidget().groups))
        widget.layout().setAlignment(QtCore.Qt.AlignTop)
        self.addItem(widget, sett.name)
        self.setCurrentIndex(len(self.settings)-1)

class NGSJupyterWidget(QtInProcessRichJupyterWidget):
    def __init__(self, multikernel_manager,*args, **kwargs):
        super().__init__(*args,**kwargs)
        self.banner = """NGSolve %s
Developed by Joachim Schoeberl at
2010-xxxx Vienna University of Technology
2006-2010 RWTH Aachen University
1996-2006 Johannes Kepler University Linz

""" % ngsolve.__version__
        if multikernel_manager is not None:
            self.kernel_id = multikernel_manager.start_kernel()
            self.kernel_manager = multikernel_manager.get_kernel(self.kernel_id)
        else:
            self.kernel_manager = QtInProcessKernelManager()
            self.kernel_manager.start_kernel()
        self.kernel_manager.kernel.gui = 'qt'
        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()
        class dummyioloop():
            def call_later(self,a,b):
                return
            def stop(self):
                return
        self.kernel_manager.kernel.io_loop = dummyioloop()

        def stop():
            self.kernel_client.stop_channels()
            self.kernel_manager.shutdown_kernel()
            # this function is qt5 compatible as well
            guisupport.get_app_qt4().exit()
        self.exit_requested.connect(stop)

    @inmain_decorator(wait_for_return=True)
    def pushVariables(self, varDict):
        self.kernel_manager.kernel.shell.push(varDict)

    @inmain_decorator(wait_for_return=True)
    def clearTerminal(self):
        self._control.clear()

def _noexec(gui, val):
    gui.executeFileOnStartup = not val
def _fastmode(gui,val):
    gui.fastmode = val
def _noOutputpipe(gui,val):
    gui.pipeOutput = not val

def _showHelp(gui, val):
    if val:
        print("Available flags:")
        for flag, tup in gui.flags.items():
            print(flag)
            print(textwrap.indent(tup[1],"  "))
        quit()

def _dontCatchExceptions(gui, val):
    gui._dontCatchExceptions = val

class GUI():
    # functions to modify the gui with flags. If the flag is not set, the function is called with False as argument
    flags = { "-noexec" : (_noexec, "Do not execute loaded Python file on startup"),
              "-fastmode" : (_fastmode, "Use fastmode for drawing large scenes faster"),
              "-noOutputpipe" : (_noOutputpipe, "Do not pipe the std output to the output window in the gui"),
              "-help" : (_showHelp, "Show this help function"),
              "-dontCatchExceptions" : (_dontCatchExceptions, "Do not catch exceptions")}
    def __init__(self):
        self.app = QtWidgets.QApplication([])
        ngui.SetLocale()
        self.multikernel_manager = MultiQtKernelManager()
        self.createMenu()
        self.createLayout()
        self.mainWidget.setWindowTitle("NGSolve")
        self.crawlPlugins()
        self.common_context = glwindow.GLWidget()

    def createMenu(self):
        self.menuBar = MenuBarWithDict()
        fileMenu = self.menuBar.createMenu("&File")
        loadMenu = fileMenu.createMenu("&Load")
        saveMenu = fileMenu.createMenu("&Save")
        saveSolution = saveMenu.addAction("&Solution")
        loadSolution = loadMenu.addAction("&Solution")
        loadSolution.triggered.connect(self.loadSolution)
        saveSolution.triggered.connect(self.saveSolution)
        def selectPythonFile():
            filename, filt = QtWidgets.QFileDialog.getOpenFileName(caption = "Load Python File",
                                                                   filter = "Python files (*.py)")
            if filename:
                self.loadPythonFile(filename)
        loadPython = loadMenu.addAction("&Python File", shortcut = "l+y")
        loadPython.triggered.connect(selectPythonFile)
        createMenu = self.menuBar.createMenu("&Create")
        newWindowAction = createMenu.addAction("New &Window")
        newWindowAction.triggered.connect(self.make_window)

    def createLayout(self):
        self.mainWidget = MainWindow()
        self.activeGLWindow = None
        menu_splitter = QtWidgets.QSplitter(parent=self.mainWidget)
        menu_splitter.setOrientation(QtCore.Qt.Vertical)
        menu_splitter.addWidget(self.menuBar)
        self.toolbox_splitter = toolbox_splitter = QtWidgets.QSplitter(parent=menu_splitter)
        menu_splitter.addWidget(toolbox_splitter)
        toolbox_splitter.setOrientation(QtCore.Qt.Horizontal)
        self.settings_toolbox = SettingsToolBox(parent=toolbox_splitter)
        toolbox_splitter.addWidget(self.settings_toolbox)
        window_splitter = QtWidgets.QSplitter(parent=toolbox_splitter)
        toolbox_splitter.addWidget(window_splitter)
        window_splitter.setOrientation(QtCore.Qt.Vertical)
        self.window_tabber = QtWidgets.QTabWidget(parent=window_splitter)
        self.window_tabber.setTabsClosable(True)
        def _remove_tab(index):
            if self.window_tabber.widget(index).isGLWindow():
                if self.activeGLWindow == self.window_tabber.widget(index):
                    self.activeGLWindow = None
            self.window_tabber.removeTab(index)
        self.window_tabber.tabCloseRequested.connect(_remove_tab)
        window_splitter.addWidget(self.window_tabber)
        self.console = NGSJupyterWidget(multikernel_manager = self.multikernel_manager)
        self.outputBuffer = OutputBuffer()
        self.output_tabber = QtWidgets.QTabWidget()
        self.output_tabber.addTab(self.console,"Console")
        self.output_tabber.addTab(self.outputBuffer, "Output")
        self.output_tabber.setCurrentIndex(1)
        window_splitter.addWidget(self.output_tabber)
        menu_splitter.setSizes([100, 10000])
        toolbox_splitter.setSizes([0, 85000])
        window_splitter.setSizes([70000, 30000])
        self.mainWidget.setLayout(ArrangeV(menu_splitter))
        # menu_splitter.show()

    def crawlPlugins(self):
        try:
            from . import plugins as plu
            plugins_exist = True
        except ImportError:
            plugins_exist = False
        if plugins_exist:
            prefix = plu.__name__ + "."
            plugins = []
            for importer, modname, ispkg in pkgutil.iter_modules(plu.__path__,prefix):
                plugins.append(__import__(modname, fromlist="dummy"))
            from .plugin import GuiPlugin
            for plugin in plugins:
                for val in plugin.__dict__.values():
                    if inspect.isclass(val):
                        if issubclass(val, GuiPlugin):
                            val.loadPlugin(self)

    def parseFlags(self, flags):
        flag = {val.split("=")[0] : (val.split("=")[1] if len(val.split("="))>1 else True) for val in flags}
        for key, tup in self.flags.items():
            if key in flag:
                tup[0](self,flag[key])
            else:
                tup[0](self, False)

    @inmain_decorator(wait_for_return=False)
    def update_setting_area(self):
        if len(self.settings_toolbox.settings) == 0:
            self.toolbox_splitter.setSizes([0,85000])
        else:
            self.toolbox_splitter.setSizes([15000, 85000])

    @inmain_decorator(wait_for_return=True)
    def make_window(self, name=None):
        self.activeGLWindow = window = glwindow.WindowTab(shared=self.common_context)
        if self.fastmode:
            window.glWidget.rendering_parameters.fastmode = True
        if self.common_context is None:
            self.common_context = window.glWidget
        name = name or "window" + str(self.window_tabber.count() + 1)
        self.window_tabber.addTab(window,name)
        self.window_tabber.setCurrentWidget(window)
        return window

    def saveSolution(self):
        import pickle
        filename, filt = QtWidgets.QFileDialog.getSaveFileName(caption="Save Solution",
                                                               filter = "Solution Files (*.sol)")
        if not filename[-4:] == ".sol":
            filename += ".sol"
        tabs = []
        for i in range(self.window_tabber.count()):
            tabs.append(self.window_tabber.widget(i))
        settings = self.settings_toolbox.settings
        with open(filename,"wb") as f:
            pickle.dump((tabs,settings), f)

    def loadSolution(self):
        import pickle
        filename, filt = QtWidgets.QFileDialog.getOpenFileName(caption="Load Solution",
                                                               filter = "Solution Files (*.sol)")
        if not filename[-4:] == ".sol":
            filename += ".sol"
        with open(filename, "rb") as f:
            tabs, settings = pickle.load(f)
        for tab in tabs:
            self.window_tabber.addTab(tab, "window" + str(self.window_tabber.count()))
            tab.show()
            self.window_tabber.setCurrentWidget(tab)
        for setting in settings:
            setting.gui = self
            self.settings_toolbox.addSettings(setting)

    def getActiveGLWindow(self):
        if self.activeGLWindow is None:
            self.make_window()
        return self.activeGLWindow

    @inmain_decorator(wait_for_return=True)
    def draw(self, *args, **kwargs):
        if 'tab' in kwargs:
            tab_found = False
            tab = kwargs['tab']
            del kwargs['tab']
            for i in range(self.window_tabber.count()):
                if self.window_tabber.tabText(i) == tab:
                    # tab already exists -> activate it
                    tab_found = True
                    wid = self.window_tabber.widget(i)
                    self.activeGLWindow = wid
                    self.window_tabber.setCurrentWidget(wid)
            if not tab_found:
                # create new tab with given name
                self.make_window(name=tab)

        self.getActiveGLWindow().draw(*args,**kwargs)

    @inmain_decorator(wait_for_return=False)
    def redraw(self):
        self.getActiveGLWindow().glWidget.updateScenes()

    @inmain_decorator(wait_for_return=True)
    def redraw_blocking(self):
        self.getActiveGLWindow().glWidget.updateScenes()

    @inmain_decorator(wait_for_return=True)
    def _loadFile(self, filename):
        txt = ""
        with open(filename,"r") as f:
            for line in f.readlines():
                txt += line
        return txt

    def loadPythonFile(self, filename):
        editTab = code_editor.CodeEditor(filename=filename,gui=self,parent=self.window_tabber)
        pos = self.window_tabber.addTab(editTab,filename)
        editTab.windowTitleChanged.connect(lambda txt: self.window_tabber.setTabText(pos, txt))
        if self.executeFileOnStartup:
            editTab.computation_started_at = 0
            editTab.run()

    def run(self,do_after_run=lambda : None):
        import os, threading
        self.mainWidget.show()
        globs = inspect.stack()[1][0].f_globals
        self.console.pushVariables(globs)
        if self.pipeOutput:
            stdout_fileno = sys.stdout.fileno()
            stdout_save = os.dup(stdout_fileno)
            stdout_pipe = os.pipe()
            os.dup2(stdout_pipe[1], stdout_fileno)
            os.close(stdout_pipe[1])
            receiver = Receiver(stdout_pipe[0])
            receiver.received.connect(self.outputBuffer.append_text)
            self.stdoutThread = QtCore.QThread()
            receiver.moveToThread(self.stdoutThread)
            self.stdoutThread.started.connect(receiver.run)
            self.stdoutThread.start()
        do_after_run()
        def onQuit():
            if self.pipeOutput:
                receiver.SetKill()
                self.stdoutThread.exit()
        self.app.aboutToQuit.connect(onQuit)
        sys.exit(self.app.exec_())

    def setFastMode(self, fastmode):
        self.fastmode = fastmode

class DummyObject:
    def __init__(self,*arg,**kwargs):
        pass
    def __getattr__(self,name):
        return DummyObject()
    def __call__(self,*args,**kwargs):
        pass

gui = DummyObject()
