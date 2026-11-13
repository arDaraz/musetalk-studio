import os
from pathlib import Path

import gradio as gr
from gradio_client.exceptions import AppError
from PIL import Image

from remote_client import generate_remote, OUTPUTS

ROOT = Path(__file__).resolve().parent


def speech_options(request):
    return {
        'source': 'script' if request[source_input] == 'Type a script' else 'audio',
        'text': request[script_input] or '', 'language': request[language_input],
        'engine': request[engine_input],
    }


def call_generation(endpoint, inputs, progress):
    try:
        return generate_remote({'endpoint': endpoint, 'inputs': inputs}, progress)
    except (AppError, RuntimeError) as error:
        raise gr.Error(str(error)) from error


def generate(request, progress=gr.Progress()):
    speech = speech_options(request)
    return call_generation('/generate', {
        'photo': request[photo_input], 'speech': speech,
        'audio': request[audio_input] if speech['source'] == 'audio' else None,
        'reference': request[reference_input] if speech['source'] == 'script' else None,
    }, progress)


def preview_voice(request, progress=gr.Progress()):
    return call_generation('/generate_voice', {
        'speech': speech_options(request), 'reference': request[reference_input],
    }, progress)


def select_engine(engine, language):
    languages = [('English', 'en')] if engine == 'cosyvoice' else [('English', 'en'), ('Arabic', 'ar')]
    return gr.update(choices=languages, value='en' if engine == 'cosyvoice' else language)


def select_source(source):
    return gr.update(visible=source == 'Type a script'), gr.update(visible=source == 'Upload audio')


def photo_quality(photo):
    if not photo:
        return ''
    with Image.open(photo) as image:
        width, height = image.size
    guidance = f'Photo resolution: {width} × {height} pixels.'
    if min(width, height) < 512:
        guidance += (' This is a small image. The server enlarges the photo, but the lips in the video are not sharp because the photo has little mouth detail.'
                     ' Upload the original full-resolution photo for a clearer video.')
    return guidance


def clipboard_target(kind, label):
    gr.HTML(
        f'<div class="clipboard-target" data-clipboard-kind="{kind}" tabindex="0" '
        f'role="group" aria-label="{label} clipboard target">'
        f'<span role="status">Hover over the {label.lower()} box and press ⌘V or Ctrl+V to paste. Click the box to upload.</span></div>'
    )


with gr.Blocks(title='MuseTalk') as app:
    gr.Markdown('# MuseTalk\nTurn your photo and script into a video with your saved voice, or upload an audio recording.')
    with gr.Row():
        with gr.Column():
            photo_input = gr.Image(label='Your photo', type='filepath', sources=['upload'], height=340, elem_id='photo-input')
            gr.Markdown('For the best video, use the original photo and not a screenshot. Show one face that looks at the camera, '
                        'in even light, with the mouth closed and not covered. Make the face at least 256 pixels wide.')
            photo_guidance = gr.Markdown()
            clipboard_target('image', 'Photo')
            source_input = gr.Radio(['Type a script', 'Upload audio'], value='Type a script', label='Speech source')
            with gr.Group() as script_group:
                engine_input = gr.Dropdown([('Chatterbox', 'chatterbox'), ('CosyVoice 3', 'cosyvoice')],
                                           value='chatterbox', label='Voice engine')
                gr.Markdown('Use your saved voice or upload a clear 3 to 30 second recording. CosyVoice supports English here. Use Chatterbox for Arabic.')
                reference_input = gr.Audio(label='Reference voice (optional)', type='filepath', sources=['upload'], elem_id='reference-input')
                clipboard_target('reference', 'Reference audio')
                gr.Markdown('CosyVoice uses the first 5 seconds of your reference and transcribes it automatically. Start the recording with clear speech. In Script, enter the new words you want to hear.')
                script_input = gr.Textbox(label='Script', lines=5, placeholder='Enter the new words you want your voice to say...')
                language_input = gr.Dropdown([('English', 'en'), ('Arabic', 'ar')], value='en', label='Script language')
                preview_button = gr.Button('Generate voice preview')
            with gr.Group(visible=False) as upload_group:
                audio_input = gr.Audio(label='Your audio', type='filepath', sources=['upload'], elem_id='audio-input')
                clipboard_target('audio', 'Audio')
            generate_button = gr.Button('Generate video', variant='primary')
        with gr.Column():
            voice = gr.Audio(label='Cloned voice preview', interactive=False)
            video = gr.Video(label='Generated video', interactive=False, height=460)
            status = gr.Textbox(label='Status', interactive=False)
    photo_input.change(photo_quality, inputs=photo_input, outputs=photo_guidance, queue=False)
    source_input.change(select_source, inputs=source_input, outputs=[script_group, upload_group], queue=False)
    engine_input.change(select_engine, inputs=[engine_input, language_input],
                        outputs=language_input, queue=False)
    speech_inputs = {source_input, script_input, language_input, engine_input, reference_input}
    preview_button.click(preview_voice, inputs=speech_inputs, outputs=[voice, status],
                         concurrency_id='generation', concurrency_limit=1)
    generate_button.click(
        generate, inputs=speech_inputs | {photo_input, audio_input}, outputs=[video, status],
        concurrency_id='generation', concurrency_limit=1,
    )

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='127.0.0.1', server_port=int(os.environ.get('MUSE_UI_PORT', '7860')),
        theme=gr.themes.Soft(), footer_links=[],
        js=(ROOT / 'clipboard.js').read_text(),
        css="""
            .clipboard-target {
                padding: 12px;
                border: 1px dashed #6366f1;
                border-radius: 8px;
                cursor: text;
            }
            #photo-input, #audio-input, #reference-input {
                border: 1px solid #dfe3eb;
                border-radius: 8px;
            }
            .clipboard-target:hover, #photo-input:hover, #audio-input:hover, #reference-input:hover,
            .clipboard-target:focus, #photo-input:focus, #audio-input:focus, #reference-input:focus {
                outline: 2px solid #6366f1;
                outline-offset: -2px;
            }
        """,
        allowed_paths=[str(OUTPUTS)],
    )
