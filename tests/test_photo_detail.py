import unittest

import numpy as np

from photo_detail import keep_photo_detail


def textured_photo(height=320, width=220):
    rng = np.random.default_rng(7)
    return rng.integers(60, 200, size=(height, width, 3), dtype=np.uint8)


def soft_face(value=128):
    return np.full((256, 256, 3), value, dtype=np.uint8)


def open_mouth_face():
    face = soft_face()
    face[150:210, 90:170] = 20
    return face


class PhotoDetailTests(unittest.TestCase):
    def test_still_face_shows_the_photo(self):
        photo = textured_photo()
        frames = list(keep_photo_detail([soft_face(), soft_face()], photo))
        self.assertEqual(len(frames), 2)
        for frame in frames:
            np.testing.assert_array_equal(frame, photo)

    def test_moving_mouth_keeps_generated_pixels_and_far_detail(self):
        photo = textured_photo()
        closed, moved = list(keep_photo_detail([soft_face(), open_mouth_face()], photo))
        np.testing.assert_array_equal(closed[:120], photo[:120])
        np.testing.assert_array_equal(moved[:120], photo[:120])
        mouth = moved[205:245, 95:125].astype(int)
        self.assertLess(np.abs(mouth - 20).max(), 3)

    def test_motion_in_a_neighbor_frame_keeps_generated_pixels(self):
        closed = list(keep_photo_detail([soft_face(), open_mouth_face()], textured_photo()))[0]
        mouth = closed[205:245, 95:125].astype(int)
        self.assertLess(np.abs(mouth - 128).max(), 3)

    def test_no_generated_faces_yields_nothing(self):
        self.assertEqual(list(keep_photo_detail([], textured_photo())), [])


if __name__ == '__main__':
    unittest.main()
