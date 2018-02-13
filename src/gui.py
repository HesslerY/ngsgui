#!/usr/bin/env python
import sys
import math
import OpenGL.GL as GL
from math import exp
import time
import ngsolve
from ngsolve.bla import Vector
from ngsolve.comp import BND, VOL
from qtconsole.inprocess import QtInProcessKernelManager, QtInProcessRichJupyterWidget
import inspect

import numpy
from . import glmath
from . import gl as mygl
import ctypes
from . import scenes

from PySide2 import QtCore, QtGui, QtWidgets, QtOpenGL
from PySide2.QtCore import Qt

def ArrangeV(*args):
    layout = QtWidgets.QVBoxLayout()
    for w in args:
        if isinstance(w, QtWidgets.QWidget):
            layout.addWidget(w)
        else:
            layout.addLayout(w)
    return layout

def ArrangeH(*args):
    layout = QtWidgets.QHBoxLayout()
    for w in args:
        if isinstance(w, QtWidgets.QWidget):
            layout.addWidget(w)
        else:
            layout.addLayout(w)
    return layout

class OptionWidgets():
    def __init__(self):
        self.visibilityOptions = {}
        self.groups = []

    def addGroup(self, name, *widgets, connectedVisibility=None):
        group = QtWidgets.QGroupBox(name)
        group.setLayout(ArrangeV(*widgets))
        if connectedVisibility is not None:
            self.visibilityOptions[connectedVisibility] = group
        self.groups.append(group)
        self.update()

    def update(self):
        for evaluator, group in self.visibilityOptions.items():
            group.setVisible(evaluator())

class ToolBox(QtWidgets.QToolBox):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.scenes = []

    def addScene(self, scene, position=-1):
        self.scenes.insert(position,scene)
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        for item in scene.getQtWidget(self.window.glWidget.updateGL,
                                      self.window.glWidget.rendering_parameters).groups:
            layout.addWidget(item)
        widget.setLayout(layout)
        self.insertItem(position,widget,scene.name)
        self.setCurrentIndex(position)

class GUIHelper():
    def __init__(self, updateSlot):
        self.updateSlot = updateSlot

    def CheckBox(self, name, slot, checked=False):
        cb = QtWidgets.QCheckBox(name)
        if checked:
            cb.setCheckState(QtCore.Qt.Checked)
        else:
            cb.setCheckState(QtCore.Qt.Unchecked)
        cb.stateChanged.connect(slot)
        cb.stateChanged.connect(self.updateSlot)
        return cb

    def Button(self, name, slot):
        button = QtWidgets.QPushButton(name)
        button.clicked.connect(slot)
        button.clicked.connect(self.updateSlot)
        return button

    def DoubleSpinBox(self, step=1, slot=None, name=None):
        box = QtWidgets.QDoubleSpinBox()
        box.valueChanged[float].connect(slot)
        box.valueChanged[float].connect(self.updateSlot)
        box.setSingleStep(step)
        if(name):
            label = QtWidgets.QLabel(name)
            return ArrangeH(label, box)
        else:
            return box


class ObjectHolder():
    def __init__(self, obj, call_func):
        self.obj = obj
        self.call_func = call_func

    def __call__(self, state):
        self.call_func(self,state)


class QColorButton(QtWidgets.QPushButton):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    colorChanged = QtCore.Signal()

    def __init__(self, initial_color,*args, **kwargs):
        super(QColorButton, self).__init__(*args, **kwargs)

        self.setColor(QtGui.QColor(*initial_color))
        self.setMaximumWidth(32)
        self.pressed.connect(self.onColorPicker)

    def setColor(self, color):
        if color:
            self._color = color
            self.colorChanged.emit()

            self.setStyleSheet("background-color: %s;" % self._color.name())

    def color(self):
        return self._color

    def onColorPicker(self):
        '''
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.

        '''
        dlg = QtWidgets.QColorDialog()
        dlg.setStyleSheet("")
        if self._color:
            dlg.setCurrentColor(self._color)

        if dlg.exec_():
            self.setColor(dlg.currentColor())

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.setColor(None)

        return super(QColorButton, self).mousePressEvent(e)

class RangeGroup(QtWidgets.QWidget):
    valueChanged = QtCore.Signal(float) # TODO: this shouldn't be static
    def __init__(self, name, min=-1, max=1, value=0, direction=Qt.Horizontal):
        super(RangeGroup, self).__init__()
#         self.valueChanged.connect(onValueChanged)

        self.scalingFactor = 1000 # scaling between integer widgets (scrollslider) and float values to get more resolution
        self.scroll = QtWidgets.QScrollBar(direction)
        self.scroll.setFocusPolicy(Qt.StrongFocus)
        self.scroll.valueChanged[int].connect(self.setIntValue)
        self.scroll.setRange(self.scalingFactor*min,self.scalingFactor*max)

        self.valueBox = QtWidgets.QDoubleSpinBox()
        self.valueBox.setRange(min,max)
        self.valueBox.valueChanged[float].connect(self.setValue)
        self.valueBox.setSingleStep(0.01*(max-min))

        self.label = QtWidgets.QLabel(name)
        
        self.setLayout(ArrangeV(ArrangeH(self.label, self.valueBox), self.scroll))
        self.setValue(value)

    def setIntValue(self, int_value):
        float_value = int_value*1.0/self.scalingFactor
        self.valueBox.setValue(float_value)

    def setValue(self, float_value):
        int_value = round(self.scalingFactor*float_value)
        self.scroll.setValue(int_value)
        self.valueChanged.emit(float_value)

class ColorMapSettings(QtWidgets.QWidget):
    linearChanged = QtCore.Signal(bool) # TODO: this shouldn't be static
    def __init__(self, min=-1, max=1, min_value=0, max_value=1, direction=Qt.Horizontal):
        super(ColorMapSettings, self).__init__()

        self.rangeMin = RangeGroup("Min", min, max, min_value, direction)
        self.minChanged = self.rangeMin.valueChanged
        self.rangeMax = RangeGroup("Max", min, max, max_value, direction)
        self.maxChanged = self.rangeMax.valueChanged

        self.linear = QtWidgets.QCheckBox('Linear', self)
        self.linear.stateChanged.connect( lambda state: self.linearChanged.emit(state==Qt.Checked))

        self.setLayout( ArrangeV( self.rangeMin, self.rangeMax, self.linear ))

        self.rangeMin.setValue(min_value)
        self.rangeMax.setValue(max_value)

class CollColors(QtWidgets.QWidget):
    colors_changed = QtCore.Signal()

    def __init__(self,coll,initial_color=(0,255,0,255)):
        super().__init__()

        self.initial_color = initial_color

        self.colorbtns = {}
        layouts = []
        self.coll = coll

        def call_func(self,state):
            color = self.obj._color
            if state:
                color.setAlpha(255)
            else:
                color.setAlpha(0)
            self.obj.setColor(color)

        for item in coll:
            if not item in self.colorbtns:
                btn = QColorButton(initial_color=initial_color)
                btn.colorChanged.connect(self.colors_changed.emit)
                cb_visible = QtWidgets.QCheckBox('visible',self)
                cb_visible.setCheckState(QtCore.Qt.Checked)
                cb_visible.stateChanged.connect(ObjectHolder(btn,call_func))
                self.colorbtns[item] = btn
                layouts.append(ArrangeH(btn,QtWidgets.QLabel(item),cb_visible))

        colors = ArrangeV(*layouts)
        colors.layout().setAlignment(Qt.AlignTop)
        btn_random = QtWidgets.QPushButton("Random",self)
        def SetRandom():
            import itertools
            import random
            n = 2
            while n**3+1 < len(self.colorbtns):
                n += 1
            vals = [int(255*i/(n-1)) for i in range(n)]
            colors = [(vals[colr],vals[colg],vals[colb]) for colr, colg, colb in
                      itertools.product(range(n),range(n),range(n))][:-1]
            random.shuffle(colors)


            gr = 0.618033988749895
            h = random.uniform(0,1)
            for i,(name,btn) in enumerate(self.colorbtns.items()):
                h += gr
                h %= 1
                s = [1.0,0.4][i%2]
                v = [1.0,0.8][i%2]
                color = QtGui.QColor()
                color.setHsvF(h,s,v)
                color.setAlpha(btn.color().alpha())
                btn.setColor(color)
            self.colors_changed.emit()

        btn_random.clicked.connect(SetRandom)
        btn_reset = QtWidgets.QPushButton("Reset", self)
        def Reset():
            for name, btn in self.colorbtns.items():
                col = QtGui.QColor(*self.initial_color)
                col.setAlpha( btn.color().alpha() )
                btn.setColor(col)
            self.colors_changed.emit()
        btn_reset.clicked.connect(Reset)
        layout = ArrangeV(colors,ArrangeH(btn_random,btn_reset))
        self.setLayout(layout)

    def getColors(self):
        return [QtGui.QColor(self.colorbtns[item]._color) for item in self.coll]

class RenderingParameters:
    def __init__(self):
        self.rotmat = glmath.Identity()
        self.zoom = 0.0
        self.ratio = 1.0
        self.dx = 0.0
        self.dy = 0.0
        self.min = Vector(3)
        self.min[:] = 0.0
        self.max = Vector(3)
        self.max[:] = 0.0

        self.clipping_rotmat = glmath.Identity()
        self.clipping_normal = Vector(4)
        self.clipping_normal[0] = 1.0
        self.clipping_point = Vector(3)
        self.clipping_dist = 0.0

    @property
    def center(self):
        return 0.5*(self.min+self.max)

    @property
    def model(self):
        mat = glmath.Identity();
        mat = self.rotmat*mat;
        mat = glmath.Translate(self.dx, -self.dy, -0 )*mat;
        mat = glmath.Scale(exp(-self.zoom/100))*mat;
        mat = glmath.Translate(0, -0, -5 )*mat;
        mat = mat*glmath.Translate(-self.center[0], -self.center[1], -self.center[2]) #move to center
        return mat

    @property
    def view(self):
        return glmath.LookAt()

    @property
    def projection(self):
        return glmath.Perspective(0.8, self.ratio, .1, 20.);

    @property
    def clipping_plane(self):
        x = self.clipping_rotmat * self.clipping_normal
        d = glmath.Dot(self.clipping_point,x[0:3])
        x[3] = -d
        x[3] = x[3]-self.clipping_dist
        return x

    def getClippingPlaneNormal(self):
        x = self.clipping_rotmat * self.clipping_normal
        return x[0:3]

    def getClippingPlanePoint(self):
        return self.clipping_point

    def setClippingPlaneNormal(self, normal):
        for i in range(3):
            self.clipping_normal[i] = normal[i]
        self.clipping_rotmat = glmath.Identity()

    def setClippingPlanePoint(self, point):
        for i in range(3):
            self.clipping_point[i] = point[i]

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self,kernel_manager,shared):
        super(MainWindow, self).__init__()

        self.scenes = []

        f = QtOpenGL.QGLFormat()
        f.setVersion(3,2)
        f.setProfile(QtOpenGL.QGLFormat.CoreProfile)
        QtOpenGL.QGLFormat.setDefaultFormat(f)

        self.glWidget = GLWidget(shared=shared)
        if shared is None:
            self.glWidget.context().setFormat(f)
            self.glWidget.context().create()

        buttons = QtWidgets.QVBoxLayout()

        btnZoomReset = QtWidgets.QPushButton("ZoomReset", self)
        btnZoomReset.clicked.connect(self.glWidget.ZoomReset)
        btnQuit = QtWidgets.QPushButton("Quit", self)
        btnQuit.clicked.connect(self.close)
        
        self.colormapSettings = ColorMapSettings(min=-2, max=2, min_value=-1, max_value=1)
        self.colormapSettings.layout().setAlignment(Qt.AlignTop)

        buttons.addWidget(btnZoomReset)
        buttons.addWidget(btnQuit)

        self.toolbox = ToolBox(self)

        mainWidget = QtWidgets.QSplitter()
        settings = QtWidgets.QWidget()
        settings.setLayout( ArrangeV(self.toolbox, buttons))
        mainWidget.addWidget(settings)
        if kernel_manager is not None:
            console_and_gl = QtWidgets.QSplitter()
            console_and_gl.setOrientation(QtCore.Qt.Vertical)
            console_and_gl.addWidget(self.glWidget)
            kernel_client = kernel_manager.client()
            kernel_client.start_channels()
            console = QtInProcessRichJupyterWidget()
            console.kernel_manager = kernel_manager
            console.kernel_client = kernel_client
            console.exit_requested.connect(self.close)
            console_and_gl.addWidget(console)
            console_and_gl.setStretchFactor(0,3)
            console_and_gl.setStretchFactor(1,1)
            mainWidget.addWidget(console_and_gl)
        else:
            mainWidget.addWidget(self.glWidget)
        self.setCentralWidget(mainWidget)

        self.setWindowTitle(self.tr("Pyside2 GL"))
        self.last = time.time()

    def draw(self, scene,position=-1):
        self.scenes.insert(position,scene)
        self.glWidget.makeCurrent()
        scene.update()
        self.glWidget.addScene(scene)
        self.toolbox.addScene(scene,position)

    def redraw(self, blocking=True):
        if time.time() - self.last < 0.02:
            return
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

class GLWidget(QtOpenGL.QGLWidget):
    redraw_signal = QtCore.Signal()

    def ZoomReset(self):
        self.rendering_parameters.rotmat = glmath.Identity()
        self.rendering_parameters.zoom = 0.0
        self.rendering_parameters.dx = 0.0
        self.rendering_parameters.dy = 0.0
        self.updateGL()

    def __init__(self, parent=None,shared=None):
        QtOpenGL.QGLWidget.__init__(self, parent=parent,shareWidget=shared)
        self.scenes = []
        self.do_rotate = False
        self.do_translate = False
        self.do_zoom = False
        self.do_move_clippingplane = False
        self.do_rotate_clippingplane = False
        self.old_time = time.time()
        self.rendering_parameters = RenderingParameters()

        self.redraw_update_done = QtCore.QWaitCondition()
        self.redraw_mutex = QtCore.QMutex()

        self.redraw_signal.connect(self.updateScenes)

        self.lastPos = QtCore.QPoint()

    def minimumSizeHint(self):
        return QtCore.QSize(50, 50)

    def sizeHint(self):
        return QtCore.QSize(400, 400)

    def initializeGL(self):
        self.updateScenes()

    def updateScenes(self):
        self.redraw_mutex.lock()
        self.makeCurrent()
        for scene in self.scenes:
            scene.update()
        self.redraw_update_done.wakeAll()
        self.redraw_mutex.unlock()
        self.update()

    def paintGL(self):
        t = time.time() - self.old_time
#         print("frames per second: ", 1.0/t, end='\r')
        self.old_time = time.time()


        GL.glClearColor( 1, 1, 1, 0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glEnable(GL.GL_BLEND);
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA);
        for scene in self.scenes:
            scene.render(self.rendering_parameters) #model, view, projection)

    def addScene(self, scene):
        self.scenes.append(scene)
        self.scenes.sort(key=lambda x: x.deferRendering())
        box_min = Vector(3)
        box_max = Vector(3)
        box_min[:] = 1e99
        box_max[:] = -1e99
        for scene in self.scenes:
            s_min, s_max = scene.getBoundingBox()
            for i in range(3):
                box_min[i] = min(s_min[i], box_min[i])
                box_max[i] = max(s_max[i], box_max[i])
        self.rendering_parameters.min = box_min
        self.rendering_parameters.max = box_max

    def mouseDoubleClickEvent(self, event):
        import OpenGL.GLU
        viewport = GL.glGetIntegerv( GL.GL_VIEWPORT )
        x = event.pos().x()
        y = viewport[3]-event.pos().y()
        GL.glReadBuffer(GL.GL_FRONT);
        z = GL.glReadPixels(x, y, 1, 1, GL.GL_DEPTH_COMPONENT, GL.GL_FLOAT)
        params = self.rendering_parameters
        p = OpenGL.GLU.gluUnProject(
                x,y,z,
                (params.view*params.model).T.NumPy(),
                params.projection.T.NumPy(),
                viewport,
                )
        for scene in self.scenes:
            scene.doubleClickAction(p)


########################
# font 
#         painter = QtGui.QPainter(self)
#         painter.drawLine(0, 0, 1, 1);
#         painter.end()

# ########################
#         GL.glUseProgram(0)
#         GL.glDisable(GL.GL_DEPTH_TEST)
#         GL.glMatrixMode(GL.GL_PROJECTION)
#         GL.glOrtho( -.5, .5, .5, -.5, -1000, 1000)
#         GL.glMatrixMode(GL.GL_MODELVIEW)
#         GL.glLoadIdentity()
# #         GL.glClearColor(1.0, 1.0, 1.0, 1.0)
# 
# 
#         GL.glClear(GL.GL_COLOR_BUFFER_BIT)
#       
#         self.qglColor(QtCore.Qt.black)
#         self.renderText(0.0, 0.0, 0.0, "Multisampling enabled")
# #         self.renderText(0.15, 0.4, 0.0, "Multisampling disabled")
########################

    def resizeGL(self, width, height):
        GL.glViewport(0, 0, width, height)
        self.rendering_parameters.ratio = width/height

    def mousePressEvent(self, event):
        self.lastPos = QtCore.QPoint(event.pos())
        if event.modifiers() == QtCore.Qt.ControlModifier:
            if event.button() == Qt.MouseButton.RightButton:
                self.do_move_clippingplane = True
            if event.button() == Qt.MouseButton.LeftButton:
                self.do_rotate_clippingplane = True
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self.do_rotate = True
            if event.button() == Qt.MouseButton.MidButton:
                self.do_translate = True
            if event.button() == Qt.MouseButton.RightButton:
                self.do_zoom = True

    def mouseReleaseEvent(self, event):
        self.do_rotate = False
        self.do_translate = False
        self.do_zoom = False
        self.do_move_clippingplane = False
        self.do_rotate_clippingplane = False

    def mouseMoveEvent(self, event):
        dx = event.x() - self.lastPos.x()
        dy = event.y() - self.lastPos.y()
        param = self.rendering_parameters
        if self.do_rotate:
            param.rotmat = glmath.RotateY(-dx/50.0)*param.rotmat
            param.rotmat = glmath.RotateX(-dy/50.0)*param.rotmat
        if self.do_translate:
            s = 200.0*exp(-param.zoom/100)
            param.dx += dx/s
            param.dy += dy/s
        if self.do_zoom:
            param.zoom += dy
        if self.do_move_clippingplane:
            s = 200.0*exp(-param.zoom/100)
            shift = -dy/s*param.getClippingPlaneNormal()
            p = param.getClippingPlanePoint()
            param.setClippingPlanePoint(p+shift)
        if self.do_rotate_clippingplane:
            # rotation of clipping plane is view-dependent
            r = param.rotmat
            param.clipping_rotmat = r.T*glmath.RotateY(-dx/50.0)*r*param.clipping_rotmat
            param.clipping_rotmat = r.T*glmath.RotateX(-dy/50.0)*r*param.clipping_rotmat
        self.lastPos = QtCore.QPoint(event.pos())
        self.updateGL()

    def wheelEvent(self, event):
        self.rendering_parameters.zoom -= event.angleDelta().y()/10
        self.updateGL()

    def freeResources(self):
        self.makeCurrent()

class GUI():
    def __init__(self):
        self.windows = []
        self.app = QtWidgets.QApplication([])
        self.kernel_manager = None

    def make_window(self, console=True):
        if console and self.kernel_manager is None:
            self.kernel_manager = QtInProcessKernelManager()
            class dummyioloop():
                def call_later(self,a,b):
                    return
                def stop(self):
                    return
            self.kernel_manager.start_kernel()
            self.kernel_manager.kernel.io_loop = dummyioloop()
        if console:
            km = self.kernel_manager
        else:
            km = None
        if len(self.windows):
            shared = self.windows[0].glWidget
        else:
            shared = None
        window = MainWindow(kernel_manager=km,shared=shared)
        window.show()
        window.raise_()
        self.windows.append(window)
        return window

    def getWindow(self,index=-1):
        return self.windows[index]

    def draw(self, *args, **kwargs):
        if not len(self.windows):
            self.make_window()
        self.windows[0].draw(*args, **kwargs)

    def redraw(self, blocking=True):
        for win in self.windows:
            win.redraw(blocking=blocking)


    def run(self):
        for i,window in enumerate(self.windows):
            window.draw(scenes.OverlayScene(window.scenes, name="Global options"),position=0)
        self.kernel_manager.kernel.shell.push(inspect.stack()[1][0].f_globals)
        res = self.app.exec_()
        for window in self.windows:
            window.glWidget.freeResources()
