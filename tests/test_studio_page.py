import unittest
from unittest.mock import patch

import gradio as gr

import webui


def speech_request(**values):
    request = {
        webui.source_input: 'script', webui.voice_input: 'saved', webui.reference_input: None,
        webui.script_input: 'Hello there', webui.language_input: 'en', webui.engine_input: 'chatterbox',
        webui.photo_input: 'photo.png', webui.audio_input: None, webui.takes_state: [], webui.preview_state: None,
    }
    request.update({getattr(webui, name): value for name, value in values.items()})
    return request


class StudioPageTests(unittest.TestCase):
    def test_script_details_estimate_speech_length(self):
        self.assertEqual(webui.script_details('   '), '')
        details = webui.script_details(' '.join(['word'] * 30))
        self.assertIn('149 characters', details)
        self.assertIn('about 12 seconds', details)

    def test_saved_voice_and_recordings_send_no_reference(self):
        self.assertIsNone(webui.chosen_reference(speech_request(reference_input='voice.wav')))
        self.assertIsNone(webui.chosen_reference(speech_request(
            source_input='audio', voice_input='clone', reference_input='voice.wav')))
        self.assertEqual(webui.chosen_reference(speech_request(voice_input='clone', reference_input='voice.wav')),
                         'voice.wav')

    def test_cloning_requires_a_recording(self):
        with self.assertRaisesRegex(gr.Error, 'Add a recording to clone'):
            webui.chosen_reference(speech_request(voice_input='clone'))

    def test_preview_note_appears_only_after_the_inputs_change(self):
        previewed = webui.preview_key(speech_request())
        self.assertEqual(webui.preview_note(speech_request()), '')
        self.assertEqual(webui.preview_note(speech_request(preview_state=previewed)), '')
        self.assertIn('changed', webui.preview_note(speech_request(preview_state=previewed, script_input='New words')))

    def test_each_video_becomes_a_selectable_take(self):
        with patch('webui.call_generation', return_value=('take-2.mp4', 'Ready')) as call:
            video, message, takes, picker, download = webui.generate(speech_request(takes_state=['take-1.mp4']))
        self.assertEqual((video, message, takes), ('take-2.mp4', 'Ready', ['take-1.mp4', 'take-2.mp4']))
        self.assertEqual(picker['choices'], [('Take 1', 'take-1.mp4'), ('Take 2', 'take-2.mp4')])
        self.assertEqual((picker['value'], picker['visible']), ('take-2.mp4', True))
        self.assertEqual(download['value'], 'take-2.mp4')
        self.assertEqual(call.call_args.args[1]['speech']['source'], 'script')

    def test_first_take_hides_the_picker(self):
        with patch('webui.call_generation', return_value=('take-1.mp4', 'Ready')):
            picker = webui.generate(speech_request())[3]
        self.assertFalse(picker['visible'])

    def test_recording_mode_hides_voice_and_script_cards(self):
        voice, script, recording = webui.select_source('audio')
        self.assertEqual((voice['visible'], script['visible'], recording['visible']), (False, False, True))


if __name__ == '__main__':
    unittest.main()
