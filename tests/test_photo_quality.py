import io
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave
from pathlib import Path

from PIL import Image

from engine import photo_advice, prepare_inputs
from webui import photo_quality


class PhotoQualityTests(unittest.TestCase):
    def prepared_frame(self, size, pixels):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / 'portrait'
            job.mkdir()
            Image.frombytes('RGB', size, pixels).save(root / 'photo.png')
            with wave.open(str(root / 'input.wav'), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(bytes(3200))
            with (root / 'prepare.log').open('w') as log, patch('engine.ROOT', root):
                enlargement = prepare_inputs(str(root / 'photo.png'), str(root / 'input.wav'), job, log)
            decoded = subprocess.run([
                'ffmpeg', '-v', 'error', '-i', str(job / 'portrait.mp4'),
                '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-',
            ], capture_output=True, check=True)
        with Image.open(io.BytesIO(decoded.stdout)) as frame:
            return enlargement, frame.convert('RGB')

    def test_preparation_preserves_a_large_photo_and_pads_only_odd_dimensions(self):
        for size in [(720, 900), (1025, 769)]:
            with self.subTest(size=size):
                pixels = bytes(index % 251 for index in range(size[0] * size[1] * 3))
                enlargement, frame = self.prepared_frame(size, pixels)
                self.assertEqual(enlargement, 1)
                self.assertEqual(frame.size, (size[0] + size[0] % 2, size[1] + size[1] % 2))
                self.assertEqual(frame.crop((0, 0, *size)).tobytes(), pixels)

    def test_preparation_enlarges_a_small_photo_by_a_whole_factor(self):
        for size, factor in [((316, 270), 3), ((500, 719), 2)]:
            with self.subTest(size=size):
                enlargement, frame = self.prepared_frame(size, bytes(size[0] * size[1] * 3))
                self.assertEqual(enlargement, factor)
                self.assertEqual(frame.size, (size[0] * factor, size[1] * factor + size[1] * factor % 2))

    def test_advice_reports_a_small_face_in_photo_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'face_width.txt').write_text('330')
            self.assertIn('110 pixels wide', photo_advice(output, 3))
            (output / 'face_width.txt').write_text('768')
            self.assertEqual(photo_advice(output, 3), '')

    def test_guidance_clears_and_checks_the_shorter_dimension(self):
        self.assertEqual(photo_quality(None), '')
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / 'photo.png'
            for size, small in [((1024, 511), True), ((511, 1024), True), ((512, 512), False)]:
                with self.subTest(size=size):
                    Image.new('RGB', size).save(photo)
                    guidance = photo_quality(str(photo))
                    self.assertIn(f'{size[0]} × {size[1]}', guidance)
                    self.assertEqual('small image' in guidance, small)


if __name__ == '__main__':
    unittest.main()
