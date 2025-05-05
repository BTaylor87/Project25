# region imports
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


# endregion

# region class definitions
class MainWindow(Ui_Form, qtw.QWidget):
    """
    Main application window for Four-Bar Linkage simulation.

    Inherits from:
        Ui_Form: Generated GUI form class
        qtw.QWidget: Qt widget base class

    Manages:
        - GUI elements and layout
        - Four-bar linkage controller
        - User interaction handling
        - Simulation setup and execution
        - Physics parameter management
    """

    def __init__(self):
        """
        Initialize the main window and configure:
        - UI elements and layout
        - Physics parameter controls
        - Graphics View setup
        - Event filters for user interaction
        - Simulation timer and state management
        """
        super().__init__()
        self.setupUi(self)

        # ─── build the min/max spin‐boxes by hand ─────────────────────────────
        # Configure angle limit controls
        self.nud_MinAngle = qtw.QDoubleSpinBox(self)
        self.nud_MaxAngle = qtw.QDoubleSpinBox(self)
        self.nud_MinAngle.setRange(0.0, 360.0)
        self.nud_MinAngle.setValue(0.0)
        self.nud_MinAngle.setSuffix("°")
        self.nud_MaxAngle.setRange(0.0, 360.0)
        self.nud_MaxAngle.setValue(360.0)
        self.nud_MaxAngle.setSuffix("°")

        # ─── build the mass/spring/damping controls ─────────────────────────
        # Configure physics parameter controls
        self.nud_Mass1 = qtw.QDoubleSpinBox(self)
        self.nud_Mass2 = qtw.QDoubleSpinBox(self)
        self.nud_Mass3 = qtw.QDoubleSpinBox(self)
        self.nud_SpringK = qtw.QDoubleSpinBox(self)
        self.nud_DampC = qtw.QDoubleSpinBox(self)
        self.btn_Simulate = qtw.QPushButton("Simulate", self)

        # Configure ranges and defaults for physics parameters
        for nud in (self.nud_Mass1, self.nud_Mass2, self.nud_Mass3):
            nud.setRange(0.1, 20.0)
            nud.setValue(1.0)
            nud.setSuffix(" kg")
        self.nud_SpringK.setRange(0.0, 1000.0)
        self.nud_SpringK.setValue(50.0)
        self.nud_SpringK.setSuffix(" N·m/rad")
        self.nud_DampC.setRange(0.0, 100.0)
        self.nud_DampC.setValue(5.0)
        self.nud_DampC.setSuffix(" N·m·s/rad")

        # Add widgets to horizontal layout
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

        # Connect signals and slots
        self.nud_MinAngle.valueChanged.connect(self._clampInputAngle)
        self.nud_MaxAngle.valueChanged.connect(self._clampInputAngle)
        self.btn_Simulate.clicked.connect(self.startSimulation)
        self.nud_SpringK.valueChanged.connect(self._updateSpringConstant)

        # region UserInterface setup
        # Initialize graphics view and controller
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

        # Initialize angle tracking
        self.prevAlpha = self.FBL_C.FBL_M.InputLink.angle
        self.prevBeta = self.FBL_C.FBL_M.OutputLink.angle

        # Set initial values
        self.lbl_OutputAngle_Val.setText(
            "{:0.3f}".format(self.FBL_C.FBL_M.OutputLink.AngleDeg())
        )
        self.nud_Link1Length.setValue(self.FBL_C.FBL_M.InputLink.length)
        self.nud_Link3Length.setValue(self.FBL_C.FBL_M.OutputLink.length)

        # Connect UI signals
        self.spnd_Zoom.valueChanged.connect(self.setZoom)
        self.nud_Link1Length.valueChanged.connect(self.setInputLinkLength)
        self.nud_Link3Length.valueChanged.connect(self.setOutputLinkLength)

        # Install event filter for scene interactions
        self.FBL_C.FBL_V.scene.installEventFilter(self)
        self.mouseDown = False
        self.show()
        # endregion

    def setInputLinkLength(self):
        """Update input link length through controller"""
        self.FBL_C.setInputLinkLength()

    def setOutputLinkLength(self):
        """Update output link length through controller"""
        self.FBL_C.setOutputLinkLength()

    def mouseMoveEvent(self, a0: qtg.QMouseEvent):
        """Track mouse position and update window title"""
        w = app.widgetAt(a0.globalPos())
        name = w.objectName() if w else "none"
        self.setWindowTitle(f"{a0.x()},{a0.y()},{name}")

    def eventFilter(self, obj, event):
        """
        Handle scene events:
        - Mouse movement tracking
        - Zoom with mouse wheel
        - Linkage dragging with mouse
        """
        if obj == self.FBL_C.FBL_V.scene:
            if event.type() == qtc.QEvent.GraphicsSceneMouseMove:
                # Update position displays
                screenPos = event.screenPos()
                scenePos = event.scenePos()
                self.setWindowTitle(
                    f"screen x={screenPos.x()}, y={screenPos.y()} : "
                    f"scene x={scenePos.x()}, y={scenePos.y()}"
                )
                # Handle linkage dragging
                if self.mouseDown:
                    self.FBL_C.moveLinkage(scenePos)
                    self._clampInputAngle()

            elif event.type() == qtc.QEvent.GraphicsSceneWheel:
                # Handle zoom control
                if event.delta() > 0:
                    self.spnd_Zoom.stepUp()
                else:
                    self.spnd_Zoom.stepDown()

            elif event.type() == qtc.QEvent.GraphicsSceneMousePress:
                # Start dragging
                if event.button() == qtc.Qt.LeftButton:
                    self.mouseDown = True

            elif event.type() == qtc.QEvent.GraphicsSceneMouseRelease:
                # Stop dragging
                self.mouseDown = False

        return super(MainWindow, self).eventFilter(obj, event)

    def setZoom(self):
        """Apply zoom transformation to graphics view"""
        self.gv_Main.resetTransform()
        self.gv_Main.scale(self.spnd_Zoom.value(), self.spnd_Zoom.value())

    # region === Angle Clamping Methods ===
    def _clampInputAngle(self):
        """
        Constrain input angle to user-defined min/max range
        Updates linkage position and view if correction needed
        """
        amin = self.nud_MinAngle.value()
        amax = self.nud_MaxAngle.value()
        curr = self.FBL_C.FBL_M.InputLink.AngleDeg()

        # Determine if clamping needed
        if curr < amin:
            target = amin
        elif curr > amax:
            target = amax
        else:
            target = None

        if target is not None:
            # Update linkage position
            rad = math.radians(target)
            link = self.FBL_C.FBL_M.InputLink
            link.angle = rad
            L = link.length
            st = link.stPt
            link.enPt.setX(st.x() + math.cos(rad) * L)
            link.enPt.setY(st.y() - math.sin(rad) * L)
            self.FBL_C.FBL_M.moveLinkage(link.enPt)
            self.FBL_C.FBL_V.scene.update()

        # Update input angle display
        self.nud_InputAngle.setValue(
            self.FBL_C.FBL_M.InputLink.AngleDeg()
        )

    # endregion

    # region === Simulation Methods ===
    def startSimulation(self):
        """
        Initialize and run physics simulation:
        - Collect parameters from UI
        - Calculate moment of inertia
        - Set up and solve differential equations
        - Start animation timer
        """
        # Get parameters from UI
        m1 = self.nud_Mass1.value()
        m2 = self.nud_Mass2.value()
        m3 = self.nud_Mass3.value()
        k = self.nud_SpringK.value()
        c = self.nud_DampC.value()

        # Get link lengths from model
        L1 = self.FBL_C.FBL_M.InputLink.length
        L2 = self.FBL_C.FBL_M.DragLink.length
        L3 = self.FBL_C.FBL_M.OutputLink.length

        # Calculate moments of inertia (assuming thin rods)
        I1 = (1 / 3) * m1 * L1 ** 2
        I2 = (1 / 3) * m2 * L2 ** 2
        I3 = (1 / 3) * m3 * L3 ** 2
        I_tot = I1 + I2 + I3

        # Set equilibrium and initial conditions
        θ_eq = 90.0  # Spring equilibrium at 90 degrees
        θ0 = self.FBL_C.FBL_M.InputLink.AngleDeg()
        ω0 = 0.0  # Initial angular velocity

        # Configure time parameters
        t_max = 5.0  # Simulation duration (seconds)
        t_eval = np.linspace(0, t_max, int(t_max * 60))  # 60 Hz sampling

        # Define system dynamics
        def state_eq(t, y):
            """System state equations for ODE solver"""
            θ, ω = y
            return [ω, (-k * (θ - θ_eq) - c * ω) / I_tot]

        # Solve differential equations
        sol = sp.integrate.solve_ivp(
            state_eq,
            (0, t_max),
            [θ0, ω0],
            t_eval=t_eval,
            rtol=1e-6, atol=1e-8
        )

        # Store simulation results
        self.sim_t = sol.t
        self.sim_theta = sol.y[0]
        self.sim_index = 0

        # Configure animation timer
        self.timer = qtc.QTimer(self)
        self.timer.setInterval(int(1000 / 60))  # ~60 FPS
        self.timer.timeout.connect(self._stepSimulation)
        # Disable user interaction during simulation
        self.FBL_C.FBL_V.scene.removeEventFilter(self)
        self.timer.start()

    def _stepSimulation(self):
        """Update linkage position for current simulation step"""
        if self.sim_index < len(self.sim_theta):
            θ = self.sim_theta[self.sim_index]
            # Update model with new angle
            rad = math.radians(θ)
            link = self.FBL_C.FBL_M.InputLink
            link.angle = rad
            L = link.length
            st = link.stPt
            link.enPt.setX(st.x() + math.cos(rad) * L)
            link.enPt.setY(st.y() - math.sin(rad) * L)
            self.FBL_C.FBL_M.moveLinkage(link.enPt)
            # Refresh view and UI
            self.FBL_C.FBL_V.scene.update()
            self.nud_InputAngle.setValue(θ)
            self.sim_index += 1
        else:
            # End simulation
            self.timer.stop()
            self.FBL_C.FBL_V.scene.installEventFilter(self)

    # endregion

    # region === Spring Constant Updates ===
    def _updateSpringConstant(self, k_new: float):
        """
        Update spring constant in model and refresh display
        Args:
            k_new: New spring constant value (N·m/rad)
        """
        self.FBL_C.FBL_M.Spring.k = k_new
        self.FBL_C.FBL_M.Spring.setToolTip(f"k = {k_new:.1f} N·m/rad")
        self.FBL_C.FBL_V.scene.update()
    # endregion


# endregion

# region function calls
if __name__ == '__main__':
    """Main application entry point"""
    app = qtw.QApplication(sys.argv)
    mw = MainWindow()
    mw.setWindowTitle('Four Bar Linkage')
    sys.exit(app.exec())
# endregion

#helped by chatGPT, deepseek, Miguel and Kaleb