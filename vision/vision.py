import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

CAMERA = 1
THRESHOLD = 200
MIN_AREA = 30

# Plate box and threshold set in the window are saved here, next to this file.
SETTINGS_FILE = Path(__file__).with_name("settings.json")

PLATE_LEFT = 120
PLATE_RIGHT = 520
PLATE_TOP = 40
PLATE_BOTTOM = 440

# Real size of the plate in mm (250 x 250 mm). Measure it with a ruler once the
# plate is built, or every mm value (and the PID gains) is off.
PLATE_W_MM = 250
PLATE_H_MM = 250

# Pixel corners of the plate, clockwise from top-left. The default is the box
# above; selectPlate() replaces it when you drag a new box.
PLATE_CORNERS = [
    (PLATE_LEFT, PLATE_TOP),
    (PLATE_RIGHT, PLATE_TOP),
    (PLATE_RIGHT, PLATE_BOTTOM),
    (PLATE_LEFT, PLATE_BOTTOM),
]

# Cached pixel -> mm matrix. Built once when the corners or plate size change,
# not on every camera frame.
PERSPECTIVE = None


def plateBox():
    """Bounding box of the plate corners: left, top, right, bottom (pixels)."""
    xs = [corner[0] for corner in PLATE_CORNERS]
    ys = [corner[1] for corner in PLATE_CORNERS]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def updatePerspective():
    """Rebuild the pixel -> mm matrix after the corners or plate size change."""
    global PERSPECTIVE
    source = np.float32(PLATE_CORNERS)
    # (0, 0) = plate centre, x right, y up. Picture y goes down, so flip it.
    target = np.float32([
        [-PLATE_W_MM / 2, PLATE_H_MM / 2],
        [PLATE_W_MM / 2, PLATE_H_MM / 2],
        [PLATE_W_MM / 2, -PLATE_H_MM / 2],
        [-PLATE_W_MM / 2, -PLATE_H_MM / 2],
    ])
    PERSPECTIVE = cv2.getPerspectiveTransform(source, target)


def makeMask(frame, threshold):
    """Black/white picture of the plate area. White = bright enough to be the ball."""
    left, top, right, bottom = plateBox()
    plate = frame[top:bottom, left:right]
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return mask


def findBall(mask):
    """Return the ball centre (x_px, y_px) in the full picture, or None."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return None

    ball = max(contours, key=cv2.contourArea)
    if cv2.contourArea(ball) < MIN_AREA:
        return None

    moments = cv2.moments(ball)
    left, top, _, _ = plateBox()  # the mask is cut to the plate
    x_px = moments["m10"] / moments["m00"] + left
    y_px = moments["m01"] / moments["m00"] + top
    return x_px, y_px


def toMm(x_px, y_px):
    """Pixels -> mm. (0, 0) = plate centre, x goes right, y goes up."""
    if PERSPECTIVE is None:
        updatePerspective()
    point = np.array([[[x_px, y_px]]], dtype=np.float32)
    x_mm, y_mm = cv2.perspectiveTransform(point, PERSPECTIVE)[0][0]
    return float(x_mm), float(y_mm)


def findBallMm(frame):
    """One camera picture -> ball position (x_mm, y_mm), or None when hidden.

    This is the function datalog.py calls once per frame. It also draws the
    plate outline (blue) and the ball it found (green) on the picture.
    """
    mask = makeMask(frame, THRESHOLD)
    ball = findBall(mask)
    cv2.polylines(frame, [np.int32(PLATE_CORNERS)], True, (255, 0, 0), 2)
    if ball is None:
        return None
    cv2.circle(frame, (int(ball[0]), int(ball[1])), 15, (0, 255, 0), 2)
    return toMm(ball[0], ball[1])


def loadSettings():
    """Read the saved plate box, threshold and corners, if they were saved before."""
    global PLATE_LEFT, PLATE_RIGHT, PLATE_TOP, PLATE_BOTTOM, THRESHOLD, PLATE_CORNERS
    if SETTINGS_FILE.exists():
        saved = json.loads(SETTINGS_FILE.read_text())
        PLATE_LEFT, PLATE_RIGHT = saved["left"], saved["right"]
        PLATE_TOP, PLATE_BOTTOM = saved["top"], saved["bottom"]
        THRESHOLD = saved["threshold"]
        if "corners" in saved:
            PLATE_CORNERS = [tuple(point) for point in saved["corners"]]
        else:
            # Older settings files only saved the box, so use its four corners.
            PLATE_CORNERS = [
                (PLATE_LEFT, PLATE_TOP),
                (PLATE_RIGHT, PLATE_TOP),
                (PLATE_RIGHT, PLATE_BOTTOM),
                (PLATE_LEFT, PLATE_BOTTOM),
            ]
    updatePerspective()


def saveSettings(threshold):
    """Write the current box, corners and threshold, then refresh the matrix."""
    saved = {
        "left": PLATE_LEFT,
        "right": PLATE_RIGHT,
        "top": PLATE_TOP,
        "bottom": PLATE_BOTTOM,
        "threshold": threshold,
        "corners": [[x, y] for x, y in PLATE_CORNERS],
    }
    SETTINGS_FILE.write_text(json.dumps(saved, indent=2))
    updatePerspective()
    print("saved", SETTINGS_FILE)


def openCamera():
    """Open the webcam and ask for 640x480."""
    # Windows: use DirectShow. The default (MSMF) keeps up to 3 old pictures
    # waiting, which adds delay; DirectShow keeps at most 1.
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    camera = cv2.VideoCapture(CAMERA, backend)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # Keep only 1 waiting picture, so we always get the newest one (less delay).
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return camera


def selectPlate(frame):
    """Let the user drag a box over the plate with the mouse."""
    global PLATE_LEFT, PLATE_RIGHT, PLATE_TOP, PLATE_BOTTOM, PLATE_CORNERS
    x, y, w, h = [int(value) for value in cv2.selectROI("camera", frame, showCrosshair=False)]
    if w == 0 or h == 0:  # cancelled, keep the old box
        return
    PLATE_LEFT, PLATE_TOP = x, y
    PLATE_RIGHT, PLATE_BOTTOM = x + w, y + h
    PLATE_CORNERS = [
        (PLATE_LEFT, PLATE_TOP),
        (PLATE_RIGHT, PLATE_TOP),
        (PLATE_RIGHT, PLATE_BOTTOM),
        (PLATE_LEFT, PLATE_BOTTOM),
    ]
    updatePerspective()


def main():
    loadSettings()
    camera = openCamera()

    cv2.namedWindow("camera")
    cv2.namedWindow("mask")
    cv2.createTrackbar("threshold", "mask", THRESHOLD, 255, lambda value: None)

    lastTime = time.time()
    while True:
        ok, frame = camera.read()
        if not ok:
            print("Cannot read the camera. Check the CAMERA number and the Windows camera permission.")
            break

        threshold = cv2.getTrackbarPos("threshold", "mask")
        mask = makeMask(frame, threshold)
        ball = findBall(mask)

        now = time.time()
        fps = 1 / (now - lastTime)
        lastTime = now

        cv2.polylines(frame, [np.int32(PLATE_CORNERS)], True, (255, 0, 0), 2)
        if ball is None:
            text = "no ball"
        else:
            x_mm, y_mm = toMm(ball[0], ball[1])
            text = f"x={x_mm:6.1f} mm  y={y_mm:6.1f} mm"
            cv2.circle(frame, (int(ball[0]), int(ball[1])), 15, (0, 255, 0), 2)

        print(text)
        cv2.putText(frame, f"{text}  {fps:4.1f} fps", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, "p = set plate box   q = save and quit", (10, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.imshow("camera", frame)
        cv2.imshow("mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("p"):
            ok, clean = camera.read()  # fresh picture without our drawings on it
            if ok:
                selectPlate(clean)
                saveSettings(threshold)  # save now, so the next datalog.py uses it
        if key == ord("q"):
            saveSettings(threshold)
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
