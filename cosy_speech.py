import json
import sys
from pathlib import Path

import soundfile as sf
import torch
import whisper
from cosyvoice.cli.cosyvoice import AutoModel
from cosyvoice.utils.common import set_all_random_seed

ROOT = Path('/workspace')
PROMPT = 'You are a helpful assistant.<|endofprompt|>'


def cloning_reference(reference):
    samples, sample_rate = sf.read(reference)
    if len(samples) <= 5 * sample_rate:
        return reference
    clipped = Path(reference).with_name('cloning-reference.wav')
    sf.write(clipped, samples[:5 * sample_rate], sample_rate)
    return str(clipped)


def reference_transcript(reference):
    recognizer = whisper.load_model('base', device='cpu', download_root=str(ROOT / 'models/whisper-asr'))
    recognition = recognizer.transcribe(reference, fp16=False, temperature=0)
    transcript = recognition['text'].strip()
    if not transcript:
        raise ValueError('Could not recognize speech in the reference recording. Use a clear recording of one speaker.')
    return transcript


def generate_speech(script_file):
    script = json.loads(script_file.read_text())
    torch.set_num_threads(2)
    script['reference'] = cloning_reference(script['reference'])
    script['transcript'] = reference_transcript(script['reference'])
    script_file.write_text(json.dumps(script, ensure_ascii=False))
    model = AutoModel(model_dir=str(ROOT / 'models/cosyvoice3'), fp16=False)
    set_all_random_seed(1986)
    segments = model.inference_zero_shot(
        script['text'], PROMPT + script['transcript'], script['reference'], stream=False,
    )
    with sf.SoundFile(script_file.with_name('voice.wav'), mode='w', samplerate=model.sample_rate, channels=1) as audio:
        for segment in segments:
            audio.write(segment['tts_speech'].squeeze(0).cpu().numpy())
    if sf.info(script_file.with_name('voice.wav')).frames == 0:
        raise ValueError('CosyVoice returned no speech.')


if __name__ == '__main__':
    generate_speech(Path(sys.argv[1]))
