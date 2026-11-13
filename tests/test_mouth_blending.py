import unittest
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

from musetalk.utils.face_parsing import FaceParsing


class MouthBlendingTests(unittest.TestCase):
    def parse_labels(self, labels):
        parser = FaceParsing.__new__(FaceParsing)
        scores = torch.nn.functional.one_hot(torch.from_numpy(labels).long(), num_classes=19)
        scores = scores.permute(2, 0, 1).unsqueeze(0).float()
        parser.net = lambda tensor: [scores]
        parser.preprocess = lambda image: torch.zeros((3, 512, 512))
        with patch('torch.cuda.is_available', return_value=False):
            return np.asarray(parser(Image.new('RGB', (512, 512)), mode='mouth'))

    def test_mask_keeps_mouth_motion_space_without_replacing_chin(self):
        labels = np.ones((512, 512), dtype=np.uint8)
        labels[285:295, 240:275] = 12
        labels[295:305, 240:275] = 11
        labels[305:315, 240:275] = 13
        mask = self.parse_labels(labels)
        self.assertEqual(mask[300, 250], 255)
        self.assertEqual(mask[320, 250], 255)
        self.assertTrue(np.all(mask[350:, :] == 0))
        self.assertTrue(np.all(mask[:, :200] == 0))
        self.assertTrue(np.all(mask[:, 315:] == 0))

    def test_missing_mouth_fails_instead_of_producing_a_static_portrait(self):
        with self.assertRaisesRegex(ValueError, 'No mouth found'):
            self.parse_labels(np.ones((512, 512), dtype=np.uint8))


if __name__ == '__main__':
    unittest.main()
