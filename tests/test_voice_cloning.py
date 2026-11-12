import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

import gradio as gr

import backend
import engine
import remote_client


class VoiceCloningTests(unittest.TestCase):
    def test_cosyvoice_rejects_arabic_before_loading_models(self):
        with patch('backend.engine.generate_voice') as generate:
            with self.assertRaisesRegex(gr.Error, 'Chatterbox for Arabic'):
                backend.generate_voice({'source': 'script', 'engine': 'cosyvoice', 'language': 'ar', 'text': 'مرحبا'})
            generate.assert_not_called()

    def test_unknown_engine_never_reaches_subprocess_selection(self):
        with self.assertRaises(gr.Error):
            backend.generate_voice({'source': 'script', 'engine': '/bin/sh', 'text': 'Hello'})

    def test_voice_preview_requires_script_but_not_a_photo(self):
        with self.assertRaisesRegex(gr.Error, 'Type a script'):
            backend.generate_voice({'source': 'audio'})
        with patch('backend.engine.generate_voice', return_value=('voice.wav', 'Ready')) as generate:
            self.assertEqual(backend.generate_voice({'source': 'script', 'text': 'Hello', 'engine': 'cosyvoice'},
                                                   reference='uploaded.wav'), ('voice.wav', 'Ready'))
            self.assertEqual(generate.call_args.args[0]['reference'], 'uploaded.wav')
            self.assertEqual(generate.call_args.args[0]['engine'], 'cosyvoice')

    def test_empty_script_is_rejected_before_creating_a_job(self):
        with patch('engine.run_generation') as run:
            with self.assertRaisesRegex(gr.Error, 'Type the script'):
                backend.generate_voice({'source': 'script', 'text': '  '})
            run.assert_not_called()

    def test_reference_duration_accepts_only_three_to_thirty_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.wav'
            for seconds, accepted in [(2.99, False), (3, True), (30, True), (30.01, False)]:
                with self.subTest(seconds=seconds):
                    with wave.open(str(source), 'wb') as audio:
                        audio.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                        audio.writeframes(bytes(round(seconds * 24000) * 2))
                    with (root / 'render.log').open('w') as log, patch('engine.ROOT', root):
                        if accepted:
                            self.assertEqual(engine.prepare_reference({'reference': str(source)}, root, log),
                                             str(root / 'reference.wav'))
                        else:
                            with self.assertRaisesRegex(ValueError, 'between 3 and 30'):
                                engine.prepare_reference({'reference': str(source)}, root, log)

    def test_preview_uploads_reference_and_downloads_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.write_bytes(b'fixture')
            client = Mock()
            job = client.submit.return_value
            job.done.return_value = True
            job.result.return_value = ('downloaded.wav', 'Ready')
            with patch('remote_client.get_client', return_value=client):
                output = remote_client.generate_remote({'endpoint': '/generate_voice', 'inputs': {
                    'reference': str(reference), 'speech': {'source': 'script', 'text': 'Hello', 'engine': 'cosyvoice'},
                }}, Mock())
            self.assertEqual(output, ('downloaded.wav', 'Ready'))
            self.assertEqual(client.submit.call_args.kwargs['reference']['path'], str(reference))
            self.assertEqual(client.submit.call_args.kwargs['api_name'], '/generate_voice')


if __name__ == '__main__':
    unittest.main()
