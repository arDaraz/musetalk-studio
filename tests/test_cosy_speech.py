import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import soundfile as sf
import torch

import cosy_speech


class CosySpeechTests(unittest.TestCase):
    def test_reference_audio_determines_prompt_not_submitted_script(self):
        with tempfile.TemporaryDirectory() as directory:
            script_file = Path(directory) / 'script.json'
            reference = str(Path(directory) / 'reference.wav')
            sf.write(reference, torch.ones(12 * 24000).numpy() * 0.1, 24000)
            script_file.write_text(json.dumps({
                'text': 'Please say these new words.', 'reference': reference,
                'transcript': 'Please say these new words.',
            }))
            recognizer = Mock()
            recognizer.transcribe.return_value = {'text': ' Words actually spoken in the recording. '}
            synthesizer = Mock(sample_rate=24000)
            synthesizer.inference_zero_shot.return_value = [{'tts_speech': torch.ones(1, 2400) * 0.1}]
            with patch('whisper.load_model', return_value=recognizer), \
                    patch('cosy_speech.AutoModel', return_value=synthesizer):
                cosy_speech.generate_speech(script_file)
            clipped = str(Path(directory) / 'cloning-reference.wav')
            recognizer.transcribe.assert_called_once_with(clipped, fp16=False, temperature=0)
            self.assertEqual(sf.info(clipped).duration, 5)
            self.assertEqual(sf.info(reference).duration, 12)
            synthesizer.inference_zero_shot.assert_called_once_with(
                'Please say these new words.',
                cosy_speech.PROMPT + 'Words actually spoken in the recording.',
                clipped, stream=False,
            )
            self.assertEqual(json.loads(script_file.read_text())['transcript'],
                             'Words actually spoken in the recording.')

    def test_unrecognized_reference_stops_before_speech_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            script_file = Path(directory) / 'script.json'
            reference = str(Path(directory) / 'silent.wav')
            sf.write(reference, torch.zeros(3 * 24000).numpy(), 24000)
            script_file.write_text(json.dumps({'text': 'Hello.', 'reference': reference}))
            recognizer = Mock()
            recognizer.transcribe.return_value = {'text': '  '}
            with patch('whisper.load_model', return_value=recognizer), \
                    patch('cosy_speech.AutoModel') as synthesize:
                with self.assertRaisesRegex(ValueError, 'recognize speech'):
                    cosy_speech.generate_speech(script_file)
                synthesize.assert_not_called()

    def test_short_reference_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = str(Path(directory) / 'reference.wav')
            for seconds in [3, 5]:
                with self.subTest(seconds=seconds):
                    sf.write(reference, torch.ones(seconds * 24000).numpy() * 0.1, 24000)
                    self.assertEqual(cosy_speech.cloning_reference(reference), reference)
                    self.assertEqual(sf.info(reference).duration, seconds)


if __name__ == '__main__':
    unittest.main()
