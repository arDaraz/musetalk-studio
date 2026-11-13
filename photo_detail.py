from collections import deque

import cv2
import numpy as np

FACE_SIZE = 256
SMOOTHING_KERNEL = (9, 9)
IGNORED_MOTION = 0.75
SAME_COLOR_BELOW = 4
NEW_COLOR_ABOVE = 10


def as_float(image):
    return np.asarray(image, dtype=np.float32)


def as_image(values):
    return np.clip(values, 0, 255).astype(np.uint8)


def smooth(image):
    return cv2.GaussianBlur(image, SMOOTHING_KERNEL, 0)


def gray(face):
    return cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)


def color(face):
    # The color excludes brightness because the model changes the brightness of a beard that only moves.
    return as_float(cv2.cvtColor(face, cv2.COLOR_BGR2LAB))[..., 1:]


def rest_face(faces, photo_face):
    lower_half = slice(FACE_SIZE // 2, None)
    target = as_float(cv2.resize(photo_face, (FACE_SIZE, FACE_SIZE), interpolation=cv2.INTER_AREA))
    distances = [np.abs(as_float(face)[lower_half] - target[lower_half]).mean() for face in faces]
    return faces[int(np.argmin(distances))]


def with_neighbors(items):
    """Yield each item with the item before it and the item after it. An end item is its own missing neighbor."""
    window = deque(maxlen=3)
    for item in items:
        if not window:
            window.append(item)
        window.append(item)
        if len(window) == 3:
            yield tuple(window)
    if window:
        window.append(window[-1])
        yield tuple(window)


def steady(motions):
    # The model shifts each frame by a part of a pixel. Sharp detail that follows that shift shimmers.
    motion = np.mean(motions, axis=0)
    distance = np.linalg.norm(motion, axis=2, keepdims=True)
    return motion * np.clip(distance / IGNORED_MOTION - 1, 0, 1)


def moved(image, motion):
    height, width = image.shape[:2]
    scaled = cv2.resize(motion, (width, height)) * np.float32([width / FACE_SIZE, height / FACE_SIZE])
    columns, rows = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    return cv2.remap(image, columns + scaled[..., 0], rows + scaled[..., 1], cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_REPLICATE)


def new_content(face, moved_rest):
    difference = smooth(np.abs(color(face) - color(as_image(moved_rest))).sum(axis=2))
    return smooth(np.clip((difference - SAME_COLOR_BELOW) / (NEW_COLOR_ABOVE - SAME_COLOR_BELOW), 0, 1))


def keep_photo_detail(generated_faces, photo_face):
    """Yield each generated face at the photo_face size, with the photo detail moved onto the face. Inputs are 8-bit BGR."""
    if not len(generated_faces):
        return
    height, width = photo_face.shape[:2]
    rest = rest_face(generated_faces, photo_face)
    rest_pixels = as_float(rest)
    lost_detail = as_float(photo_face) - cv2.resize(rest_pixels, (width, height))
    rest_gray = gray(rest)
    motion_finder = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    motions = (motion_finder.calc(gray(face), rest_gray, None) for face in generated_faces)
    for face, nearby_motions in zip(generated_faces, with_neighbors(motions)):
        motion = steady(nearby_motions)
        generated_only = cv2.resize(new_content(face, moved(rest_pixels, motion)), (width, height))[..., None]
        restored = cv2.resize(as_float(face), (width, height)) + (1 - generated_only) * moved(lost_detail, motion)
        yield as_image(restored)
