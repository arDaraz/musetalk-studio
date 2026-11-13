import cv2
import numpy as np

FACE_SIZE = 256
SMOOTHING_KERNEL = (25, 25)
STILL_BELOW = 10
MOVING_ABOVE = 25
NEIGHBOR_FRAMES = 2


def as_float(face):
    return np.asarray(face, dtype=np.float32)


def smooth(image):
    return cv2.GaussianBlur(image, SMOOTHING_KERNEL, 0)


def rest_face(faces, photo_face):
    lower_half = slice(FACE_SIZE // 2, None)
    target = as_float(cv2.resize(photo_face, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA))
    distances = [np.abs(as_float(face)[lower_half] - target[lower_half]).mean() for face in faces]
    return as_float(faces[int(np.argmin(distances))])


def motion_map(face, smooth_rest):
    change = np.abs(smooth(as_float(face)) - smooth_rest).max(axis=2)
    moving = np.clip((change - STILL_BELOW) / (MOVING_ABOVE - STILL_BELOW), 0, 1)
    # One byte per pixel keeps a long video inside the container memory limit.
    return (moving * 255).astype(np.uint8)


def keep_photo_detail(generated_faces, photo_face):
    """Yield each generated face resized to photo_face.

    Still pixels show the photo detail. Inputs are BGR crops of the repainted face.
    """
    if not len(generated_faces):
        return
    height, width = photo_face.shape[:2]
    rest = rest_face(generated_faces, photo_face)
    lost_detail = as_float(photo_face) - cv2.resize(rest, (width, height))
    smooth_rest = smooth(rest)
    motion = [motion_map(face, smooth_rest) for face in generated_faces]
    for index, face in enumerate(generated_faces):
        # A pixel that moves in a neighboring frame keeps the generated value. This prevents flicker.
        nearby = motion[max(0, index - NEIGHBOR_FRAMES):index + NEIGHBOR_FRAMES + 1]
        moving = cv2.resize(smooth(np.max(nearby, axis=0) / np.float32(255)), (width, height))[..., None]
        restored = cv2.resize(as_float(face), (width, height)) + (1 - moving) * lost_detail
        yield np.clip(restored, 0, 255).astype(np.uint8)
