import json
import logging
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import gradio as gr

ROOT = Path('/workspace')
OUTPUTS = ROOT / 'results' / 'web'
OUTPUTS.mkdir(parents=True, exist_ok=True)


def run_media(command, log):
    subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)


def prepare_inputs(photo, audio, job, log):
    run_media([
        'ffmpeg', '-hide_banner', '-y', '-i', photo, '-frames:v', '1',
        '-vf', "scale='min(768,iw)':-2,pad=ceil(iw/2)*2:ceil(ih/2)*2",
        '-r', '25', '-pix_fmt', 'yuv420p', str(job / f'{job.name}.mp4'),
    ], log)
    run_media([
        'ffmpeg', '-hide_banner', '-y', '-i', audio, '-vn', '-ac', '1',
        '-ar', '16000', str(job / 'audio.wav'),
    ], log)
    config = {'portrait': {
        'video_path': str(job / f'{job.name}.mp4'),
        'audio_path': str(job / 'audio.wav'),
        'result_name': 'video.mp4',
    }}
    (job / 'config.json').write_text(json.dumps(config))


def render_video(job, output, log):
    run_media([
        '/usr/bin/python', '-u', '-m', 'scripts.inference',
        '--inference_config', str(job / 'config.json'),
        '--result_dir', str(output),
        '--unet_model_path', str(ROOT / 'models/musetalkV15/unet.pth'),
        '--unet_config', str(ROOT / 'models/musetalkV15/musetalk.json'),
        '--version', 'v15', '--batch_size', '1', '--use_float16',
    ], log)
    video = output / 'v15' / 'video.mp4'
    if not video.is_file():
        raise gr.Error('MuseTalk could not render this photo. Use a clear, front-facing portrait with one visible face.')
    run_media(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], log)
    return str(video)


def validate_request(request):
    if not request[photo_input]:
        raise gr.Error('Upload a photo with one clear, visible face.')
    if request[source_input] == 'Type a script':
        if not request[script_input] or not request[script_input].strip():
            raise gr.Error('Type the script you want your voice to say.')
    elif not request[audio_input]:
        raise gr.Error('Upload an audio recording.')


def speech_audio(request, output, log):
    if request[source_input] == 'Upload audio':
        return request[audio_input]
    script_file = output / 'script.json'
    script_file.write_text(json.dumps({
        'text': request[script_input].strip(),
        'language': request[language_input],
    }, ensure_ascii=False))
    run_media(['env', '-u', 'LD_LIBRARY_PATH', '/opt/voice/bin/python', str(ROOT / 'speech.py'), str(script_file)], log)
    return str(output / 'voice.wav')


def create_video(request, output, progress):
    with tempfile.TemporaryDirectory(prefix='portrait-', dir=ROOT) as directory:
        with (output / 'render.log').open('w') as log:
            job = Path(directory)
            progress(0.1, desc='Preparing speech in your saved voice' if request[source_input] == 'Type a script' else 'Preparing audio')
            audio_path = speech_audio(request, output, log)
            progress(0.4, desc='Preparing your photo')
            prepare_inputs(request[photo_input], audio_path, job, log)
            progress(0.5, desc='Generating video on the GX10')
            return render_video(job, output, log)


def generate(request, progress=gr.Progress()):
    validate_request(request)
    started = time.monotonic()
    output = OUTPUTS / uuid.uuid4().hex
    output.mkdir()
    try:
        video_path = create_video(request, output, progress)
    except subprocess.CalledProcessError as error:
        logging.exception('Generation failed. See %s', output / 'render.log')
        raise gr.Error('Generation failed. Check your inputs and try again. The server saved a log for this job.') from error
    progress(1, desc='Video ready')
    return video_path, f'Ready in {time.monotonic() - started:.0f} seconds. Use the download button on the video to save it.'


def select_source(source):
    return gr.update(visible=source == 'Type a script'), gr.update(visible=source == 'Upload audio')


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
            clipboard_target('image', 'Photo')
            source_input = gr.Radio(['Type a script', 'Upload audio'], value='Type a script', label='Speech source')
            with gr.Group() as script_group:
                gr.Markdown('Type what you want to say using the voice sample configured on the server.')
                script_input = gr.Textbox(label='Script', lines=5, placeholder='Write your script here...')
                language_input = gr.Dropdown([('English', 'en'), ('Arabic', 'ar')], value='en', label='Script language')
            with gr.Group(visible=False) as upload_group:
                audio_input = gr.Audio(label='Your audio', type='filepath', sources=['upload'], elem_id='audio-input')
                clipboard_target('audio', 'Audio')
            generate_button = gr.Button('Generate video', variant='primary')
        with gr.Column():
            video = gr.Video(label='Generated video', interactive=False, height=460)
            status = gr.Textbox(label='Status', interactive=False)
    source_input.change(select_source, inputs=source_input, outputs=[script_group, upload_group], queue=False)
    generate_button.click(
        generate, inputs={photo_input, source_input, script_input, language_input, audio_input},
        outputs=[video, status], concurrency_limit=1,
    )

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='0.0.0.0', server_port=7860,
        theme=gr.themes.Soft(), footer_links=[],
        js=(ROOT / 'clipboard.js').read_text(),
        css="""
            .clipboard-target {
                padding: 12px;
                border: 1px dashed #6366f1;
                border-radius: 8px;
                cursor: text;
            }
            #photo-input, #audio-input {
                border: 1px solid #dfe3eb;
                border-radius: 8px;
            }
            .clipboard-target:hover, #photo-input:hover, #audio-input:hover,
            .clipboard-target:focus, #photo-input:focus, #audio-input:focus {
                outline: 2px solid #6366f1;
                outline-offset: -2px;
            }
        """,
        allowed_paths=[str(OUTPUTS)],
    )
