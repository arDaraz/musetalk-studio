import json
import logging
import subprocess
import tempfile
import time
import uuid
import wave
from pathlib import Path


ROOT = Path('/workspace')
OUTPUTS = ROOT / 'results' / 'web'
SPEECH_COMMANDS = {
    'chatterbox': ['/opt/voice/bin/python', str(ROOT / 'speech.py')],
    'cosyvoice': ['PYTHONPATH=/opt/CosyVoice:/opt/CosyVoice/third_party/Matcha-TTS',
                 '/opt/cosyvoice/bin/python', str(ROOT / 'cosy_speech.py')],
}


def run_media(command, log):
    subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)


def prepare_inputs(photo, audio, job, log):
    run_media([
        'ffmpeg', '-hide_banner', '-y', '-i', photo, '-frames:v', '1',
        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
        '-r', '25', '-c:v', 'libx264rgb', '-crf', '0', '-pix_fmt', 'rgb24',
        str(job / f'{job.name}.mp4'),
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
        '--parsing_mode', 'mouth',
    ], log)
    video = output / 'v15' / 'video.mp4'
    if not video.is_file():
        raise ValueError('MuseTalk could not render this photo. Use a clear, front-facing portrait with one visible face.')
    run_media(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], log)
    return str(video)


def validate_request(request):
    if not request['photo']:
        raise ValueError('Upload a photo with one clear, visible face.')
    if request['source'] == 'script':
        if not request['text'] or not request['text'].strip():
            raise ValueError('Type the script you want your voice to say.')
    elif not request['audio']:
        raise ValueError('Upload an audio recording.')


def prepare_reference(request, output, log):
    reference = request.get('reference') or str(ROOT / 'voices/badr.wav')
    normalized = output / 'reference.wav'
    run_media(['ffmpeg', '-hide_banner', '-y', '-i', reference, '-vn', '-ac', '1',
               '-ar', '24000', '-t', '31', str(normalized)], log)
    with wave.open(str(normalized)) as audio:
        duration = audio.getnframes() / audio.getframerate()
    if not 3 <= duration <= 30:
        raise ValueError('Use a reference recording between 3 and 30 seconds long.')
    return str(normalized)


def speech_audio(request, output, log):
    if request['source'] == 'audio':
        return request['audio']
    script_file = output / 'script.json'
    script_file.write_text(json.dumps({
        'text': request['text'].strip(), 'language': request['language'],
        'reference': prepare_reference(request, output, log),
    }, ensure_ascii=False))
    command = SPEECH_COMMANDS[request.get('engine', 'chatterbox')]
    run_media(['env', '-u', 'LD_LIBRARY_PATH', *command, str(script_file)], log)
    return str(output / 'voice.wav')


def create_voice(request, output, progress):
    progress(0.1, desc='Generating speech in your cloned voice')
    with (output / 'render.log').open('w') as log:
        return speech_audio(request, output, log)


def create_video(request, output, progress):
    with tempfile.TemporaryDirectory(prefix='portrait-', dir=ROOT) as directory:
        with (output / 'render.log').open('w') as log:
            job = Path(directory)
            progress(0.1, desc='Preparing speech in your cloned voice' if request['source'] == 'script' else 'Preparing audio')
            audio_path = speech_audio(request, output, log)
            progress(0.4, desc='Preparing your photo')
            prepare_inputs(request['photo'], audio_path, job, log)
            progress(0.5, desc='Generating video on the DGX')
            return render_video(job, output, log)


def run_generation(request, renderer, progress):
    started = time.monotonic()
    output = OUTPUTS / uuid.uuid4().hex
    output.mkdir(parents=True)
    try:
        media_path = renderer(request, output, progress)
    except subprocess.CalledProcessError as error:
        logging.exception('Generation failed. See %s', output / 'render.log')
        raise RuntimeError('Generation failed. Check your inputs and try again. The server saved a log for this job.') from error
    progress(1, desc='Ready')
    return media_path, f'Ready in {time.monotonic() - started:.0f} seconds. Use the download button to save it.'



def generate(request, progress):
    validate_request(request)
    return run_generation(request, create_video, progress)


def generate_voice(request, progress):
    if not request['text'].strip():
        raise ValueError('Type the script you want your voice to say.')
    return run_generation(request, create_voice, progress)
