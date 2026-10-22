import json
import time
from pathlib import Path

import cv2

CAMERA = 1
THRESHOLD = 200
MIN_AREA = 30

# Plate box and threshold set in the window are saved here, next to this file.
SETTINGS_FILE = Path(__file__).with_name("settings.json")

PLATE_LEFT = 120
PLATE_RIGHT = 520
PLATE_TOP = 40
PLATE_BOTTOM = 440

# Real size of the plate inside the box, in mm. Not final yet: measure it with a
# ruler once the plate is built, or every mm value (and the PID gains) is off.
PLATE_W_MM = 300
PLATE_H_MM = 300


def make_mask(frame, threshold):
    """Black/white picture of the plate area. White = bright enough to be the ball."""
    # A picture in OpenCV is a grid of pixels: frame[row, column], row = y, column = x.
    # Slicing [top:bottom, left:right] cuts out only the plate, so things outside it are ignored.
    plate = frame[PLATE_TOP:PLATE_BOTTOM, PLATE_LEFT:PLATE_RIGHT]

    # cvtColor: change the colour format. The camera gives BGR (Blue, Green, Red, 3 numbers
    # per pixel). GRAY has 1 number per pixel: 0 = black, 255 = white. We only need brightness.
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    # GaussianBlur: soften the picture a little. Each pixel becomes the average of its
    # 5x5 neighbours, so random noise dots disappear. 0 = let OpenCV pick the blur strength.
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # threshold: every pixel brighter than `threshold` becomes 255 (white), the rest 0 (black).
    # THRESH_BINARY = only two values, white or black. It returns (used threshold, picture);
    # we only need the picture, so the first value goes into `_`.
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return mask


def findBall(mask):
    """Return the ball centre (x_px, y_px) in the full picture, or None if there is no ball."""
    # findContours: find the outline of every white blob in the mask.
    #   RETR_EXTERNAL       = only outer outlines (ignore holes inside a blob)
    #   CHAIN_APPROX_SIMPLE = store outlines with fewer points (saves memory)
    # It returns (list of outlines, hierarchy); we don't need the hierarchy.
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return None

    # contourArea: how many pixels are inside an outline. The biggest blob is the ball.
    ball = max(contours, key=cv2.contourArea)
    if cv2.contourArea(ball) < MIN_AREA:
        return None

    # moments: sums over the blob's pixels.
    #   m00 = area, m10 = sum of all x, m01 = sum of all y
    # So sum / area = average position = the centre of the ball.
    m = cv2.moments(ball)
    x_px = m["m10"] / m["m00"] + PLATE_LEFT  # + offset because the mask is cut to the plate
    y_px = m["m01"] / m["m00"] + PLATE_TOP
    return x_px, y_px


def findBallMm(frame):
    """One camera picture -> ball position (x_mm, y_mm), or None when the ball is not visible.

    This is the function datalog.py calls once per frame.
    """
    mask = make_mask(frame, THRESHOLD)
    ball = findBall(mask)
    if ball is None:
        return None
    return toMm(ball[0], ball[1])


def toMm(x_px, y_px):
    """Pixels -> mm. (0, 0) = plate centre, x goes right, y goes up."""
    # ponytail: straight-line scaling, assumes the camera looks straight down.
    # If the camera is tilted, switch to cv2.getPerspectiveTransform with the 4 corners.
    center_x = (PLATE_LEFT + PLATE_RIGHT) / 2
    center_y = (PLATE_TOP + PLATE_BOTTOM) / 2
    x_mm = (x_px - center_x) * PLATE_W_MM / (PLATE_RIGHT - PLATE_LEFT)
    y_mm = (center_y - y_px) * PLATE_H_MM / (PLATE_BOTTOM - PLATE_TOP)  # picture y goes DOWN, so flip it
    return x_mm, y_mm


def load_settings():
    """Read the saved plate box and threshold, if they were saved before."""
    # `global` lets this function change the settings at the top of the file.
    global PLATE_LEFT, PLATE_RIGHT, PLATE_TOP, PLATE_BOTTOM, THRESHOLD
    if not SETTINGS_FILE.exists():
        return
    s = json.loads(SETTINGS_FILE.read_text())
    PLATE_LEFT, PLATE_RIGHT = s["left"], s["right"]
    PLATE_TOP, PLATE_BOTTOM = s["top"], s["bottom"]
    THRESHOLD = s["threshold"]


def save_settings(threshold):
    s = {"left": PLATE_LEFT, "right": PLATE_RIGHT, "top": PLATE_TOP, "bottom": PLATE_BOTTOM,
         "threshold": threshold}
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    print("saved", SETTINGS_FILE)


def openCamera():
    """Open the webcam and ask for 640x480."""
    cam = cv2.VideoCapture(CAMERA)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # BUFFERSIZE 1: keep only 1 waiting picture, so we always get the newest one (less delay).
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cam


def select_plate(frame):
    """Let the user drag a box over the plate with the mouse."""
    global PLATE_LEFT, PLATE_RIGHT, PLATE_TOP, PLATE_BOTTOM
    # selectROI: OpenCV's built-in "drag a rectangle" tool. Drag with the mouse, then press
    # Enter or Space to accept (c = cancel). Returns (x, y, width, height) of the box.
    x, y, w, h = [int(v) for v in cv2.selectROI("camera", frame, showCrosshair=False)]
    if w == 0 or h == 0:  # cancelled, keep the old box
        return
    PLATE_LEFT, PLATE_TOP = x, y
    PLATE_RIGHT, PLATE_BOTTOM = x + w, y + h


def main():
    load_settings()

    # VideoCapture: open the webcam with this number, 640x480 pixels.
    cam = openCamera()

    # namedWindow: create an empty window with this name (imshow fills it later).
    cv2.namedWindow("camera")
    cv2.namedWindow("mask")
    # createTrackbar: a slider named "threshold" in the "mask" window, start value THRESHOLD,
    # max 255. The last argument is a function to run when it moves; we read it ourselves
    # in the loop instead, so it does nothing.
    cv2.createTrackbar("threshold", "mask", THRESHOLD, 255, lambda value: None)

    last_time = time.time()
    while True:
        # read: grab one picture. ok = False if the camera failed.
        ok, frame = cam.read()
        if not ok:
            print("Cannot read the camera. Check CAMERA number (and camera permission on Mac).")
            break

        # getTrackbarPos: current value of the slider.
        threshold = cv2.getTrackbarPos("threshold", "mask")
        mask = make_mask(frame, threshold)
        ball = findBall(mask)

        now = time.time()
        fps = 1 / (now - last_time)
        last_time = now

        # rectangle: draw a box from (left, top) to (right, bottom). Colour is (B, G, R), so
        # (255, 0, 0) = blue. Last number = line thickness in pixels.
        cv2.rectangle(frame, (PLATE_LEFT, PLATE_TOP), (PLATE_RIGHT, PLATE_BOTTOM), (255, 0, 0), 2)

        if ball is None:
            text = "no ball"
        else:
            x_mm, y_mm = toMm(ball[0], ball[1])
            text = f"x={x_mm:6.1f} mm  y={y_mm:6.1f} mm"
            # circle: draw a circle at the ball centre (must be whole numbers), radius 15,
            # green (0, 255, 0), thickness 2.
            cv2.circle(frame, (int(ball[0]), int(ball[1])), 15, (0, 255, 0), 2)

        print(text)
        # putText: write text on the picture at (10, 25) = 10 px from the left, 25 px from the
        # top. 0.6 = font size, green, thickness 2.
        cv2.putText(frame, f"{text}  {fps:4.1f} fps", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, "p = set plate box   q = save and quit", (10, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        # imshow: show a picture in a window.
        cv2.imshow("camera", frame)
        cv2.imshow("mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("p"):
            ok, clean = cam.read()  # fresh picture without our drawings on it
            if ok:
                select_plate(clean)
        if key == ord("q"):
            save_settings(threshold)
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
