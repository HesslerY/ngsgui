
import os
os.environ['QT_API'] = 'pyside2'
TEST_CREATION = os.getenv("TEST_CREATION")

from . import glwindow, code_editor
from . widgets import ArrangeV
from .thread import inmain_decorator
from .menu import MenuBarWithDict
from .globalSettings import SettingDialog

import ngsolve

from PySide2 import QtWidgets, QtCore, QtGui

class Receiver(QtCore.QObject):
    """Class responsible for piping the stdout to the internal output. Removes ansi escape characters.
"""
    received = QtCore.Signal(str)

    def __init__(self,pipe, *args,**kwargs):
        import re
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
    """Textview where the stdoutput is piped into. Is not writable, so stdin is not piped (yet).
"""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setReadOnly(True)

    def append_text(self, text):
        self.moveCursor(QtGui.QTextCursor.End)
        self.insertPlainText(text)

class SettingsToolBox(QtWidgets.QToolBox):
    """Global Toolbox on the left hand side, independent of windows. This ToolBox can be used by plugins to
to create Settings which are global to all windows.
"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = []

    @inmain_decorator(wait_for_return=False)
    def addSettings(self, sett):
        self.settings.append(sett)
        widget = QtWidgets.QWidget()
        widget.setLayout(ArrangeV(*sett.widgets.groups))
        widget.layout().setAlignment(QtCore.Qt.AlignTop)
        self.addItem(widget, sett.name)
        self.setCurrentIndex(len(self.settings)-1)
        if self.parent():
            self.parent().setSizes([20000,80000])


def _noexec(gui, val):
    gui.executeFileOnStartup = not val
def _fastmode(gui,val):
    gui.window_tabber._fastmode = val
def _noOutputpipe(gui,val):
    gui.pipeOutput = not val

def _showHelp(gui, val):
    import textwrap
    if val:
        print("Available flags:")
        for flag, tup in gui.flags.items():
            print(flag)
            print(textwrap.indent(tup[1],"  "))
        quit()

def _dontCatchExceptions(gui, val):
    gui._dontCatchExceptions = val

class GUI():
    """Graphical user interface for NGSolve. This object is created when ngsolve is started and the ngsgui.gui.gui object is set to it. You can import it with:
from ngsgui.gui import gui
It can be used to manipulate any behaviour of the interface.
"""
    # functions to modify the gui with flags. If the flag is not set, the function is called with False as argument
    flags = { "-noexec" : (_noexec, "Do not execute loaded Python file on startup"),
              "-fastmode" : (_fastmode, "Use fastmode for drawing large scenes faster"),
              "-noOutputpipe" : (_noOutputpipe, "Do not pipe the std output to the output window in the gui"),
              "-help" : (_showHelp, "Show this help function"),
              "-dontCatchExceptions" : (_dontCatchExceptions, "Do not catch exceptions up to user input, but show internal gui traceback")}
    # use a list of tuples instead of a dict to be able to sort it
    sceneCreators = {}
    file_loaders = {}
    def __init__(self):
        from .console import MultiQtKernelManager
        self.app = QtWidgets.QApplication([])
        ngsolve.solve._SetLocale()
        self.multikernel_manager = MultiQtKernelManager()
        self._commonContext = glwindow.GLWidget()
        self.app.setOrganizationName("NGSolve")
        self.app.setApplicationName("NGSolve")
        self._createMenu()
        self._createLayout()
        self.mainWidget.setWindowTitle("NGSolve")
        self._crawlPlugins()
        # set shader include files
        import ngsgui.shader
        from . import gl
        import glob
        for shaderpath in ngsgui.shader.locations:
            for incfile in glob.glob(os.path.join(shaderpath, '*.inc')):
                gl.Shader.includes[os.path.basename(incfile)] = open(incfile,'r').read()
        self._procs = []
        self.app.aboutToQuit.connect(self._killProcs)

    def _killProcs(self):
        for proc in self._procs:
            proc.kill()
            proc.waitForFinished()

    def _createMenu(self):
        self.menuBar = MenuBarWithDict()
        filemenu = self.menuBar.addMenu("&File")
        saveSolution = filemenu["&Save"].addAction("&Solution")
        loadSolution = filemenu["&Load"].addAction("&Solution")
        loadSolution.triggered.connect(self.loadSolution)
        saveSolution.triggered.connect(self.saveSolution)
        def selectPythonFile():
            filename, filt = QtWidgets.QFileDialog.getOpenFileName(caption = "Load Python File",
                                                                   filter = "Python files (*.py)")
            if filename:
                self.loadPythonFile(filename)
        loadPython = filemenu["&Load"].addAction("&Python File", shortcut = "l+y")
        loadPython.triggered.connect(selectPythonFile)
        newWindowAction = self.menuBar["&Create"].addAction("New &Window")
        newWindowAction.triggered.connect(lambda :self.window_tabber.make_window())
        settings = self.menuBar["&Settings"].addAction("&Settings")
        def showSettings():
            self.settings = SettingDialog()
            self.settings.show()
        settings.triggered.connect(showSettings)
        if TEST_CREATION:
            from .settings import BaseSettings
            save_test =  filemenu["&Save"].addAction("&Test")
            def saveTest():
                import pickle
                filename, filt = QtWidgets.QFileDialog.getSaveFileName(caption="Save Test",
                                                                       filter = "Test files (*.test)")
                if not filename.endswith(".test"):
                    filename += ".test"
                save_getstate = BaseSettings.__getstate__
                BaseSettings.__getstate__ = lambda self: ({key : par.getValue() for key, par in self._par_name_dict.items() if hasattr(par, "getValue")},)
                tabs = []
                for i in range(self.window_tabber.count()):
                    if self.window_tabber.widget(i).isGLWindow():
                        tabs.append(((self.window_tabber.widget(i).glWidget.scenes,
                                      self.window_tabber.widget(i)._rendering_parameters),
                                     self.window_tabber.tabBar().tabText(i)))
                with open(filename, "wb") as f:
                    pickle.dump(tabs,f)
                BaseSettings.__getstate__ = save_getstate
            save_test.triggered.connect(saveTest)
            load_test = filemenu["&Load"].addAction("&Test")
            def loadTest():
                filename, filt = getOpenFileName(caption="Load Test",
                                                 filter = "Test files (*.test)")
                if filename:
                    self._loadTest(filename)
            load_test.triggered.connect(loadTest)

    def _loadTest(self, filename):
        import pickle
        from .settings import BaseSettings
        from .glwindow import WindowTab
        save_setstate = BaseSettings.__setstate__
        def newSetstate(scene, state):
            BaseSettings.__init__(scene)
            for key, value in state[0].items():
                scene.__getattribute__("set" + key)(value)
        BaseSettings.__setstate__ = newSetstate
        with open(filename, "rb") as f:
            tabs = pickle.load(f)
        for (scenes, parameters), name in tabs:
            tab = WindowTab(rendering_parameters=parameters)
            tab._startup_scenes = scenes
            tab.create(self._commonContext)
            self.window_tabber.addTab(tab, name)
        BaseSettings.__setstate__ = save_setstate


    def getScenesFromCurrentWindow(self):
        """Get the list of the scenes of the currently active GLWindow"""
        return self.window_tabber.activeGLWindow.glWidget.scenes

    def _createLayout(self):
        from .console import NGSJupyterWidget
        self.mainWidget = QtWidgets.QWidget()
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
        self.window_tabber = glwindow.WindowTabber(commonContext = self._commonContext,
                                                   parent=window_splitter)
        window_splitter.addWidget(self.window_tabber)
        self.console = NGSJupyterWidget(gui=self,multikernel_manager = self.multikernel_manager)
        self.console.exit_requested.connect(self.app.quit)
        self.outputBuffer = OutputBuffer()
        self.output_tabber = glwindow.WindowTabber(commonContext=self._commonContext,
                                                   parent=window_splitter)
        self.output_tabber.addTab(self.console,"Console")
        self.output_tabber.addTab(self.outputBuffer, "Output")
        self.output_tabber.setCurrentIndex(1)
        settings = QtCore.QSettings()
        if settings.value("sysmon/active", "false") == "true":
            from .systemmonitor import SystemMonitor
            self._SysMonitor = SystemMonitor()
            sysmon_splitter = QtWidgets.QSplitter()
            sysmon_splitter.addWidget(self.output_tabber)
            sysmon_splitter.addWidget(self._SysMonitor)
            sysmon_splitter.setOrientation(QtCore.Qt.Vertical)
            sysmon_splitter.setSizes([10000,2000])
            window_splitter.addWidget(sysmon_splitter)
        else:
            window_splitter.addWidget(self.output_tabber)
        menu_splitter.setSizes([100, 10000])
        toolbox_splitter.setSizes([0, 85000])
        window_splitter.setSizes([70000, 30000])
        self.mainWidget.setLayout(ArrangeV(menu_splitter))

        # global shortkeys:
        def activateConsole():
            self.output_tabber.setCurrentWidget(self.console)
            self.console._control.setFocus()

        def switchTabWindow(direction):
            self.window_tabber.setCurrentIndex((self.window_tabber.currentIndex() + direction)%self.window_tabber.count())

        def addShortcut(name, key, func):
            action = QtWidgets.QAction(name)
            action.triggered.connect(func)
            action.setShortcut(QtGui.QKeySequence(key))
            self.mainWidget.addAction(action)
            # why do we need to keep this reference?
            if not hasattr(self.mainWidget,'_actions'):
                self.mainWidget._actions = []
            self.mainWidget._actions.append(action)

        addShortcut("Activate Console", "Ctrl+j", activateConsole)
        addShortcut("Quit", "Ctrl+q", lambda: self.app.quit())
        addShortcut("Close Tab", "Ctrl+w", lambda: self.window_tabber._remove_tab(self.window_tabber.currentIndex()))
        addShortcut("Next Tab", "Ctrl+LeftArrow", lambda: switchTabWindow(-1))
        addShortcut("Previous Tab", "Ctrl+RightArrow", lambda: switchTabWindow(1))

    def _crawlPlugins(self):
        import pkg_resources
        for entry_point in pkg_resources.iter_entry_points(group="ngsgui.plugin",name=None):
            plugin = entry_point.load()
            plugin(self)

    def _tryLoadFile(self, filename):
        if os.path.isfile(filename):
            name, ext = os.path.splitext(filename)
            if not ext in GUI.file_loaders:
                self.showMessageBox("File loading error", "Cannot load file type: " + ext)
                return
            GUI.file_loaders[ext](self, filename)

    def _parseFlags(self, flags):
        self._loadFiles = []
        for val in flags:
            if os.path.isfile(val):
                self._loadFiles.append(val)
                flags.remove(val)
        flag = {val.split("=")[0] : (val.split("=")[1] if len(val.split("="))>1 else True) for val in flags}
        for key, tup in self.flags.items():
            if key in flag:
                tup[0](self,flag[key])
            else:
                tup[0](self, False)
        for flag in flags:
            flg = flag.split("=")[0]
            if flg not in self.flags:
                print("Don't know flag: ", flg)
                _showHelp(self,True)

    def showMessageBox(self, title, text):
        self._msgbox = QtWidgets.QMessageBox(text=text)
        self._msgbox.SetWindowTitle(title)
        self._msgbox.show()

    def saveSolution(self):
        """Opens a file dialog to save the current state of the GUI, including all drawn objects."""
        import pickle
        filename, filt = QtWidgets.QFileDialog.getSaveFileName(caption="Save Solution",
                                                               filter = "Solution Files (*.ngs)")
        if not filename[-4:] == ".ngs":
            filename += ".ngs"
        tabs = []
        for i in range(self.window_tabber.count()):
            tabs.append((self.window_tabber.widget(i),self.window_tabber.tabBar().tabText(i)))
        settings = self.settings_toolbox.settings
        currentIndex = self.window_tabber.currentIndex()
        with open(filename,"wb") as f:
            pickle.dump((tabs,settings, currentIndex), f)

    def _loadSolutionFile(self, filename):
        import pickle
        if not filename[-4:] == ".ngs":
            filename += ".ngs"
        with open(filename, "rb") as f:
            tabs,settings,currentIndex = pickle.load(f)
        for tab,name in tabs:
            if isinstance(tab, glwindow.WindowTab):
                tab.create(self._commonContext)
            if isinstance(tab, code_editor.texteditor.CodeEditor):
                tab.gui = self
            self.window_tabber.addTab(tab, name)
        for setting in settings:
            setting.gui = self
            self.settings_toolbox.addSettings(setting)
        self.window_tabber.activeGLWindow = self.window_tabber.widget(currentIndex)

    def loadSolution(self):
        """Opens a file dialog to load a solution (*.ngs) file"""
        filename, filt = QtWidgets.QFileDialog.getOpenFileName(caption="Load Solution",
                                                               filter = "Solution Files (*.ngs)")
        self._loadSolutionFile(filename)

    def draw(self, *args, **kwargs):
        """Draw an object in the active GLWindow. The objects class must have a registered function/constructor (in GUI.sceneCreators) to create a scene from. Scenes, Meshes, (most) CoefficientFunctions, (most) GridFunctions and geometries can be drawn by default."""
        self.window_tabber.draw(*args,**kwargs)

    @inmain_decorator(wait_for_return=False)
    def redraw(self):
        """Redraw non-blocking. This can create problems in the visualization if objects are drawn to fast after each other"""
        self.window_tabber.activeGLWindow.glWidget.updateScenes()

    @inmain_decorator(wait_for_return=True)
    def redraw_blocking(self):
        """Draw blocking, this is the save option, but a bit slower than non-blocking redraw"""
        self.window_tabber.activeGLWindow.glWidget.updateScenes()

    @inmain_decorator(wait_for_return=True)
    def renderToImage(self, width, height, filename=None):
        """Render the current active GLWindow into a file"""
        import copy
        import OpenGL.GL as GL
        from PySide2 import QtOpenGL
        viewport = GL.glGetIntegerv( GL.GL_VIEWPORT )
        GL.glViewport(0, 0, width, height)
        format = QtOpenGL.QGLFramebufferObjectFormat()
        format.setAttachment(QtOpenGL.QGLFramebufferObject.Depth)
        format.setInternalTextureFormat(GL.GL_RGBA8);
        fbo = QtOpenGL.QGLFramebufferObject(width, height, format)
        fbo.bind()

        self.redraw_blocking()
        self.window_tabber.activeGLWindow.glWidget.paintGL()
        im = fbo.toImage()
        im2 = QtGui.QImage(im)
        im2.fill(QtCore.Qt.white)
        p = QtGui.QPainter(im2)
        p.drawImage(0,0,im)
        p.end()

        if filename!=None:
            im2.save(filename)
        fbo.release()
        GL.glViewport(*viewport)
        return im

    def plot(self, *args, **kwargs):
        """ Plot a matplotlib figure into a new Window"""
        self.window_tabber.plot(*args, **kwargs)

    @inmain_decorator(wait_for_return=True)
    def _loadFile(self, filename):
        txt = ""
        with open(filename,"r") as f:
            for line in f.readlines():
                txt += line
        return txt

    def loadPythonFile(self, filename):
        """Load a Python file and execute it if gui.executeFileOnStartup is True"""
        settings = QtCore.QSettings()
        import ngsgui.code_editor.texteditor as texteditor
        editorType = settings.value("editor/type", "default")
        if editorType == "emacs":
            import ngsgui.code_editor.emacs as emacs_editor
            editTab = emacs_editor.EmacsEditor(filename, self)
            self.window_tabber.addTab(editTab, filename)
        elif editorType == "default":
            editTab = texteditor.CodeEditor(filename=filename,gui=self,parent=self.window_tabber)
            self.window_tabber.addTab(editTab, filename)
        elif not editorType:
            editTab = NoEditor(filename=filename, gui=self)
        if self.executeFileOnStartup:
            editTab.computation_started_at = 0
            editTab.run()

    def _run(self,do_after_run=lambda : None):
        import sys, inspect
        self.mainWidget.show()
        globs = inspect.stack()[1][0].f_globals
        self.console.pushVariables(globs)
        if self.pipeOutput:
            stdout_fileno = sys.stdout.fileno()
            stderr_fileno = sys.stderr.fileno()
            stderr_save = os.dup(stderr_fileno)
            stdout_save = os.dup(stdout_fileno)
            stdout_pipe = os.pipe()
            os.dup2(stdout_pipe[1], stdout_fileno)
            os.dup2(stdout_pipe[1], stderr_fileno)
            os.close(stdout_pipe[1])
            receiver = Receiver(stdout_pipe[0])
            receiver.received.connect(self.outputBuffer.append_text)
            self.stdoutThread = QtCore.QThread()
            receiver.moveToThread(self.stdoutThread)
            self.stdoutThread.started.connect(receiver.run)
            self.stdoutThread.start()
        settings = QtCore.QSettings()
        if settings.value("sysmon/active", "false") == "true":
            self._cpuTimer = QtCore.QTimer()
            self._cpuTimer.setInterval(1000)
            self._cpuTimer.timeout.connect(self._SysMonitor.update)
            self._cpuTimer.start()
        do_after_run()
        for f in self._loadFiles:
            self._tryLoadFile(f)
        def onQuit():
            if self.pipeOutput:
                receiver.SetKill()
                self.stdoutThread.exit()
        self.app.aboutToQuit.connect(onQuit)
        sys.exit(self.app.exec_())

    def setFastMode(self, fastmode):
        self.fastmode = fastmode

class DummyObject:
    """If code is not executed using ngsolve, then this dummy object allows to use the same code with a netgen or python3 call as well"""
    def __init__(self,*arg,**kwargs):
        pass
    def __getattr__(self,name):
        return DummyObject()
    def __call__(self,*args,**kwargs):
        pass

    def plot(self, *args, **kwargs):
        import matplotlib.pyplot as plt
        plt.plot(*args, **kwargs)
        plt.show()

GUI.file_loaders[".py"] = GUI.loadPythonFile
GUI.file_loaders[".ngs"] = GUI._loadSolutionFile
GUI.file_loaders[".test"] = GUI._loadTest
def _loadSTL(gui, filename):
    import netgen.stl as stl
    print("create stl geometry")
    geo = stl.LoadSTLGeometry(filename)
    ngsolve.Draw(geo)

def _loadOCC(gui, filename):
    try:
        import netgen.NgOCC as occ
        geo = occ.LoadOCCGeometry(filename)
        ngsolve.Draw(geo)
    except ImportError:
        gui.showMessageBox("Netgen is not built with OCC support!")
def _loadGeo(gui, filename):
    import netgen.csg as csg
    geo = csg.CSGeometry(filename)
    ngsolve.Draw(geo)

def _loadin2d(gui, filename):
    import netgen.geom2d as geom2d
    geo = geom2d.SplineGeometry(filename)
    ngsolve.Draw(geo)

GUI.file_loaders[".stl"] = _loadSTL
GUI.file_loaders[".step"] = _loadOCC
GUI.file_loaders[".geo"] = _loadGeo
GUI.file_loaders[".in2d"] = _loadin2d
gui = DummyObject()
