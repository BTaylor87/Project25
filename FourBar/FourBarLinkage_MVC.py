#region imports
import PyQt5.QtGui as qtg
import PyQt5.QtCore as qtc
import PyQt5.QtWidgets as qtw
import math
from scipy import optimize
from copy import deepcopy as dc
#endregion

#region four bar linkage classes in MVC Pattern
"""
The Model-View-Controller design patter divides the duties between retaining the state of an object (model) and the 
display of the state of the object (view) to the user/GUI/CLI.  The controller mediates all updates of the model and the
view caused by a change in state of the model or user interaction with the view (e.g., mouse movement or clicks).
"""
#region model and supporting classes
class RigidLink(qtw.QGraphicsItem):
    def __init__(self, stX=0, stY=0, enX=1, enY=1, radius=10, mass=10,
                 parent=None, pen=None, brush=None, name='RigidLink',
                 label_pen=qtg.QPen(qtc.Qt.black)):
        """
        This is a custom class for drawing a rigid link.  The paint function executes every time
        the scene updates.  See header comment in your original for full details.
        """
        super().__init__(parent)

        # step 1: store styling & IDs
        self.pen       = pen
        self.label_pen = label_pen
        self.brush     = brush
        self.name      = name

        # step 1: define start/end points
        self.stPt = qtc.QPointF(stX, stY)
        self.enPt = qtc.QPointF(enX, enY)
        # ─── LEGACY ALIAS ───────────────────────────────────────────────
        # allow references to .endPt to work exactly like .enPt
        self.endPt = self.enPt
        # ────────────────────────────────────────────────────────────────

        self.radius = radius
        self.mass   = mass  # assume uniform distribution

        # step 2: compute current angle & length
        self.angle = self.linkAngle()

        # step 3: initial bounding rect (will be updated in paint)
        self.rect = qtc.QRectF(-self.radius, -self.radius,
                               self.length + self.radius, self.radius)

        # step 4: prepare transform
        self.transform = qtg.QTransform()
        self.transform.reset()

    def boundingRect(self):
        return self.transform.mapRect(self.rect)

    def deltaY(self):
        self.DY = self.enPt.y() - self.stPt.y()
        return self.DY

    def deltaX(self):
        self.DX = self.enPt.x() - self.stPt.x()
        return self.DX

    def linkLength(self):
        self.length = math.hypot(self.deltaX(), self.deltaY())
        return self.length

    def linkAngle(self):
        self.linkLength()
        if self.length == 0:
            self.angle = 0
        else:
            self.angle = math.acos(self.DX / self.length)
            if self.DY > 0:
                self.angle *= -1
        # wrap into [0,2π)
        while self.angle < 0:
            self.angle += 2 * math.pi
        while self.angle >= 2 * math.pi:
            self.angle -= 2 * math.pi
        return self.angle

    def AngleDeg(self):
        return self.angle * 180.0 / math.pi

    def paint(self, painter, option, widget=None):
        """
        Draw a semicircle at the start, a centerline, the body of the link, semicircle at the end,
        pivots, name, and apply the proper rotation + translation.
        """
        path = qtg.QPainterPath()
        length = self.linkLength()
        angDeg = self.linkAngle() * 180.0 / math.pi

        # bounding circles
        rectSt = qtc.QRectF(-self.radius, -self.radius,
                             2*self.radius, 2*self.radius)
        rectEn = qtc.QRectF(self.length - self.radius, -self.radius,
                             2*self.radius, 2*self.radius)

        # centerline (dashed)
        centerPen = qtg.QPen(self.pen.color())
        centerPen.setStyle(qtc.Qt.DashDotLine)
        r, g, b, a = self.pen.color().getRgb()
        centerPen.setColor(qtg.QColor(r, g, b, 128))
        centerPen.setWidth(1)
        painter.setPen(centerPen)
        painter.drawLine(qtc.QPointF(0,0), qtc.QPointF(length,0))

        # build link body
        path.arcMoveTo(rectSt, 90);  path.arcTo(rectSt, 90, 180)
        path.lineTo(self.length, self.radius)
        path.arcMoveTo(rectEn, 270); path.arcTo(rectEn, 270, 180)
        path.lineTo(0, -self.radius)

        # draw body
        if self.pen:   painter.setPen(self.pen)
        if self.brush: painter.setBrush(self.brush)
        painter.drawPath(path)

        # draw pivot circles
        pivotSt = qtc.QRectF(-self.radius/6, -self.radius/6,
                             self.radius/3, self.radius/3)
        pivotEn = qtc.QRectF(self.length - self.radius/6, -self.radius/6,
                             self.radius/3, self.radius/3)
        painter.drawEllipse(pivotSt)
        painter.drawEllipse(pivotEn)

        # update bounding rect for picking
        self.rect = qtc.QRectF(-self.radius, -self.radius,
                               self.length + 2*self.radius, 2*self.radius)

        # draw label
        painter.setBrush(qtg.QBrush(qtc.Qt.black))
        painter.setPen(self.label_pen)
        painter.setFont(qtg.QFont("Times", self.radius))
        painter.drawText(self.rect, qtc.Qt.AlignCenter, self.name)

        # apply transformation: rotate then translate
        self.transform.reset()
        self.transform.translate(self.stPt.x(), self.stPt.y())
        self.transform.rotate(-angDeg)
        self.setTransform(self.transform)

        # update tooltip
        info = (f"{self.name}\n"
                f"start: ({self.stPt.x():.3f},{self.stPt.y():.3f})\n"
                f"end:   ({self.enPt.x():.3f},{self.enPt.y():.3f})\n"
                f"length: {self.length:.3f}\n"
                f"angle:  {self.angle*180/math.pi:.3f}")
        self.setToolTip(info)

class RigidPivotPoint(qtw.QGraphicsItem):
    def __init__(self, ptX=0, ptY=0, pivotHeight=10, pivotWidth=10, parent=None, pen=None, brush=None, rotation=0,
                 name='RigidPivotPoint', label_pen=None):
        """
        This is a class for the pivot points that are immobile (i.e., connected to ground).
        The pivot is drawn with a dot to represent the actual pin joint, a rounded plate, and a ground plane.
        Optionally, the name of the pivot can be displayed to the right, left, above or below the pivot.
        :param ptX: The x location of the pin joint (i.e., the dot)
        :param ptY: The y location of the pin joint (i.e., the dot)
        :param pivotHeight: The height of the rounded plate.
        :param pivotWidth: The width of the rounded plate
        :param parent:
        :param pen: Pen for drawing the outline of the plate
        :param brush: Brush for drawing the ground plane
        :param rotation: Orientation of the ground plane
        :param name: Name of the pivot.
        :param label_pen:  a pen for drawing a label
        """
        super().__init__(parent)
        self.x = ptX
        self.y = ptY
        self.pt = qtc.QPointF(ptX, ptY)
        self.pen = pen if pen is not None else qtg.QPen(qtg.QColor('black'))
        self.brush = brush
        self.height = pivotHeight
        self.width = pivotWidth
        self.radius = min(self.height, self.width) / 4
        self.rect = qtc.QRectF(self.x - self.width / 2, self.y - self.radius, self.width, self.height + self.radius)
        self.rotationAngle = rotation
        self.name = name
        self.transformation = qtg.QTransform()
        stTT = self.name + "\nx={:0.3f}, y={:0.3f}".format(self.x, self.y)
        self.setToolTip(stTT)
        # self.tag_location = args['tag_location']

    def boundingRect(self):
        bounding_rect = self.transformation.mapRect(self.rect)
        return bounding_rect

    def rotate(self, angle):
        self.rotationAngle = angle

    def paint(self, painter, option, widget=None):
        path = qtg.QPainterPath()
        radius = min(self.height, self.width) / 2
        name = self.name
        H = math.sqrt(math.pow(self.width / 2, 2) + math.pow(self.height, 2))
        phi = math.asin(radius / H)
        theta = math.asin(self.height / H)
        ang = math.pi - phi - theta
        l = H * math.cos(phi)

        x1 = self.width / 2
        y1 = self.height
        path.moveTo(x1, y1)
        x2 = l * math.cos(ang)
        y2 = l * math.sin(ang)
        path.lineTo(x1 + x2, y1 - y2)
        pivotRect = qtc.QRectF(-radius, -radius, 2 * radius, 2 * radius)
        stAng = math.pi / 2 - phi - theta
        spanAng = math.pi - 2 * stAng
        path.arcTo(pivotRect, stAng * 180 / math.pi, spanAng * 180 / math.pi)
        x4 = -self.width / 2
        y4 = +self.height
        path.lineTo(x4, y4)
        # path.arcTo(pivotRect,ang*180/math.pi, 90)
        if self.pen is not None:
            painter.setPen(self.pen)  # Red color pen
        if self.brush is not None:
            painter.setBrush(self.brush)
        painter.drawPath(path)

        pivotPtRect = qtc.QRectF(-radius / 4, -radius / 4, radius / 2, radius / 2)
        painter.drawEllipse(pivotPtRect)
        x5 = -self.width
        x6 = +self.width

        # Draw the symbol for the ground
        painter.drawLine(x5, y4, x6, y4)

        penOutline = qtg.QPen(qtc.Qt.NoPen)
        hatchbrush = qtg.QBrush(qtc.Qt.BDiagPattern)
        brushTransform = qtg.QTransform()
        brushTransform.scale(0.5, 0.5)
        hatchbrush.setTransform(brushTransform)
        painter.setPen(penOutline)
        painter.setBrush(hatchbrush)
        painter.setFont(qtg.QFont("Arial", 3))
        support = qtc.QRectF(x5, y4, self.width * 2, self.height)
        painter.drawRect(support)

        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        painter.drawText(support, qtc.Qt.AlignCenter, name)
        self.rect = qtc.QRectF(-self.width, -self.radius, self.width * 2, self.height * 2 + self.radius)
        self.transformation.reset()
        self.transformation.translate(self.x, self.y)
        self.transformation.rotate(self.rotationAngle)
        self.setTransform(self.transformation)

        self.transformation.reset()
        # brPen=qtg.QPen()
        # brPen.setWidth(0)
        # painter.setPen(brPen)
        # painter.drawRect(self.boundingRect())
class Tracer(qtw.QGraphicsItem):
    def __init__(self, x=0, y=0, pen=None, penOutline = qtg.QPen(qtc.Qt.black)):
        super().__init__()
        self.pts = [qtc.QPointF(x, y)]
        self.rect = qtc.QRectF(-5, -5, 10, 10)
        self.pen = pen
        self.penOutline = penOutline

    def boundingRect(self):
        bounding_rect = self.rect
        return bounding_rect

    def lastPt(self):
        return self.pts[len(self.pts) - 1]

    def paint(self, painter, option, widget=None):
        if self.pen is not None:
            painter.setPen(self.pen)
        path = qtg.QPainterPath()
        if len(self.pts) > 0:
            path.moveTo(self.pts[0])
        for i in range(1, len(self.pts)):
            path.lineTo(self.pts[i])
        painter.drawPath(path)
        pt = self.pts[len(self.pts) - 1]
        painter.setPen(self.penOutline)
        painter.drawEllipse(qtc.QRectF(pt.x() - 2.5, pt.y() - 2.5, 5, 5))
class LinearSpring(qtw.QGraphicsItem):
    def __init__(self, ptSt=qtc.QPointF(0, 0), ptEn=qtc.QPointF(1, 1), coilsWidth=10, coilsLength=30, parent=None,
                 pen=None, name='Spring', label=None, k=10, nCoils=6):
        """
        This is my class for a spring,
        :param ptSt: a QPointF point
        :param ptEn: a QPointF point
        :param coilsWidth: float for width of coils part
        :param coilsLength: float for free length of coils part
        :param parent:
        :param pen: for drawing the lines
        :param brush: not used for this one
        :param name: just a convenient name
        :param label: text to be displayed beside the spring
        :param k: the spring constant
        :param nCoils: number of coils to be drawn
        """
        super().__init__(parent)
        self.stPt = ptSt
        self.enPt = ptEn
        self.freeLength = self.getLength()  # this assumes the spring to be free on initial definition
        self.DL = self.length - self.freeLength
        self.centerPt = (self.stPt + self.enPt) / 2.0
        self.force = 0
        self.pen = pen
        self.coilsWidth = coilsWidth
        self.coilsLength = coilsLength
        self.top = - self.coilsLength / 2
        self.left = -self.coilsWidth / 2
        self.rect = qtc.QRectF(self.left, self.top, self.coilsWidth, self.coilsLength)
        self.name = name
        self.label = label
        self.k = k
        self.nCoils = nCoils
        self.transformation = qtg.QTransform()
        stTT = self.name + "\nx={:0.1f}, y={:0.1f}\nk = {:0.1f}".format(self.centerPt.x(), self.centerPt.y(), self.k)
        self.setToolTip(stTT)

    def setk(self, k=None):
        if k is not None:
            self.k = k
            stTT = self.name + "\nx={:0.3f}, y={:0.3f}\nk = {:0.3f}".format(self.stPt.x(), self.stPt.y(), self.k)
            self.setToolTip(stTT)

    def boundingRect(self):
        bounding_rect = self.transformation.mapRect(self.rect)
        return bounding_rect

    def getLength(self):
        p = self.enPt - self.stPt
        self.length = math.sqrt(p.x() ** 2 + p.y() ** 2)
        return self.length

    def getForce(self):
        self.force = self.k * self.getDL()
        return self.force

    def getDL(self):
        self.DL = self.length - self.freeLength
        return self.DL

    def getAngleDeg(self):
        p = self.enPt - self.stPt
        self.angleRad = math.atan2(p.y(), p.x())
        self.angleDeg = 180.0 / math.pi * self.angleRad
        return self.angleDeg

    def paint(self, painter, option, widget=None):
        """
        My method for drawing the spring is:
        Step 1:  compute the rectangle that will contain the coils section
            - call self.getLength()
            - call self.getDL() # note that self.DL < 0 for compression > 0 for tension
            - self.rect = qtc.QRectF(-(self.coilLength+self.DL)/2, -self.coilWidth/2, (self.coilLength+self.DL), self.coilWidth)
        Step 2: draw lines representing the coils
        Step 3: draw lines connecting (-self.length/2,0) to (self.rect.left,0) and (self.rect.right,0) to (self.length/2,0)
        Step 4: draw little circles at (-self.length/2,0) and (self.length/2,0)
        Step 5: translate by (self.length/2,0)
        Step 6: rotate to self.angleDeg
        Step 7: translate to stPt
        Step 8: decorate with text
        :param painter:
        :param option:
        :param widget:
        :return:
        """
        self.transformation.reset()

        if self.pen is not None:
            painter.setPen(self.pen)  # Red color pen
        # Step 1:
        self.getLength()
        self.getAngleDeg()
        self.getDL()
        ht = self.coilsWidth
        wd = self.coilsLength + self.DL
        top = -ht / 2
        left = -wd / 2
        right = wd / 2
        self.rect = qtc.QRectF(left, top, wd, ht)
        # painter.drawRect(self.rect)
        # Step 2:
        painter.drawLine(qtc.QPointF(left, 0), qtc.QPointF(left, ht / 2))
        dX = wd / (self.nCoils)
        for i in range(self.nCoils):
            painter.drawLine(qtc.QPointF(left + i * dX, ht / 2), qtc.QPointF(left + (i + 0.5) * dX, -ht / 2))
            painter.drawLine(qtc.QPointF(left + (i + 0.5) * dX, -ht / 2), qtc.QPointF(left + (i + 1) * dX, ht / 2))
        painter.drawLine(qtc.QPointF(right, ht / 2), qtc.QPointF(right, 0))
        # Step 3:
        painter.drawLine(qtc.QPointF(-self.length / 2, 0), qtc.QPointF(left, 0))
        painter.drawLine(qtc.QPointF(right, 0), qtc.QPointF(self.length / 2, 0))
        # Step 4:
        nodeRad = 2
        stRec = qtc.QRectF(-self.length / 2 - nodeRad, -nodeRad, 2 * nodeRad, 2 * nodeRad)
        enRec = qtc.QRectF(self.length / 2 - nodeRad, -nodeRad, 2 * nodeRad, 2 * nodeRad)
        painter.drawEllipse(stRec)
        painter.drawEllipse(enRec)
        # Step 5:
        self.transformation.translate(self.stPt.x(), self.stPt.y())
        self.transformation.rotate(self.angleDeg)
        self.transformation.translate(self.length / 2, 0)
        self.setTransform(self.transformation)
        # Step 6:
        self.transformation.reset()
        font = painter.font()
        font.setPointSize(6)
        painter.setFont(font)
        text = "k = {:0.1f} N/m".format(self.k)
        text += ", F = {:0.2f} N".format(self.force)
        fm = qtg.QFontMetrics(painter.font())
        centerPt = (self.stPt + self.enPt) / 2, 0
        painter.drawText(qtc.QPointF(-fm.width(text) / 2.0, fm.height() / 2.0), text)
        if self.label is not None:
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(qtc.QPointF((self.coilsWidth / 2.0) + 10, 0), self.label)

        self.transformation.reset()
        # brPen=qtg.QPen()
        # brPen.setWidth(0)
        # painter.setPen(brPen)
        # painter.setBrush(qtc.Qt.NoBrush)
        # painter.drawRect(self.boundingRect())
class DashPot(qtw.QGraphicsItem):
    def __init__(self, ptSt=qtc.QPointF(0, 0), ptEn=qtc.QPointF(1, 1), dpWidth=10, dpLength=30, parent=None, pen=None,
                 name='Dashpot', label=None, c=10):
        """
        This is my class for a dashpot,
        :param ptSt: a QPointF point
        :param ptEn: a QPointF point
        :param dpWidth: float for width of dashpot part
        :param dpLength: float for free length of dashpot part
        :param parent:
        :param pen: for drawing the lines
        :param brush: not used for this one
        :param name: just a convenient name
        :param label: text to be displayed beside the dashpot
        :param c: the dashpot coefficient
        """
        super().__init__(parent)
        self.stPt = ptSt
        self.enPt = ptEn
        self.freeLength = self.getLength()  # this assumes the dashpot to be free on initial definition
        self.DL = self.length - self.freeLength
        self.centerPt = (self.stPt + self.enPt) / 2.0
        self.pen = pen
        self.Width = dpWidth
        self.Length = dpLength
        self.conn1Len = self.freeLength - self.Length
        self.conn1Len /= 2
        self.conn2Len = self.freeLength / 2
        self.top = - self.Length / 2
        self.left = -self.Width / 2
        self.rect = qtc.QRectF(self.left, self.top, self.Width, self.Length)
        self.name = name
        self.label = label
        self.c = c
        self.transformation = qtg.QTransform()
        stTT = self.name + "\nx={:0.1f}, y={:0.1f}\nc = {:0.1f}".format(self.centerPt.x(), self.centerPt.y(), self.c)
        self.setToolTip(stTT)

    def setc(self, c=None):
        if c is not None:
            self.c = c
            stTT = self.name + "\nx={:0.3f}, y={:0.3f}\nc = {:0.3f}".format(self.stPt.x(), self.stPt.y(), self.c)
            self.setToolTip(stTT)

    def boundingRect(self):
        bounding_rect = self.transformation.mapRect(self.rect)
        return bounding_rect

    def getLength(self):
        p = self.enPt - self.stPt
        self.length = math.sqrt(p.x() ** 2 + p.y() ** 2)
        return self.length

    def getDL(self):
        self.DL = self.length - self.freeLength
        return self.DL

    def getAngleDeg(self):
        p = self.enPt - self.stPt
        self.angleRad = math.atan2(p.y(), p.x())
        self.angleDeg = 180.0 / math.pi * self.angleRad
        return self.angleDeg

    def paint(self, painter, option, widget=None):
        """
        My method for drawing the spring is:
        Step 1:  compute the rectangle that will contain the dashpot section
            - call self.getLength()
            - call self.getDL() # note that self.DL < 0 for compression > 0 for tension
            - self.rect = qtc.QRectF(-(self.FBL.DashPotLength)/2, -self.FBL.DashPotWidth/2, (self.FBL.DashPotLength), self.FBL.DashPotWidth)
        Step 2: draw lines representing the dashpot
        Step 3: draw lines connecting (-self.length/2,0) to (self.rect.left,0) and (self.rect.right,0) to (self.length/2,0)
        Step 4: draw little circles at (-self.length/2,0) and (self.length/2,0)
        Step 5: translate by (self.length/2,0)
        Step 6: rotate to self.angleDeg
        Step 7: translate to stPt
        Step 8: decorate with text
        :param painter:
        :param option:
        :param widget:
        :return:
        """
        self.transformation.reset()

        if self.pen is not None:
            painter.setPen(self.pen)  # Red color pen
        # Step 1:
        self.getLength()
        self.getAngleDeg()
        self.getDL()
        ht = self.Width
        wd = self.Length
        top = -ht / 2
        left = self.conn1Len
        right = left + wd
        self.rect = qtc.QRectF(left, top, wd, ht)
        # painter.drawRect(self.rect)
        # Step 2:
        painter.drawLine(qtc.QPointF(left, -ht / 2), qtc.QPointF(left, ht / 2))
        painter.drawLine(qtc.QPointF(left, -ht / 2), qtc.QPointF(right, -ht / 2))
        painter.drawLine(qtc.QPointF(left, ht / 2), qtc.QPointF(right, ht / 2))
        painter.drawLine(qtc.QPointF(left + wd / 2 + self.DL, ht / 2 * 0.95),
                         qtc.QPointF(left + wd / 2 + self.DL, -ht / 2 * 0.95))
        # Step 3:
        painter.drawLine(qtc.QPointF(0, 0), qtc.QPointF(left, 0))
        painter.drawLine(qtc.QPointF(left + wd / 2 + self.DL, 0),
                         qtc.QPointF(self.conn2Len + left + wd / 2 + self.DL, 0))
        # Step 4:
        nodeRad = 2
        stRec = qtc.QRectF(-nodeRad, -nodeRad, 2 * nodeRad, 2 * nodeRad)
        enRec = qtc.QRectF(self.length - nodeRad, -nodeRad, 2 * nodeRad, 2 * nodeRad)
        painter.drawEllipse(stRec)
        painter.drawEllipse(enRec)
        # Step 5:
        self.transformation.translate(self.stPt.x(), self.stPt.y())
        self.transformation.rotate(self.angleDeg)
        self.setTransform(self.transformation)
        # Step 6:
        # self.transformation.reset()
        # font=painter.font()
        # font.setPointSize(6)
        # painter.setFont(font)
        # text="k = {:0.1f} N/m".format(self.k)
        # fm = qtg.QFontMetrics(painter.font())
        # centerPt = (self.stPt+self.enPt)/2,0
        # painter.drawText(qtc.QPointF(-fm.width(text)/2.0,fm.height()/2.0), text)
        # if self.label is not None:
        #     font.setPointSize(12)
        #     painter.setFont(font)
        #     painter.drawText(qtc.QPointF((self.FBL.DashPotWidth / 2.0) + 10, 0), self.label)

        self.transformation.reset()
        # brPen=qtg.QPen()
        # brPen.setWidth(0)
        # painter.setPen(brPen)
        # painter.setBrush(qtc.Qt.NoBrush)
        # painter.drawRect(self.boundingRect())
class FourBarLinkage_Model():
    '''
    This is my model class for a Four Bar Linkage.
    The four bar consists of:
    1. Four bars: 0. ground link (fixed), 1. input link, 2. connecting link, and 3. output link
    2. Four pin joints: two fixed position joints on the ground link [0, 3], two mobile joints on the connecting link [1, 2]
    3. Tracer points that draw lines connecting points as the four bar linkage moves.

    To specify the four bar linkage, you need to input at minimum:
    A. x,y coordinates of the two fixed position joints
    B. the angle and length of the input link
    C. the angle and length of the output link

    From the specification of A., B., and C., the length of the connector link is calculated.

    Operation of the four-bar linkage:
        There is one degree of freedom in the motion of the four bar linkage:  the input angle.
        My strategy is to use fsolve of scipy to find the output angle with the following constraint: The lengths of all the links must remain fixed (i.e., rigid links).
    '''
    def __init__(self):
        self.GroundLink = RigidLink()
        self.InputLink = RigidLink()
        self.DragLink = RigidLink()
        self.OutputLink = RigidLink()
        self.Pivot0 = RigidPivotPoint()
        self.Pivot1 = RigidPivotPoint()
        self.Spring = LinearSpring()
        self.DashPot = DashPot()
        self.Tracer0 = Tracer()
        self.Tracer1 = Tracer()
        self.Tracer2 = Tracer()
        self.Tracer3 = Tracer()

    def setInputLength(self, L=10):
        self.InputLink.enPt.setX(self.InputLink.stPt.x() + math.cos(self.InputLink.angle) * L)
        self.InputLink.enPt.setY(self.InputLink.stPt.y() - math.sin(self.InputLink.angle) * L)
        self.InputLink.linkLength()
        self.DragLink.stPt.setX(self.InputLink.enPt.x())
        self.DragLink.stPt.setY(self.InputLink.enPt.y())

    def setOutputLength(self, L=10):
        self.OutputLink.enPt.setX(self.OutputLink.stPt.x() + math.cos(self.OutputLink.angle) * L)
        self.OutputLink.enPt.setY(self.OutputLink.stPt.y() - math.sin(self.OutputLink.angle) * L)
        self.OutputLink.linkLength()
        self.DragLink.enPt.setX(self.OutputLink.enPt.x())
        self.DragLink.enPt.setY(self.OutputLink.enPt.y())

    def moveLinkage(self, pt=qtc.QPointF(0, 0)):
        l1 = self.InputLink.length
        l2 = self.DragLink.length
        l3 = self.OutputLink.length

        x = pt.x()
        y = pt.y()
        if (x == self.InputLink.stPt.x()):
            self.angle1 = math.pi / 2 if y <= self.InputLink.stPt.y() else math.pi * 3.0 / 2.0
        else:
            self.angle1 = math.atan(-(y - self.InputLink.stPt.y()) / (x - self.InputLink.stPt.x()))
            self.angle1 += math.pi if x < self.InputLink.stPt.x() else 0
        if (self.OutputLink.enPt.x() == self.OutputLink.enPt.x()):
            self.angle2 = math.pi / 2 if self.OutputLink.enPt.y() < self.OutputLink.stPt.y() else math.pi * 3.0 / 2.0
        else:
            self.angle2 = math.atan(-(self.OutputLink.enPt.y() - self.DragLink.stPt.y()) / (
                    self.OutputLink.enPt.x() - self.OutputLink.stPt.x()))
            self.angle2 += math.pi if self.OutputLink.enPt.x() < self.OutputLink.stPt.x() else 0

        self.InputLink.enPt.setX(self.InputLink.stPt.x() + math.cos(self.angle1) * l1)
        self.InputLink.enPt.setY(self.InputLink.stPt.y() - math.sin(self.angle1) * l1)
        x1 = self.InputLink.enPt.x()
        y1 = self.InputLink.enPt.y()
        self.lTest = l2

        def fn1(angle2):
            x2 = self.OutputLink.stPt.x() + l3 * math.cos(angle2)
            y2 = self.OutputLink.stPt.y() - l3 * math.sin(angle2)
            self.lTest = math.sqrt(math.pow(x2 - x1, 2) + math.pow(y2 - y1, 2))
            return l2 - self.lTest
        # Here is where the position of coupler link is found.
        result = optimize.fsolve(fn1, [self.angle2])
        if abs(self.lTest - l2) > 0.001:
            self.angle2 = self.prevBeta
            self.angle1 = self.prevAlpha
            self.InputLink.enPt.setX(self.InputLink.stPt.x() + math.cos(self.angle1) * l1)
            self.InputLink.endPt.setY(self.InputLink.stPt.y() - math.sin(self.angle1) * l1)
        else:
            self.angle2 = result[0]
            self.prevAlpha = self.angle1
            self.prevBeta = self.angle2

        # self.InputLink.enPt.x()=scenePos.x()
        # self.InputLink.enPt.y()=scenePos.y()
        # self.InputLink.update()
        self.OutputLink.enPt.setX(self.OutputLink.stPt.x() + l3 * math.cos(self.angle2))
        self.OutputLink.enPt.setY(self.OutputLink.stPt.y() - l3 * math.sin(self.angle2))
        pt1 = dc(self.InputLink.enPt)
        pt0 = dc(self.OutputLink.enPt)
        ptMid = (pt0 + pt1) / 2
        self.Tracer1.pts.append(pt1)
        self.Tracer0.pts.append(pt0)
        self.Tracer2.pts.append(ptMid)
        self.Tracer3.pts.append(ptMid + 0.5 * (pt0 - ptMid))
        self.Spring.enPt = dc(self.Tracer3.lastPt())
        self.Spring.getForce()
        self.DashPot.enPt = dc(self.Tracer3.lastPt())
        if len(self.Tracer1.pts) >= 1000:
            self.Tracer0.pts = self.Tracer0.pts[1:]
            self.Tracer1.pts = self.Tracer1.pts[1:]
            self.Tracer2.pts = self.Tracer2.pts[1:]
            self.Tracer3.pts = self.Tracer3.pts[1:]

        self.DragLink.stPt = self.InputLink.enPt
        self.DragLink.enPt = self.OutputLink.enPt
#endregion

#region view
class FourBarLinkage_View():
    def __init__(self, gv_Main):
        self.gv_Main = gv_Main

    def setupGraphics(self):
        # create a scene object
        self.scene = qtw.QGraphicsScene()

        self.scene.setObjectName("MyScene")
        self.scene.setSceneRect(-200, -200, 400, 400)  # xLeft, yTop, Width, Height

        # set the scene for the graphics view object
        self.gv_Main.setScene(self.scene)
        # make some pens and brushes for my drawing
        self.setupPensAndBrushes()

        # assign scene object to gv_Main
        self.gv_Main.setViewportUpdateMode(qtw.QGraphicsView.FullViewportUpdate)

    def setupPensAndBrushes(self):
        # make the pens first
        # a thick green pen
        self.penThick = qtg.QPen(qtc.Qt.darkGreen)
        self.penThick.setWidth(5)
        # a medium blue pen
        self.penMed = qtg.QPen(qtc.Qt.darkBlue)
        self.penMed.setStyle(qtc.Qt.SolidLine)
        self.penMed.setWidth(2)
        # a this orange pen
        self.penLink = qtg.QPen(qtg.QColor("orange"))
        self.penLink.setWidth(1)
        # a pen for the grid lines
        self.penGridLines = qtg.QPen()
        self.penGridLines.setWidth(1)
        self.penGridLines.setColor(qtg.QColor.fromHsv(197, 144, 228, 128))

        self.penTracer = qtg.QPen(qtc.Qt.blue)
        self.penTracerIcon = qtg.QPen(qtc.Qt.black)
        # now make some brushes
        # build a brush for filling with solid red
        self.brushFill = qtg.QBrush(qtc.Qt.darkRed)
        # a brush that makes a hatch pattern
        self.brushHatch = qtg.QBrush()
        self.brushHatch.setStyle(qtc.Qt.DiagCrossPattern)
        # a brush for the background of my grid
        self.brushGrid = qtg.QBrush(qtg.QColor.fromHsv(87, 98, 245, 128))
        self.brushLink = qtg.QBrush(qtg.QColor.fromHsv(35, 255, 255, 64))
        self.brushPivot = qtg.QBrush(qtg.QColor.fromHsv(0, 0, 128, 255))

    def BuildScene(self, FBL_M):
        """
                In our four bar linkage, there is one degree of freedom:  the input angle
                Each link position is determined by working from the drive link to the output link.
                :return:
        """
        # clear out the old scene first
        self.scene.clear()

        # draw a grid
        self.drawAGrid(DeltaX=10, DeltaY=10, Height=400, Width=400, Pen=self.penGridLines, Brush=self.brushGrid)

        # Set DragLink start and end points
        FBL_M.DragLink.stPt = qtc.QPointF(-100, -60)
        FBL_M.DragLink.enPt = qtc.QPointF(100, -150)

        # Set coordinates and properties of Pivot 0
        FBL_M.Pivot0 = self.drawPivot(-100, 0, 10, 20)
        FBL_M.Pivot0.setTransformOriginPoint(qtc.QPointF(FBL_M.Pivot0.x, FBL_M.Pivot0.y))
        FBL_M.Pivot0.rotate(0)
        FBL_M.Pivot0.name = "RP 0"

        # set coordinates and properties of Pivot 1
        FBL_M.Pivot1 = self.drawPivot(60, 00, 10, 20)
        FBL_M.Pivot1.setTransformOriginPoint(qtc.QPointF(FBL_M.Pivot1.x, FBL_M.Pivot1.y))
        FBL_M.Pivot1.rotate(0)
        FBL_M.Pivot1.name = "RP 1"
        # Make the ground link
        FBL_M.GroundLink = self.drawLinkage(FBL_M.Pivot0.x, FBL_M.Pivot0.y, FBL_M.Pivot1.x, FBL_M.Pivot1.y,
                                          radius=5, pen=self.penGridLines, brush=self.brushGrid)
        # Make the input link
        FBL_M.InputLink = self.drawLinkage(FBL_M.Pivot0.x, FBL_M.Pivot0.y, FBL_M.DragLink.stPt.x(),
        # Make the coupler link
        FBL_M.DragLink.stPt.y(), 5)
        FBL_M.DragLink = self.drawLinkage(FBL_M.DragLink.stPt.x(), FBL_M.DragLink.stPt.y(),
                                             FBL_M.DragLink.enPt.x(), FBL_M.DragLink.enPt.y(), 5)
        # Make the output link
        FBL_M.OutputLink = self.drawLinkage(FBL_M.Pivot1.x, FBL_M.Pivot1.y, FBL_M.DragLink.enPt.x(),
                                               FBL_M.DragLink.enPt.y(), 5)
        FBL_M.GroundLink.name = "Frame"
        FBL_M.InputLink.name = "Input"
        FBL_M.DragLink.name = "Coupler"
        FBL_M.OutputLink.name = "Output"

        #Make some tracer points
        FBL_M.Tracer0 = Tracer(x=100, y=-150, pen=self.penTracer)
        self.scene.addItem(FBL_M.Tracer0)
        FBL_M.Tracer1 = Tracer(x=-100, y=-60, pen=self.penTracer)
        self.scene.addItem(FBL_M.Tracer1)
        FBL_M.Tracer2 = Tracer(0, 0, pen=self.penTracer)
        FBL_M.Tracer2.pts[0] = (FBL_M.Tracer0.pts[0] + FBL_M.Tracer1.pts[0]) / 2
        self.scene.addItem(FBL_M.Tracer2)
        FBL_M.Tracer3 = Tracer(0, 0, pen=self.penTracer)
        FBL_M.Tracer3.pts[0] = (FBL_M.Tracer0.pts[0] + FBL_M.Tracer2.pts[0]) / 2
        self.scene.addItem(FBL_M.Tracer3)

        # make a spring and dashpot
        FBL_M.Spring = LinearSpring(FBL_M.Pivot1.pt, FBL_M.Tracer3.pts[0], 20, 50)
        self.scene.addItem(FBL_M.Spring)
        FBL_M.DashPot = DashPot(FBL_M.Pivot1.pt, FBL_M.Tracer3.lastPt(), 10, 80)
        self.scene.addItem(FBL_M.DashPot)

    def drawAGrid(self, DeltaX=10, DeltaY=10, Height=200, Width=200, CenterX=0, CenterY=0, Pen=None, Brush=None, SubGrid=None):
        """
        This makes a grid for reference.  No snapping to grid enabled.
        :param DeltaX: grid spacing in x direction
        :param DeltaY: grid spacing in y direction
        :param Height: height of grid (y)
        :param Width: width of grid (x)
        :param CenterX: center of grid (x, in scene coords)
        :param CenterY: center of grid (y, in scene coords)
        :param Pen: pen for grid lines
        :param Brush: brush for background
        :param SubGrid: subdivide the grid (not currently working)
        :return: nothing
        """
        height = self.scene.sceneRect().coilsLength() if Height is None else Height
        width = self.scene.sceneRect().coilsWidth() if Width is None else Width
        left = self.scene.sceneRect().left() if CenterX is None else (CenterX - width / 2.0)
        right = self.scene.sceneRect().right() if CenterX is None else (CenterX + width / 2.0)
        top = self.scene.sceneRect().top() if CenterY is None else (CenterY - height / 2.0)
        bottom = self.scene.sceneRect().bottom() if CenterY is None else (CenterY + height / 2.0)
        Dx = DeltaX
        Dy = DeltaY
        pen = qtg.QPen() if Pen is None else Pen

        # make the background rectangle first
        if Brush is not None:
            rect = self.drawARectangle(left, top, width, height)
            rect.setBrush(Brush)
            rect.setPen(pen)

        # draw the vertical grid lines
        x = left
        while x <= right:
            lVert = self.drawALine(x, top, x, bottom)
            lVert.setPen(pen)
            x += Dx
        # draw the horizontal grid lines
        y = top
        while y <= bottom:
            lHor = self.drawALine(left, y, right, y)
            lHor.setPen(pen)
            y += Dy

    def drawARectangle(self, leftX, topY, widthX, heightY, pen=None, brush=None):

        rect = qtw.QGraphicsRectItem(leftX, topY, widthX, heightY)
        if brush is not None:
            rect.setBrush(brush)
        if pen is not None:
            rect.setPen(pen)

        self.scene.addItem(rect)
        return rect

    def drawALine(self, stX, stY, enX, enY, pen=None):
        if pen is None: pen = self.penMed
        line = qtw.QGraphicsLineItem(stX, stY, enX, enY)
        line.setPen(pen)
        self.scene.addItem(line)
        return line

    def polarToRect(self, centerX, centerY, radius, angleDeg=0):
        angleRad = angleDeg * 2.0 * math.pi / 360.0
        return centerX + radius * math.cos(angleRad), centerY + radius * math.sin(angleRad)

    def drawACircle(self, centerX, centerY, Radius, angle=0, brush=None, pen=None):
        ellipse = qtw.QGraphicsEllipseItem(centerX - Radius, centerY - Radius, 2 * Radius, 2 * Radius)
        if pen is not None:
            ellipse.setPen(pen)
        if brush is not None:
            ellipse.setBrush(brush)
        self.scene.addItem(ellipse)
        return ellipse

    def drawASquare(self, centerX, centerY, Size, brush=None, pen=None):
        sqr = qtw.QGraphicsRectItem(centerX - Size / 2.0, centerY - Size / 2.0, Size, Size)
        if pen is not None:
            sqr.setPen(pen)
        if brush is not None:
            sqr.setBrush(brush)
        self.scene.addItem(sqr)
        return sqr

    def drawATriangle(self, centerX, centerY, Radius, angleDeg=0, brush=None, pen=None):
        pts = []

        x, y = self.polarToRect(centerX, centerY, Radius, 0 + angleDeg)
        pts.append(qtc.QPointF(x, y))
        x, y = self.polarToRect(centerX, centerY, Radius, 120 + angleDeg)
        pts.append(qtc.QPointF(x, y))
        x, y = self.polarToRect(centerX, centerY, Radius, 240 + angleDeg)
        pts.append(qtc.QPointF(x, y))
        x, y = self.polarToRect(centerX, centerY, Radius, 0 + angleDeg)
        pts.append(qtc.QPointF(x, y))

        pg = qtg.QPolygonF(pts)
        PG = qtw.QGraphicsPolygonItem(pg)
        if pen is not None:
            PG.setPen(pen)
        if brush is not None:
            PG.setBrush(brush)
        self.scene.addItem(PG)
        return PG

    def drawAnArrow(self, startX, startY, endX, endY, pen=None, brush=None):
        line = qtw.QGraphicsLineItem(startX, startY, endX, endY)
        p = qtg.QPen() if pen is None else pen
        line.setPen(pen)
        angleDeg = 180.0 / math.pi * math.atan((endY - startY) / (endX - startX))
        self.scene.addItem(line)
        self.drawATriangle(endX, endY, 5, angleDeg=angleDeg, pen=pen, brush=brush)

    def drawRigidSurface(self, centerX, centerY, Width=10, Height=3, pen=None, brush=None):
        """
        This should draw a figure that has a rectangle with the top border an solid line and the rectangle filled
        with a hatch pattern
        :param centerX:
        :param centerY:
        :param Width:
        :param Height:
        :return:
        """
        top = centerY
        left = centerX - Width / 2
        right = centerX + Width / 2
        self.drawALine(centerX - Width / 2, centerY, centerX + Width / 2, centerY, pen=pen)
        penOutline = qtg.QPen(qtc.Qt.NoPen)

        self.drawARectangle(left, top, Width, Height, pen=penOutline, brush=brush)

    def drawLinkage(self, stX, stY, enX, enY, radius=10, pen=None, brush=None):
        if pen is None: pen = self.penLink
        if brush is None: brush = self.brushLink
        lin1 = RigidLink(stX, stY, enX, enY, radius, pen=pen, brush=brush)
        self.scene.addItem(lin1)
        return lin1

    def drawPivot(self, x, y, ht, wd):
        pivot = RigidPivotPoint(x, y, ht, wd, brush=self.brushPivot)
        self.scene.addItem(pivot)
        return pivot

    def pickAColor(self):
        cdb = qtw.QColorDialog(self)
        c = cdb.getColor()
        hsv = c.getHsv()
        self.pushButton.setText(str(hsv))
        self.penGridLines.setColor(qtg.QColor.fromHsv(hsv[0], hsv[1], hsv[2], hsv[3]))
        self.buildScene()
        pass

    def setZoom(self):
        self.gv_Main.resetTransform()
        self.gv_Main.scale(self.spnd_Zoom.value(), self.spnd_Zoom.value())
#endregion

#region controller
class FourBarLinkage_Controller():
    def __init__(self, widgets):
        #widgets = [self.gv_Main, self.nud_InputAngle, self.lbl_OutputAngle_Val, self.nud_Link1Length, self.nud_Link3Length, self.spnd_Zoom]
        self.widgets=widgets
        self.gv_Main, self.nud_InputAngle, self.lbl_OutputAngle_Val, self.nud_Link1Length, self.nud_Link3Length, self.spnd_Zoom = widgets

        self.FBL_M = FourBarLinkage_Model()
        self.FBL_V = FourBarLinkage_View(self.gv_Main)

    def setupGraphics(self):
        self.FBL_V.setupGraphics()

    def buildScene(self):
        self.FBL_V.BuildScene(self.FBL_M)

    def setInputLinkLength(self):
        self.FBL_M.setInputLength(self.nud_Link1Length.value())
        self.FBL_M.moveLinkage(self.FBL_M.InputLink.enPt)
        self.FBL_V.scene.update()

    def setOutputLinkLength(self):
        self.FBL_M.setOutputLength(self.nud_Link3Length.value())
        self.FBL_M.moveLinkage(self.FBL_M.InputLink.enPt)
        self.FBL_V.scene.update()

    def moveLinkage(self, scenePos):
        self.FBL_M.moveLinkage(scenePos)
        self.FBL_V.scene.update()
        self.nud_InputAngle.setValue(self.FBL_M.InputLink.AngleDeg())
        self.lbl_OutputAngle_Val.setText("{:0.2f}".format(self.FBL_M.OutputLink.AngleDeg()))
#endregion
#endregion

if __name__ ==  "__main__":
    pass