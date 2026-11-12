import json
import sys
from pathlib import Path

import soundfile as sf
import torch
from cosyvoice.cli.cosyvoice import AutoModel

ROOT = Path('/workspace')
PROMPT = 'You are a helpful assistant.<|endofprompt|>'


def speech_segments(model, script):
    if script['transcript']:
        return model.inference_zero_shot(
            script['text'], PROMPT + script['transcript'], script['reference'], stream=False,
        )
    return model.inference_cross_lingual(
        PROMPT + script['text'], script['reference'], stream=False,
    )


def generate_speech(script_file):
    script = json.loads(script_file.read_text())
    torch.set_num_threads(2)
    model = AutoModel(model_dir=str(ROOT / 'models/cosyvoice3'), fp16=True)
    with sf.SoundFile(script_file.with_name('voice.wav'), mode='w', samplerate=model.sample_rate, channels=1) as audio:
        for segment in speech_segments(model, script):
            audio.write(segment['tts_speech'].squeeze(0).cpu().numpy())
    if sf.info(script_file.with_name('voice.wav')).frames == 0:
        raise ValueError('CosyVoice returned no speech.')


if __name__ == '__main__':
    generate_speech(Path(sys.argv[1]))
