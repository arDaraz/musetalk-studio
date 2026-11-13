import unittest

import cv2
import numpy as np

from mouth_restore import ALIGNED_POINTS, alignment, put_mouth_back, with_restored_detail


def sharpness(image):
    return cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_32F).var()


def detailed_face(size=512):
    rng = np.random.default_rng(3)
    shapes = cv2.GaussianBlur(rng.uniform(0, 255, (size, size, 3)).astype(np.float32), (0, 0), 20)
    shapes = (shapes - shapes.min()) / (shapes.max() - shapes.min()) * 120 + 60
    return (shapes + rng.uniform(-25, 25, (size, size, 3))).astype(np.uint8)


class MouthRestoreTests(unittest.TestCase):
    def test_alignment_moves_the_face_points_to_the_aligned_position(self):
        in_photo = ALIGNED_POINTS * 1.6 + (40, 25)
        landmarks = np.zeros((68, 2), dtype=np.float32)
        landmarks[36:42], landmarks[42:48] = in_photo[0], in_photo[1]
        landmarks[30], landmarks[48], landmarks[54] = in_photo[2], in_photo[3], in_photo[4]
        moved = cv2.transform(in_photo[None], alignment(landmarks))[0]
        np.testing.assert_allclose(moved, ALIGNED_POINTS, atol=0.01)

    def test_restored_detail_sharpens_a_face_with_the_same_shape(self):
        restored = detailed_face()
        aligned = cv2.GaussianBlur(restored, (0, 0), 3)
        result = with_restored_detail(aligned, restored.astype(np.float32))
        self.assertGreater(sharpness(result), 5 * sharpness(aligned))

    def test_restored_detail_keeps_a_mouth_that_the_restoration_closed(self):
        restored = detailed_face()
        aligned = cv2.GaussianBlur(restored, (0, 0), 3)
        aligned[340:400, 200:320] = 15
        result = with_restored_detail(aligned, restored.astype(np.float32))
        np.testing.assert_array_equal(result[355:385, 215:305], aligned[355:385, 215:305])

    def test_only_the_mouth_changes_in_the_frame(self):
        frame = np.full((600, 800, 3), 90, dtype=np.uint8)
        sharp_face = np.full((512, 512, 3), 200, dtype=np.uint8)
        mouth = np.zeros((512, 512), dtype=bool)
        mouth[350:390, 210:300] = True
        to_aligned = np.float32([[1, 0, -100], [0, 1, -50]])
        result = put_mouth_back(frame, sharp_face, mouth, to_aligned)
        np.testing.assert_array_equal(result[410:430, 320:390], 200)
        changed = np.argwhere((result != frame).any(axis=2))
        self.assertGreaterEqual(changed[:, 0].min(), 390)
        self.assertLessEqual(changed[:, 0].max(), 450)
        self.assertGreaterEqual(changed[:, 1].min(), 300)
        self.assertLessEqual(changed[:, 1].max(), 410)


if __name__ == '__main__':
    unittest.main()
