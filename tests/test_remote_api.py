import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gradio as gr
import httpx

import backend
import remote_client


class BackendContractTests(unittest.TestCase):
    def test_invalid_speech_options_never_start_inference(self):
        with patch('backend.engine.generate') as generate:
            for options in [None, {'source': 'unknown'}, {'source': 'script', 'language': 'invalid'}]:
                with self.subTest(options=options), self.assertRaises(gr.Error):
                    backend.generate(None, None, options)
            generate.assert_not_called()

    def test_script_options_cross_the_api_boundary(self):
        progress = Mock()
        with patch('backend.engine.generate', return_value=('video.mp4', 'Ready')) as generate:
            output = backend.generate('photo.png', None,
                                      {'source': 'script', 'text': 'مرحبا', 'language': 'ar'}, progress)
        self.assertEqual(output, ('video.mp4', 'Ready'))
        self.assertEqual(generate.call_args.args[0], {
            'photo': 'photo.png', 'audio': None, 'source': 'script', 'text': 'مرحبا', 'language': 'ar',
        })
        self.assertIs(generate.call_args.args[1], progress)

    def test_missing_photo_returns_a_user_error_before_generation(self):
        with self.assertRaisesRegex(gr.Error, 'Upload a photo'):
            backend.generate(None, None, {'source': 'script', 'text': 'Hello'})


class RemoteClientTests(unittest.TestCase):
    def tearDown(self):
        remote_client.get_client.cache_clear()

    def test_unconfigured_server_fails_on_request_without_preventing_ui_import(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, 'not configured'):
            remote_client.get_client()

    def test_connection_failure_has_a_useful_message(self):
        with patch.dict(os.environ, {'MUSE_API_URL': 'http://server.invalid'}):
            with patch('remote_client.Client', side_effect=httpx.ConnectError('offline')):
                with self.assertRaisesRegex(RuntimeError, 'Check Tailscale'):
                    remote_client.get_client()

    def test_uploads_progress_and_downloaded_result(self):
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / 'photo.png'
            photo.write_bytes(b'fixture')
            audio = Path(directory) / 'audio.wav'
            audio.write_bytes(b'fixture')
            job = Mock()
            job.done.side_effect = [False, True]
            job.status.return_value = SimpleNamespace(progress_data=[
                SimpleNamespace(progress=0.5, desc='Generating on DGX'),
            ])
            job.result.return_value = (str(Path(directory) / 'video.mp4'), 'Ready')
            client = Mock()
            client.submit.return_value = job
            progress = Mock()
            speech = {'source': 'audio'}
            with patch('remote_client.get_client', return_value=client), patch('remote_client.time.sleep'):
                output = remote_client.generate_remote(str(photo), str(audio), speech, progress)
            self.assertEqual(output, job.result.return_value)
            submitted_photo, submitted_audio, submitted_speech = client.submit.call_args.args
            self.assertEqual(submitted_photo['path'], str(photo))
            self.assertEqual(submitted_audio['path'], str(audio))
            self.assertEqual(submitted_speech, speech)
            self.assertEqual(client.submit.call_args.kwargs, {'api_name': '/generate'})
            progress.assert_any_call(0.5, desc='Generating on DGX')


if __name__ == '__main__':
    unittest.main()
