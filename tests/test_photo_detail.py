import unittest

import cv2
import numpy as np

from photo_detail import keep_photo_detail, with_neighbors

FACE_SHIFT = 6


def detailed_photo(size=256):
    rng = np.random.default_rng(7)
    shapes = cv2.GaussianBlur(rng.uniform(0, 255, (size, size, 3)).astype(np.float32), (0, 0), 6)
    shapes = (shapes - shapes.min()) / (shapes.max() - shapes.min()) * 120 + 60
    grain = rng.uniform(-25, 25, (size, size, 3)).astype(np.float32)
    return (shapes + grain).astype(np.uint8)


def soft(face):
    return cv2.GaussianBlur(face, (0, 0), 3)


def lowered(face):
    return np.roll(face, FACE_SHIFT, axis=0)


def error(frame, expected):
    middle = slice(40, -40)
    return np.abs(frame[middle, middle].astype(int) - expected[middle, middle]).mean()


class PhotoDetailTests(unittest.TestCase):
    def test_still_face_shows_the_photo(self):
        photo = detailed_photo()
        frames = list(keep_photo_detail([soft(photo), soft(photo)], photo))
        self.assertEqual(len(frames), 2)
        for frame in frames:
            np.testing.assert_array_equal(frame, photo)

    def test_photo_detail_moves_with_the_face(self):
        photo = detailed_photo()
        rest = soft(photo)
        frames = list(keep_photo_detail([rest, lowered(rest), lowered(rest), lowered(rest)], photo))
        self.assertLess(error(frames[2], lowered(photo)), 0.5 * error(frames[2], photo))
        self.assertLess(error(frames[2], lowered(photo)), 0.5 * error(lowered(rest), lowered(photo)))

    def test_new_mouth_content_stays_as_generated(self):
        photo = detailed_photo()
        rest = soft(photo)
        open_mouth = rest.copy()
        open_mouth[150:210, 90:170] = (40, 30, 150)
        frame = list(keep_photo_detail([rest, open_mouth], photo))[1]
        np.testing.assert_array_equal(frame[:100], photo[:100])
        inside = frame[165:195, 105:155].astype(int)
        self.assertLess(np.abs(inside - (40, 30, 150)).max(), 3)

    def test_resizes_to_the_photo(self):
        photo = cv2.resize(detailed_photo(), (110, 160))
        frame = list(keep_photo_detail([cv2.resize(soft(photo), (256, 256))], photo))[0]
        np.testing.assert_array_equal(frame, photo)

    def test_no_generated_faces_yields_nothing(self):
        self.assertEqual(list(keep_photo_detail([], detailed_photo())), [])

    def test_each_item_gets_its_neighbors(self):
        self.assertEqual(list(with_neighbors('abc')), [('a', 'a', 'b'), ('a', 'b', 'c'), ('b', 'c', 'c')])
        self.assertEqual(list(with_neighbors('a')), [('a', 'a', 'a')])
        self.assertEqual(list(with_neighbors('')), [])


if __name__ == '__main__':
    unittest.main()
