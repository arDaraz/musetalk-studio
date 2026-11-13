import html
import os
from pathlib import Path

import gradio as gr
from gradio_client.exceptions import AppError
from PIL import Image

from remote_client import generate_remote, OUTPUTS

ROOT = Path(__file__).resolve().parent
WORDS_PER_SECOND = 2.5

THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.teal,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont('Plus Jakarta Sans'), 'system-ui', 'sans-serif'],
    radius_size=gr.themes.sizes.radius_lg,
).set(body_background_fill='#F4F5F7')


def speech_options(request):
    return {
        'source': request[source_input], 'text': request[script_input] or '',
        'language': request[language_input], 'engine': request[engine_input],
    }


def chosen_reference(request):
    if request[source_input] != 'script' or request[voice_input] == 'saved':
        return None
    if not request[reference_input]:
        raise gr.Error('Add a recording to clone, or choose Saved voice.')
    return request[reference_input]


def call_generation(endpoint, inputs, progress):
    try:
        return generate_remote({'endpoint': endpoint, 'inputs': inputs}, progress)
    except (AppError, RuntimeError) as error:
        raise gr.Error(str(error)) from error


def generate(request, progress=gr.Progress()):
    speech = speech_options(request)
    video_path, message = call_generation('/generate', {
        'photo': request[photo_input], 'speech': speech,
        'audio': request[audio_input] if speech['source'] == 'audio' else None,
        'reference': chosen_reference(request),
    }, progress)
    takes = request[takes_state] + [video_path]
    return video_path, message, takes, take_choices(takes), gr.update(value=video_path, visible=True)


def take_choices(takes):
    return gr.update(choices=[(f'Take {number}', path) for number, path in enumerate(takes, start=1)],
                     value=takes[-1], visible=len(takes) > 1)


def show_take(path):
    return path, path


def preview_key(request):
    return tuple(request[component] for component in preview_inputs)


def preview_voice(request, progress=gr.Progress()):
    audio, message = call_generation('/generate_voice', {
        'speech': speech_options(request), 'reference': chosen_reference(request),
    }, progress)
    return audio, preview_key(request), hint_html(html.escape(message))


def preview_note(request):
    previewed = request[preview_state]
    if previewed and previewed != preview_key(request):
        return warn_html('The script or voice changed. Generate the preview again to hear the update.')
    return ''


def script_details(text):
    words = (text or '').split()
    if not words:
        return ''
    seconds = max(1, round(len(words) / WORDS_PER_SECOND))
    return hint_html(f'{len(text.strip())} characters · about {seconds} seconds of speech')


def select_engine(engine, language):
    languages = [('English', 'en')] if engine == 'cosyvoice' else [('English', 'en'), ('العربية', 'ar')]
    return gr.update(choices=languages, value='en' if engine == 'cosyvoice' else language)


def select_source(source):
    script = source == 'script'
    return gr.update(visible=script), gr.update(visible=script), gr.update(visible=not script)


def select_voice(voice):
    return gr.update(visible=voice == 'clone')


def photo_quality(photo):
    if not photo:
        return ''
    with Image.open(photo) as image:
        width, height = image.size
    if min(width, height) < 512:
        return warn_html(f'{width} × {height} pixels. This is a small image. Upload the original photo for a sharper '
                         'mouth and beard. Enlarging this image will not restore missing detail.')
    return hint_html(f'{width} × {height} pixels.')


def step_title(number, title):
    gr.HTML(f'<h2 class="step-title"><span class="step-number">{number}</span>{title}</h2>')


def hint_html(text):
    return f'<p class="hint">{text}</p>'


def warn_html(text):
    return f'<p class="warn">{text}</p>'


def hint(text):
    gr.HTML(hint_html(text))


def clipboard_target(kind, label):
    gr.HTML(
        f'<div class="clipboard-target" data-clipboard-kind="{kind}" tabindex="0" '
        f'role="group" aria-label="{label} clipboard target">'
        f'<span role="status">Hover over the {label.lower()} box and press ⌘V or Ctrl+V to paste, or click the box to upload.</span></div>'
    )


with gr.Blocks(title='MuseTalk') as app:
    gr.HTML('<header class="studio-header"><span class="brand">MuseTalk</span>'
            '<span class="tagline">Turn a photo and a script into a talking video.</span></header>')
    with gr.Row(equal_height=False):
        with gr.Column(scale=5, min_width=380, elem_id='inputs'):
            with gr.Column(elem_classes='card'):
                step_title(1, 'Photo')
                photo_input = gr.Image(label='Photo', show_label=False, type='filepath', sources=['upload'],
                                       height=240, elem_id='photo-input')
                photo_guidance = gr.HTML()
                clipboard_target('image', 'Photo')
            with gr.Column(elem_classes='card'):
                step_title(2, 'Speech')
                source_input = gr.Radio([('Type a script', 'script'), ('Upload a recording', 'audio')], value='script',
                                        label='Speech source', show_label=False, container=False,
                                        elem_classes='choice-cards')
                hint('A cloned voice reads your script. A recording is used as it is.')
            with gr.Column(elem_classes='card') as voice_group:
                step_title(3, 'Voice')
                voice_input = gr.Radio([('Saved voice', 'saved'), ('Clone from a recording', 'clone')], value='saved',
                                       label='Voice', show_label=False, container=False, elem_classes='segmented')
                with gr.Column(visible=False, elem_classes='nested') as clone_group:
                    reference_input = gr.Audio(label='Recording to clone', type='filepath', sources=['upload'],
                                               elem_id='reference-input')
                    clipboard_target('reference', 'Recording')
                    hint('Use a clear recording of 3 to 30 seconds. CosyVoice uses the first 5 seconds and '
                         'transcribes them, so start with clear speech.')
                engine_input = gr.Dropdown([('Chatterbox', 'chatterbox'), ('CosyVoice 3', 'cosyvoice')],
                                           value='chatterbox', label='Engine',
                                           info='CosyVoice 3 reads English. Chatterbox reads English and Arabic.')
            with gr.Column(elem_classes=['card', 'current']) as script_group:
                step_title(4, 'Script')
                script_input = gr.Textbox(label='Script', show_label=False, container=False, lines=5,
                                          placeholder='Type the words you want your voice to say...')
                with gr.Row(equal_height=True, elem_classes='script-meta'):
                    script_meta = gr.HTML()
                    language_input = gr.Radio([('English', 'en'), ('العربية', 'ar')], value='en',
                                              label='Script language', show_label=False, container=False,
                                              elem_classes='segmented')
                preview_button = gr.Button('Generate voice preview', variant='secondary')
                voice = gr.Audio(label='Voice preview', interactive=False)
                preview_status = gr.HTML()
            with gr.Column(visible=False, elem_classes=['card', 'current']) as upload_group:
                step_title(3, 'Your recording')
                audio_input = gr.Audio(label='Your recording', type='filepath', sources=['upload'], elem_id='audio-input')
                clipboard_target('audio', 'Audio')
                hint('The lips follow this recording exactly. No script is needed.')
            generate_button = gr.Button('Make video', variant='primary', size='lg', elem_id='make-video')
            hint('The DGX renders one video at a time.')
        with gr.Column(scale=7, min_width=480):
            with gr.Column(elem_classes=['card', 'stage-card']):
                video = gr.Video(label='Video', show_label=False, interactive=False, height=560, elem_id='stage')
                with gr.Row(equal_height=True, elem_classes='stage-bar'):
                    status = gr.Markdown('Your video appears here after you select **Make video**.', elem_id='status')
                    download = gr.DownloadButton('Download MP4', variant='primary', visible=False, scale=0,
                                                 min_width=160)
            take_picker = gr.Radio(label='Takes', choices=[], visible=False, elem_classes='segmented')
    takes_state = gr.State([])
    preview_state = gr.State()

    photo_input.change(photo_quality, inputs=photo_input, outputs=photo_guidance, queue=False)
    source_input.change(select_source, inputs=source_input, outputs=[voice_group, script_group, upload_group],
                        queue=False)
    voice_input.change(select_voice, inputs=voice_input, outputs=clone_group, queue=False)
    engine_input.change(select_engine, inputs=[engine_input, language_input], outputs=language_input, queue=False)
    script_input.change(script_details, inputs=script_input, outputs=script_meta, queue=False,
                        trigger_mode='always_last')
    preview_inputs = (voice_input, reference_input, script_input, language_input, engine_input)
    speech_inputs = {source_input, *preview_inputs}
    gr.on([component.change for component in preview_inputs], preview_note, inputs=speech_inputs | {preview_state},
          outputs=preview_status, queue=False, trigger_mode='always_last')
    preview_button.click(preview_voice, inputs=speech_inputs, outputs=[voice, preview_state, preview_status],
                         show_progress_on=voice, concurrency_id='generation', concurrency_limit=1)
    generate_button.click(
        generate, inputs=speech_inputs | {photo_input, audio_input, takes_state},
        outputs=[video, status, takes_state, take_picker, download],
        show_progress_on=video, concurrency_id='generation', concurrency_limit=1,
    )
    take_picker.input(show_take, inputs=take_picker, outputs=[video, download], queue=False)

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='127.0.0.1', server_port=int(os.environ.get('MUSE_UI_PORT', '7860')),
        theme=THEME, footer_links=[],
        js=(ROOT / 'clipboard.js').read_text(),
        css=(ROOT / 'studio.css').read_text(),
        allowed_paths=[str(OUTPUTS)],
    )
