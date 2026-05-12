from pupil_apriltags import Detector
import cv2
import numpy as np
import math

def rotation_matrix_to_euler_angles(R):
    """
    Converts rotation matrix to roll, pitch, yaw in degrees.
    Convention may need adjustment depending on your coordinate frame.
    """
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)

    singular = sy < 1e-6

    if not singular:
        roll = math.atan2(R[2, 1], R[2, 2])
        pitch = math.atan2(-R[2, 0], sy)
        yaw = math.atan2(R[1, 0], R[0, 0])
    else:
        roll = math.atan2(-R[1, 2], R[1, 1])
        pitch = math.atan2(-R[2, 0], sy)
        yaw = 0

    return np.degrees([roll, pitch, yaw])


TAG_SIZE = 0.05  # meters. Example: 5 cm tag. CHANGE THIS.

at_detector = Detector(
    families="tag25h9",
    nthreads=1,
    quad_decimate=1.0,
    quad_sigma=0.0,
    refine_edges=1,
    decode_sharpening=0.25,
    debug=0
)

cap = cv2.VideoCapture(0)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("Camera did not open")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Could not read frame")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape

    # Rough camera parameters.
    # Better: use real camera calibration.
    fx = w
    fy = w
    cx = w / 2
    cy = h / 2

    camera_params = [799.3907361857031,
    794.2843064465196,
    399.03967921864864,
    273.1926221127301]

    detections = at_detector.detect(
        gray,
        estimate_tag_pose=True,
        camera_params=camera_params,
        tag_size=TAG_SIZE
    )

    for tag in detections:
        corners = tag.corners.astype(int)

        for i in range(4):
            p1 = tuple(corners[i])
            p2 = tuple(corners[(i + 1) % 4])
            cv2.line(frame, p1, p2, (0, 255, 0), 2)

        center = tuple(tag.center.astype(int))
        cv2.circle(frame, center, 5, (0, 0, 255), -1)

        # Translation vector: position of tag relative to camera
        t = tag.pose_t.flatten()
        x, y, z = t

        distance = np.linalg.norm(t)

        # Bearing angles relative to camera direction
        horizontal_angle = math.degrees(math.atan2(x, z))
        vertical_angle = math.degrees(math.atan2(y, z))

        # Rotation matrix: orientation of tag
        R = tag.pose_R
        roll, pitch, yaw = rotation_matrix_to_euler_angles(R)

        text_lines = [
            f"ID: {tag.tag_id}",
            f"Dist: {distance:.2f} m",
            f"Z: {z:.2f} m",
            f"X angle: {horizontal_angle:.1f} deg",
            f"Y angle: {vertical_angle:.1f} deg",
            f"Roll: {roll:.1f}",
            f"Pitch: {pitch:.1f}",
            f"Yaw: {yaw:.1f}",
        ]

        x_text, y_text = center

        for idx, line in enumerate(text_lines):
            cv2.putText(
                frame,
                line,
                (x_text, y_text + 25 * idx),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 0, 0),
                2
            )

        print(
            f"ID={tag.tag_id} | "
            f"distance={distance:.3f}m | "
            f"x={x:.3f}, y={y:.3f}, z={z:.3f} | "
            f"horizontal={horizontal_angle:.2f} deg | "
            f"vertical={vertical_angle:.2f} deg | "
            f"roll={roll:.2f}, pitch={pitch:.2f}, yaw={yaw:.2f}"
        )

    cv2.imshow("AprilTag Pose Estimation", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()