#region imports
from FourBar_GUI import Ui_Form
from FourBarLinkage_MVC import FourBarLinkage_Controller
import PyQt5.QtGui as qtg
import PyQt5.QtCore as qtc
import PyQt5.QtWidgets as qtw
import math
import sys
import numpy as np
import scipy as sp
from scipy import optimize
from copy import deepcopy as dc
#endregion

#region class definitions
class MainWindow(Ui_Form, qtw.QWidget):
    def __init__(self):
        """
        This program illustrates the use of the graphics view framework.
        The QGraphicsView widget is created in designer.  The QGraphicsView displays a QGraphicsScene.
        A QGraphicsScene contains QGraphicsItem objects.
        """
        super().__init__()
        self.setupUi(self)

        # ─── build the min/max spin‐boxes by hand ─────────────────────────────
        self.nud_MinAngle = qtw.QDoubleSpinBox(self)
        self.nud_MaxAngle = qtw.QDoubleSpinBox(self)
        self.nud_MinAngle.setRange(0.0, 360.0)
        self.nud_MinAngle.setValue(0.0)
        self.nud_MinAngle.setSuffix("°")
        self.nud_MaxAngle.setRange(0.0, 360.0)
        self.nud_MaxAngle.setValue(360.0)
        self.nud_MaxAngle.setSuffix("°")
        # ─── build the mass/spring/damping controls ─────────────────────────
        self.nud_Mass1 = qtw.QDoubleSpinBox(self)
        self.nud_Mass2 = qtw.QDoubleSpinBox(self)
        self.nud_Mass3 = qtw.QDoubleSpinBox(self)
        self.nud_SpringK = qtw.QDoubleSpinBox(self)
        self.nud_DampC   = qtw.QDoubleSpinBox(self)
        self.btn_Simulate= qtw.QPushButton("Simulate", self)

        # configure ranges/defaults
        for nud in (self.nud_Mass1, self.nud_Mass2, self.nud_Mass3):
            nud.setRange(0.1,  20.0)
            nud.setValue(1.0)
            nud.setSuffix(" kg")
        self.nud_SpringK.setRange(0.0, 1000.0)
        self.nud_SpringK.setValue(50.0)
        self.nud_SpringK.setSuffix(" N·m/rad")
        self.nud_DampC.setRange(0.0, 100.0)
        self.nud_DampC.setValue(5.0)
        self.nud_DampC.setSuffix(" N·m·s/rad")

        # insert into your existing horizontalLayout
        self.horizontalLayout.addWidget(self.nud_MinAngle)
        self.horizontalLayout.addWidget(self.nud_MaxAngle)
        self.horizontalLayout.addWidget(qtw.QLabel("m1:"))
        self.horizontalLayout.addWidget(self.nud_Mass1)
        self.horizontalLayout.addWidget(qtw.QLabel("m2:"))
        self.horizontalLayout.addWidget(self.nud_Mass2)
        self.horizontalLayout.addWidget(qtw.QLabel("m3:"))
        self.horizontalLayout.addWidget(self.nud_Mass3)
        self.horizontalLayout.addWidget(qtw.QLabel("k:"))
        self.horizontalLayout.addWidget(self.nud_SpringK)
        self.horizontalLayout.addWidget(qtw.QLabel("c:"))
        self.horizontalLayout.addWidget(self.nud_DampC)
        self.horizontalLayout.addWidget(self.btn_Simulate)

        # wire up clamping and simulation
        self.nud_MinAngle.valueChanged.connect(self._clampInputAngle)
        self.nud_MaxAngle.valueChanged.connect(self._clampInputAngle)
        self.btn_Simulate.clicked.connect(self.startSimulation)
        # ──────────────────────────────────────────────────────────────────

        #region UserInterface stuff here
        widgets = [
            self.gv_Main,
            self.nud_InputAngle,
            self.lbl_OutputAngle_Val,
            self.nud_Link1Length,
            self.nud_Link3Length,
            self.spnd_Zoom
        ]
        self.FBL_C = FourBarLinkage_Controller(widgets)
        self.FBL_C.setupGraphics()
        self.gv_Main.setMouseTracking(True)
        self.setMouseTracking(True)
        self.FBL_C.buildScene()

        self.prevAlpha = self.FBL_C.FBL_M.InputLink.angle
        self.prevBeta  = self.FBL_C.FBL_M.OutputLink.angle

        self.lbl_OutputAngle_Val.setText(
            "{:0.3f}".format(self.FBL_C.FBL_M.OutputLink.AngleDeg())
        )
        self.nud_Link1Length.setValue(self.FBL_C.FBL_M.InputLink.length)
        self.nud_Link3Length.setValue(self.FBL_C.FBL_M.OutputLink.length)

        self.spnd_Zoom.valueChanged.connect(self.setZoom)
        self.nud_Link1Length.valueChanged.connect(self.setInputLinkLength)
        self.nud_Link3Length.valueChanged.connect(self.setOutputLinkLength)

        self.FBL_C.FBL_V.scene.installEventFilter(self)
        self.mouseDown = False
        self.show()
        #endregion

    def setInputLinkLength(self):
        self.FBL_C.setInputLinkLength()

    def setOutputLinkLength(self):
        self.FBL_C.setOutputLinkLength()

    def mouseMoveEvent(self, a0: qtg.QMouseEvent):
        w    = app.widgetAt(a0.globalPos())
        name = w.objectName() if w else "none"
        self.setWindowTitle(f"{a0.x()},{a0.y()},{name}")

    def eventFilter(self, obj, event):
        if obj == self.FBL_C.FBL_V.scene:
            if event.type() == qtc.QEvent.GraphicsSceneMouseMove:
                screenPos = event.screenPos()
                scenePos  = event.scenePos()
                self.setWindowTitle(
                    f"screen x={screenPos.x()}, y={screenPos.y()} : "
                    f"scene x={scenePos.x()}, y={scenePos.y()}"
                )
                if self.mouseDown:
                    self.FBL_C.moveLinkage(scenePos)
                    self._clampInputAngle()

            elif event.type() == qtc.QEvent.GraphicsSceneWheel:
                if event.delta()>0:
                    self.spnd_Zoom.stepUp()
                else:
                    self.spnd_Zoom.stepDown()

            elif event.type() == qtc.QEvent.GraphicsSceneMousePress:
                if event.button()==qtc.Qt.LeftButton:
                    self.mouseDown = True

            elif event.type() == qtc.QEvent.GraphicsSceneMouseRelease:
                self.mouseDown = False

        return super(MainWindow, self).eventFilter(obj, event)

    def setZoom(self):
        self.gv_Main.resetTransform()
        self.gv_Main.scale(self.spnd_Zoom.value(), self.spnd_Zoom.value())

    #region === helper: clamp current input‐link angle to [min, max] ===
    def _clampInputAngle(self):
        amin = self.nud_MinAngle.value()
        amax = self.nud_MaxAngle.value()
        curr = self.FBL_C.FBL_M.InputLink.AngleDeg()

        if curr < amin:
            target = amin
        elif curr > amax:
            target = amax
        else:
            target = None

        if target is not None:
            rad = math.radians(target)
            link = self.FBL_C.FBL_M.InputLink
            link.angle = rad
            L  = link.length
            st = link.stPt
            link.enPt.setX(st.x() + math.cos(rad)*L)
            link.enPt.setY(st.y() - math.sin(rad)*L)
            self.FBL_C.FBL_M.moveLinkage(link.enPt)
            self.FBL_C.FBL_V.scene.update()

        self.nud_InputAngle.setValue(
            self.FBL_C.FBL_M.InputLink.AngleDeg()
        )
    #endregion

    #region === Simulation methods for Task 3 ===
    def startSimulation(self):
        """
        Reads masses, k, c, solves:
          I_tot θ¨ + c θ˙ + k (θ − 90°) = 0
        starting from current θ, θ˙=0.
        """
        # grab parameters
        m1 = self.nud_Mass1.value()
        m2 = self.nud_Mass2.value()
        m3 = self.nud_Mass3.value()
        k  = self.nud_SpringK.value()
        c  = self.nud_DampC.value()

        # link lengths
        L1 = self.FBL_C.FBL_M.InputLink.length
        # —— corrected here: use DragLink, not Coupler ——
        L2 = self.FBL_C.FBL_M.DragLink.length
        L3 = self.FBL_C.FBL_M.OutputLink.length

        # approximate total inertia about input pivot
        I1 = (1/3)*m1 * L1**2
        I2 = (1/3)*m2 * L2**2
        I3 = (1/3)*m3 * L3**2
        I_tot = I1 + I2 + I3

        # equilibrium and initial conditions
        θ_eq = 90.0
        θ0   = self.FBL_C.FBL_M.InputLink.AngleDeg()
        ω0   = 0.0

        # time span & evaluation points
        t_max   = 5.0                                        # seconds
        t_eval  = np.linspace(0, t_max, int(t_max*60))      # 60 Hz sampling

        # define the state ODE: y = [θ, ω]
        def state_eq(t, y):
            θ, ω = y
            return [ω, (-k*(θ-θ_eq) - c*ω) / I_tot]

        # solve
        sol = sp.integrate.solve_ivp(
            state_eq,
            (0, t_max),
            [θ0, ω0],
            t_eval=t_eval,
            rtol=1e-6, atol=1e-8
        )

        # store for animation
        self.sim_t     = sol.t
        self.sim_theta = sol.y[0]
        self.sim_index = 0

        # set up a timer to step through the solution
        self.timer = qtc.QTimer(self)
        self.timer.setInterval(int(1000/60))  # ~60 FPS
        self.timer.timeout.connect(self._stepSimulation)
        # disable user drag while simulating
        self.FBL_C.FBL_V.scene.removeEventFilter(self)
        self.timer.start()

    def _stepSimulation(self):
        if self.sim_index < len(self.sim_theta):
            θ = self.sim_theta[self.sim_index]
            # update model
            rad = math.radians(θ)
            link = self.FBL_C.FBL_M.InputLink
            link.angle = rad
            L  = link.length
            st = link.stPt
            link.enPt.setX(st.x() + math.cos(rad)*L)
            link.enPt.setY(st.y() - math.sin(rad)*L)
            self.FBL_C.FBL_M.moveLinkage(link.enPt)
            self.FBL_C.FBL_V.scene.update()
            self.nud_InputAngle.setValue(θ)
            self.sim_index += 1
        else:
            self.timer.stop()
            # re-enable dragging
            self.FBL_C.FBL_V.scene.installEventFilter(self)
    #endregion
#endregion

#region function calls
if __name__ == '__main__':
    app = qtw.QApplication(sys.argv)
    mw  = MainWindow()
    mw.setWindowTitle('Four Bar Linkage')
    sys.exit(app.exec())
#endregion
