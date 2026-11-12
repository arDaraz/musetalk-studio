import io
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image

from webui import photo_quality, prepare_inputs


class PhotoQualityTests(unittest.TestCase):
    def test_preparation_preserves_pixels_and_pads_only_odd_dimensions(self):
        for size in [(316, 270), (1025, 769)]:
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                job = root / 'portrait'
                job.mkdir()
                pixels = bytes(index % 251 for index in range(size[0] * size[1] * 3))
                photo = Image.frombytes('RGB', size, pixels)
                photo.save(root / 'photo.png')
                with wave.open(str(root / 'input.wav'), 'wb') as audio:
                    audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                    audio.writeframes(bytes(3200))
                with (root / 'prepare.log').open('w') as log:
                    prepare_inputs(str(root / 'photo.png'), str(root / 'input.wav'), job, log)
                decoded = subprocess.run([
                    'ffmpeg', '-v', 'error', '-i', str(job / 'portrait.mp4'),
                    '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-',
                ], capture_output=True, check=True)
                with Image.open(io.BytesIO(decoded.stdout)) as frame:
                    self.assertEqual(frame.size, (size[0] + size[0] % 2, size[1] + size[1] % 2))
                    self.assertEqual(frame.convert('RGB').crop((0, 0, *size)).tobytes(), pixels)

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
