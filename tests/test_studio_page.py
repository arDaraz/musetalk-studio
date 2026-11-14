import unittest
from unittest.mock import patch

import gradio as gr

import webui


def page_request(**values):
    request = {
        webui.source_input: 'script', webui.voice_input: 'saved', webui.reference_input: None,
        webui.script_input: 'Hello there', webui.language_input: 'en', webui.engine_input: 'chatterbox',
        webui.photo_input: '/tmp/photo.png', webui.audio_input: None, webui.takes_state: [],
        webui.preview_state: None, webui.step_state: webui.PHOTO,
    }
    request.update({getattr(webui, name): value for name, value in values.items()})
    return request


def shown_step(updates):
    return [index for index, group in enumerate(webui.step_groups) if updates[group]['visible']]


class StudioPageTests(unittest.TestCase):
    def test_script_details_estimate_speech_length(self):
        self.assertEqual(webui.script_details('   '), '')
        details = webui.script_details(' '.join(['word'] * 30))
        self.assertIn('149 characters', details)
        self.assertIn('about 12 seconds', details)

    def test_saved_voice_and_recordings_send_no_reference(self):
        self.assertIsNone(webui.chosen_reference(page_request(reference_input='voice.wav')))
        self.assertIsNone(webui.chosen_reference(page_request(
            source_input='audio', voice_input='clone', reference_input='voice.wav')))
        self.assertEqual(webui.chosen_reference(page_request(voice_input='clone', reference_input='voice.wav')),
                         'voice.wav')

    def test_cloning_requires_a_recording(self):
        with self.assertRaisesRegex(gr.Error, 'Add a recording to clone'):
            webui.chosen_reference(page_request(voice_input='clone'))

    def test_preview_note_appears_only_after_the_inputs_change(self):
        previewed = webui.preview_key(page_request())
        self.assertEqual(webui.preview_note(page_request()), '')
        self.assertEqual(webui.preview_note(page_request(preview_state=previewed)), '')
        self.assertIn('changed', webui.preview_note(page_request(preview_state=previewed, script_input='New words')))

    def test_each_video_becomes_a_selectable_take(self):
        with patch('webui.call_generation', return_value=('take-2.mp4', 'Ready')) as call:
            video, message, takes, picker, download = webui.generate(page_request(takes_state=['take-1.mp4']))
        self.assertEqual((video, message, takes), ('take-2.mp4', 'Ready', ['take-1.mp4', 'take-2.mp4']))
        self.assertEqual(picker['choices'], [('Take 1', 'take-1.mp4'), ('Take 2', 'take-2.mp4')])
        self.assertEqual((picker['value'], picker['visible']), ('take-2.mp4', True))
        self.assertEqual(download['value'], 'take-2.mp4')
        self.assertEqual(call.call_args.args[1]['speech']['source'], 'script')

    def test_first_take_hides_the_picker(self):
        with patch('webui.call_generation', return_value=('take-1.mp4', 'Ready')):
            picker = webui.generate(page_request())[3]
        self.assertFalse(picker['visible'])

    def test_script_flow_visits_every_step(self):
        self.assertEqual(shown_step(webui.continue_from_photo(page_request())), [webui.VOICE])
        self.assertEqual(shown_step(webui.continue_from_voice(page_request())), [webui.SCRIPT])
        self.assertEqual(shown_step(webui.continue_from_script(page_request())), [webui.VIDEO])
        self.assertEqual(shown_step(webui.go_back(page_request(step_state=webui.VIDEO))), [webui.SCRIPT])

    def test_recording_flow_skips_the_script_step(self):
        request = page_request(source_input='audio', audio_input='speech.m4a', step_state=webui.VIDEO)
        self.assertEqual(shown_step(webui.continue_from_voice(request)), [webui.VIDEO])
        self.assertEqual(shown_step(webui.go_back(request)), [webui.VOICE])
        self.assertEqual(shown_step(webui.make_another_take(request)), [webui.VOICE])
        self.assertIn('Script (skipped)', webui.header_html(webui.VIDEO, recording=True))

    def test_missing_inputs_keep_the_current_step(self):
        with patch('webui.gr.Warning') as warning:
            self.assertEqual(webui.continue_from_photo(page_request(photo_input=None)), {})
            self.assertEqual(webui.continue_from_voice(page_request(voice_input='clone')), {})
            self.assertEqual(webui.continue_from_voice(page_request(source_input='audio')), {})
            self.assertEqual(webui.continue_from_script(page_request(script_input='  ')), {})
        self.assertEqual(warning.call_count, 4)

    def test_only_the_photo_step_shows_the_photo_examples(self):
        photo_tips = webui.tips_html(webui.PHOTO)
        self.assertIn('class="photo-guide-faults"', photo_tips)
        self.assertIn('<li>Keep the head upright.</li>', photo_tips)
        self.assertNotIn('{tips}', photo_tips)
        self.assertNotIn('photo-guide', webui.tips_html(webui.VOICE))

    def test_summary_escapes_user_text(self):
        summary = webui.summary_html(page_request(script_input='<b>Hi</b>'))
        self.assertIn('&lt;b&gt;Hi&lt;/b&gt;', summary)
        self.assertIn('photo.png', summary)


if __name__ == '__main__':
    unittest.main()
