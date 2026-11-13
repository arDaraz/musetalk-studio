import html
import os
from pathlib import Path

import gradio as gr
from gradio_client.exceptions import AppError
from PIL import Image

from remote_client import generate_remote, OUTPUTS

ROOT = Path(__file__).resolve().parent
WORDS_PER_SECOND = 2.5
STEP_TITLES = ('Photo', 'Voice', 'Script', 'Video')
PHOTO, VOICE, SCRIPT, VIDEO = range(len(STEP_TITLES))
ENGINE_NAMES = {'chatterbox': 'Chatterbox', 'cosyvoice': 'CosyVoice 3'}
STEP_TIPS = (
    ('For the best video', [
        'Use the original photo, not a screenshot.', 'Show one face that looks at the camera.',
        'Use even light on the face.', 'Keep the mouth closed and not covered.',
        'Make the face at least 256 pixels wide.',
    ]),
    ('For a clear cloned voice', [
        'Use a recording of 3 to 30 seconds with one speaker.',
        'CosyVoice clones from the first 5 seconds, so start the recording with clear speech.',
        'Without a recording, the voice saved on the DGX reads the script.',
    ]),
    ('For natural speech', [
        'Write short sentences.', 'Spell out numbers and short forms the way you say them.',
        'Listen to the preview before you make the video.',
    ]),
    ('While the video renders', [
        'A video takes about a minute. The DGX makes one video at a time.',
        'Each video in this session stays in Takes, so you can compare them.',
    ]),
)
CAMERA_TIPS = ('For a good camera photo', [
    'Face a window or a lamp, so the light is even.', 'Put the camera at eye level.',
    'Look into the camera, not at the screen.', 'Keep the mouth closed and not covered.',
    'The camera turns off when you take the photo or cancel.',
])

UPLOAD_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/>'
               '<path d="M5 20h14"/></svg>')
CAMERA_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2'
               'h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3.5"/></svg>')
PHOTO_ACTIONS = (
    '<div class="photo-actions" data-clipboard-kind="image">'
    '<span role="status">You can also paste a photo with ⌘V or Ctrl+V.</span>'
    '<div class="photo-buttons">'
    f'<button type="button" class="studio-button" data-photo-action="choose">{UPLOAD_ICON}Choose a file</button>'
    f'<button type="button" class="studio-button" data-photo-action="camera">{CAMERA_ICON}Take a photo</button>'
    '</div></div>'
)
CAMERA_PANEL = (
    '<div class="camera-panel">'
    '<div class="viewfinder" data-show="live countdown review">'
    '<video autoplay playsinline muted aria-label="Live camera view" data-show="live countdown"></video>'
    '<canvas class="camera-shot" role="img" aria-label="The photo you took" data-show="review"></canvas>'
    '<div class="face-guide" aria-hidden="true" data-show="live countdown"></div>'
    '<span class="camera-chip live" data-show="live countdown">Live</span>'
    '<span class="camera-chip" data-show="review">Your photo</span>'
    '<span class="camera-hint" data-show="live">Put your face inside the oval and look at the camera</span>'
    '<span class="countdown" role="status" aria-live="assertive" data-show="countdown"></span>'
    '</div>'
    '<div class="camera-controls" data-show="live countdown">'
    '<div class="camera-options"><select aria-label="Camera"></select>'
    '<label><input type="checkbox" checked> 3-second timer</label></div>'
    '<div class="camera-actions">'
    '<button type="button" class="studio-button quiet" data-photo-action="cancel">Cancel</button>'
    f'<button type="button" class="studio-button primary" data-photo-action="shoot">{CAMERA_ICON}Take photo</button>'
    '</div></div>'
    '<div class="camera-controls" data-show="review">'
    '<span class="camera-size" role="status"></span>'
    '<div class="camera-actions">'
    '<button type="button" class="studio-button" data-photo-action="camera">Retake</button>'
    '<button type="button" class="studio-button primary" data-photo-action="use">Use this photo</button>'
    '</div></div>'
    '<div class="warn camera-error" role="alert" data-show="error"><strong></strong><span></span>'
    '<div class="camera-controls">'
    '<button type="button" class="studio-button primary" data-photo-action="camera">Try again</button>'
    '<button type="button" class="studio-button" data-photo-action="cancel">Upload a photo instead</button>'
    '</div></div>'
    '</div>'
)

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
        raise gr.Error('Add a recording to clone, or choose My saved voice.')
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
        return warn_html('You changed the script or voice after this preview. Generate it again to hear the update.')
    return ''


def script_details(text):
    words = (text or '').split()
    if not words:
        return ''
    seconds = max(1, round(len(words) / WORDS_PER_SECOND))
    return hint_html(f'{len(text.strip())} characters · about {seconds} seconds of speech')


def select_engine(engine, language):
    cosyvoice = engine == 'cosyvoice'
    languages = [('English', 'en')] if cosyvoice else [('English', 'en'), ('العربية', 'ar')]
    return gr.update(choices=languages, value='en' if cosyvoice else language), gr.update(visible=cosyvoice)


def select_source(source):
    script = source == 'script'
    return gr.update(visible=script), gr.update(visible=not script)


def select_voice(voice):
    return gr.update(visible=voice == 'clone')


def photo_quality(photo):
    if not photo:
        return ''
    with Image.open(photo) as image:
        width, height = image.size
    if min(width, height) < 512:
        return warn_html(f'{width} × {height} pixels. This is a small image. The server enlarges the photo, but the '
                         'lips in the video are not sharp because the photo has little mouth detail. Upload the '
                         'original full-resolution photo for a clearer video.')
    return hint_html(f'{width} × {height} pixels.')


def header_html(step, recording):
    items = []
    for index, title in enumerate(STEP_TITLES):
        if recording and index == SCRIPT:
            state, mark, title = 'skipped', '-', 'Script (skipped)'
        elif index < step:
            state, mark = 'done', '✓'
        else:
            state, mark = ('current' if index == step else 'todo'), str(index + 1)
        current = ' aria-current="step"' if state == 'current' else ''
        items.append(f'<li class="{state}"{current}><span class="dot">{mark}</span>{title}</li>')
    return (f'<header class="studio-header"><span class="brand">MuseTalk</span>'
            f'<ol class="stepper" aria-label="Progress">{"".join(items)}</ol>'
            '<span class="privacy">Your photo and audio go only to your DGX</span></header>')


def summary_html(request):
    photo = html.escape(Path(request[photo_input]).name) if request[photo_input] else 'Not added yet'
    if request[source_input] == 'audio':
        voice, script = 'Your recording', 'Skipped. Your recording is the speech.'
    else:
        engine = ENGINE_NAMES[request[engine_input]]
        voice = (f'Saved voice · {engine}' if request[voice_input] == 'saved'
                 else f'Cloned from your recording · {engine}')
        text = (request[script_input] or '').strip()
        script = html.escape(text if len(text) <= 90 else text[:90] + '...') if text else 'Not written yet'
    rows = ''.join(f'<dt>{label}</dt><dd>{value}</dd>'
                   for label, value in (('Photo', photo), ('Voice', voice), ('Script', script)))
    return f'<h2 class="aside-title">Your video</h2><dl class="summary">{rows}</dl>'


def tips_list(title, tips, kind):
    items = ''.join(f'<li>{tip}</li>' for tip in tips)
    return f'<div class="{kind}"><h2 class="aside-title">{title}</h2><ul class="tips">{items}</ul></div>'


def tips_html(step):
    content = tips_list(*STEP_TIPS[step], 'step-tips')
    if step == PHOTO:
        content += tips_list(*CAMERA_TIPS, 'camera-tips')
    return content


def go_to(request, step):
    recording = request[source_input] == 'audio'
    return {
        step_state: step, header: header_html(step, recording), summary: summary_html(request),
        tips: tips_html(step), edit_script: gr.update(visible=not recording),
        **{group: gr.update(visible=index == step) for index, group in enumerate(step_groups)},
    }


def stay(message):
    gr.Warning(message)
    return {}


def continue_from_photo(request):
    if not request[photo_input]:
        return stay('Add a photo to continue.')
    return go_to(request, VOICE)


def continue_from_voice(request):
    if request[source_input] == 'audio':
        if not request[audio_input]:
            return stay('Add your recording to continue.')
        return go_to(request, VIDEO)
    if request[voice_input] == 'clone' and not request[reference_input]:
        return stay('Add a recording to clone, or choose My saved voice.')
    return go_to(request, SCRIPT)


def continue_from_script(request):
    if not (request[script_input] or '').strip():
        return stay('Type the script you want your voice to say.')
    return go_to(request, VIDEO)


def go_back(request):
    step = request[step_state] - 1
    if step == SCRIPT and request[source_input] == 'audio':
        step = VOICE
    return go_to(request, step)


def make_another_take(request):
    return go_to(request, VOICE if request[source_input] == 'audio' else SCRIPT)


def step_heading(number, title, text):
    gr.HTML(f'<div class="step-heading"><span class="eyebrow">Step {number} of {len(STEP_TITLES)}</span>'
            f'<h1>{title}</h1><p>{text}</p></div>')


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


def back_button():
    return gr.Button('Back', variant='secondary', scale=0, min_width=120)


def continue_button(label):
    return gr.Button(label, variant='primary', scale=0, min_width=220, elem_classes='continue')


with gr.Blocks(title='MuseTalk') as app:
    header = gr.HTML(header_html(PHOTO, recording=False), container=False)
    with gr.Row(equal_height=False, elem_classes='studio-main'):
        with gr.Column(scale=3, min_width=420, elem_classes='step-card'):
            with gr.Column(elem_id='photo-step') as photo_step:
                step_heading(1, 'Add your photo',
                             'Upload, paste, or take one clear photo of the face. The video moves only the mouth, '
                             'so the rest of the photo stays as it is.')
                with gr.Column(elem_id='photo-zone'):
                    photo_input = gr.Image(label='Photo', show_label=False, type='filepath', sources=['upload'],
                                           height=260, placeholder='# Drop a photo here\nor click to choose one',
                                           container=False, elem_id='photo-input')
                    gr.HTML(PHOTO_ACTIONS, container=False, padding=False)
                gr.HTML(CAMERA_PANEL, container=False, padding=False)
                photo_guidance = gr.HTML(elem_classes='photo-guidance')
                with gr.Row(elem_classes='nav-row'):
                    photo_next = continue_button('Continue to voice')
            with gr.Column(visible=False) as voice_step:
                step_heading(2, 'How should it sound?',
                             'Type a script for a cloned voice to read, or use a recording you already have.')
                source_input = gr.Radio([('Type a script', 'script'), ('Upload a recording', 'audio')], value='script',
                                        label='Where does the speech come from?', elem_classes=['choice-cards', 'flat'])
                with gr.Column(elem_classes='nested') as script_voice:
                    voice_input = gr.Radio([('My saved voice', 'saved'), ('Clone from a new recording', 'clone')],
                                           value='saved', label='Which voice?', elem_classes=['segmented', 'flat'])
                    with gr.Column(visible=False, elem_classes='nested') as clone_group:
                        reference_input = gr.Audio(label='Recording to clone', type='filepath', sources=['upload'],
                                                   elem_id='reference-input')
                        clipboard_target('reference', 'Recording')
                        hint('Use a clear recording of 3 to 30 seconds. CosyVoice clones from the first 5 seconds '
                             'and writes down their words for you.')
                    engine_input = gr.Radio([('Chatterbox (English and Arabic)', 'chatterbox'),
                                             ('CosyVoice 3 (English only)', 'cosyvoice')],
                                            value='chatterbox', label='Voice engine', elem_classes=['choice-cards', 'flat'])
                with gr.Column(visible=False, elem_classes='nested') as recording_group:
                    audio_input = gr.Audio(label='Your recording', type='filepath', sources=['upload'],
                                           elem_id='audio-input')
                    clipboard_target('audio', 'Audio')
                    hint('The lips follow this recording exactly, so you skip the script step.')
                with gr.Row(elem_classes='nav-row'):
                    voice_back = back_button()
                    voice_next = continue_button('Continue')
            with gr.Column(visible=False) as script_step:
                step_heading(3, 'What should you say?',
                             'Type the new words. Your cloned voice reads them, and your photo speaks them.')
                script_input = gr.Textbox(label='Script', lines=5,
                                          placeholder='Type the words you want your voice to say...')
                with gr.Row(equal_height=True, elem_classes='script-meta'):
                    script_meta = gr.HTML()
                    language_input = gr.Radio([('English', 'en'), ('العربية', 'ar')], value='en',
                                              label='Script language', show_label=False, container=False,
                                              elem_classes='segmented')
                language_note = gr.HTML(hint_html('CosyVoice 3 reads English only. For Arabic, choose Chatterbox '
                                                  'in step 2.'), visible=False)
                with gr.Column(elem_classes='preview-box'):
                    gr.HTML('<h2 class="box-title">Listen before you make the video</h2>'
                            '<p class="hint">Optional. A preview takes about 20 seconds.</p>')
                    preview_button = gr.Button('Generate voice preview', variant='secondary')
                    voice = gr.Audio(label='Voice preview', interactive=False)
                    preview_status = gr.HTML()
                with gr.Row(elem_classes='nav-row'):
                    script_back = back_button()
                    script_next = continue_button('Continue to video')
            with gr.Column(visible=False) as video_step:
                step_heading(4, 'Make your video', 'Check your choices on the right, then make the video.')
                with gr.Row(elem_classes='edit-row'):
                    edit_photo = gr.Button('Edit photo', size='sm', variant='secondary')
                    edit_voice = gr.Button('Edit voice', size='sm', variant='secondary')
                    edit_script = gr.Button('Edit script', size='sm', variant='secondary')
                generate_button = gr.Button('Make my video', variant='primary', size='lg', elem_id='make-video')
                video = gr.Video(label='Video', show_label=False, interactive=False, height=480, elem_id='stage')
                status = gr.Markdown(elem_id='status')
                with gr.Row(elem_classes='nav-row'):
                    video_back = back_button()
                    another_take = gr.Button('Make another take', variant='secondary', scale=0, min_width=180)
                    download = gr.DownloadButton('Download MP4', variant='primary', visible=False, scale=0,
                                                 min_width=180)
                take_picker = gr.Radio(label='Takes', choices=[], visible=False, elem_classes=['segmented', 'flat'])
        with gr.Column(scale=2, min_width=320, elem_classes='aside'):
            summary = gr.HTML(container=False, padding=False, elem_classes='aside-card')
            tips = gr.HTML(tips_html(PHOTO), container=False, padding=False, elem_classes=['aside-card', 'tips-card'])
    step_state = gr.State(PHOTO)
    takes_state = gr.State([])
    preview_state = gr.State()
    step_groups = (photo_step, voice_step, script_step, video_step)

    photo_input.change(photo_quality, inputs=photo_input, outputs=photo_guidance, queue=False)
    source_input.change(select_source, inputs=source_input, outputs=[script_voice, recording_group], queue=False)
    voice_input.change(select_voice, inputs=voice_input, outputs=clone_group, queue=False)
    engine_input.change(select_engine, inputs=[engine_input, language_input], outputs=[language_input, language_note],
                        queue=False)
    script_input.change(script_details, inputs=script_input, outputs=script_meta, queue=False,
                        trigger_mode='always_last')
    preview_inputs = (voice_input, reference_input, script_input, language_input, engine_input)
    speech_inputs = {source_input, *preview_inputs}
    gr.on([component.change for component in preview_inputs], preview_note, inputs=speech_inputs | {preview_state},
          outputs=preview_status, queue=False, trigger_mode='always_last')

    nav_inputs = speech_inputs | {step_state, photo_input, audio_input}
    nav_outputs = [step_state, header, summary, tips, edit_script, *step_groups]
    for button, handler in (
        (photo_next, continue_from_photo), (voice_next, continue_from_voice), (script_next, continue_from_script),
        (voice_back, go_back), (script_back, go_back), (video_back, go_back), (another_take, make_another_take),
        (edit_photo, lambda request: go_to(request, PHOTO)), (edit_voice, lambda request: go_to(request, VOICE)),
        (edit_script, lambda request: go_to(request, SCRIPT)),
    ):
        button.click(handler, inputs=nav_inputs, outputs=nav_outputs, concurrency_limit=None, show_progress='hidden')

    preview_button.click(preview_voice, inputs=speech_inputs, outputs=[voice, preview_state, preview_status],
                         show_progress_on=voice, concurrency_id='generation', concurrency_limit=1)
    generate_button.click(
        generate, inputs=speech_inputs | {photo_input, audio_input, takes_state},
        outputs=[video, status, takes_state, take_picker, download],
        show_progress_on=video, concurrency_id='generation', concurrency_limit=1,
    )
    take_picker.input(show_take, inputs=take_picker, outputs=[video, download], queue=False)
    app.load(summary_html, inputs=nav_inputs, outputs=summary, queue=False)

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='127.0.0.1', server_port=int(os.environ.get('MUSE_UI_PORT', '7860')),
        theme=THEME, footer_links=[],
        js=(ROOT / 'studio.js').read_text(),
        css=(ROOT / 'studio.css').read_text(),
        allowed_paths=[str(OUTPUTS)],
    )
