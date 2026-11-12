import json
import re
import sys
import textwrap
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

ROOT = Path('/workspace')


def script_chunks(text):
    sentences = re.split(r'(?<=[.!?؟。])\s+|\n+', text.strip())
    return [chunk for sentence in sentences for chunk in textwrap.wrap(sentence, width=200)]


def generate_speech(script_file):
    script = json.loads(script_file.read_text())
    chunks = script_chunks(script['text'])
    if not chunks:
        raise ValueError('The script is empty.')
    torch.set_num_threads(2)
    model = ChatterboxMultilingualTTS.from_local(ROOT / 'models/chatterbox', device='cuda', t3_model='v3')
    model.prepare_conditionals(str(ROOT / 'voices/badr.wav'))
    with sf.SoundFile(script_file.with_name('voice.wav'), mode='w', samplerate=model.sr, channels=1) as audio:
        for index, chunk in enumerate(chunks):
            print(f'Generating speech segment {index + 1}/{len(chunks)}', flush=True)
            waveform = model.generate(chunk, language_id=script['language'])
            audio.write(waveform.squeeze(0).numpy())
            if index + 1 < len(chunks):
                audio.write(np.zeros(int(model.sr * 0.15), dtype=np.float32))


if __name__ == '__main__':
    generate_speech(Path(sys.argv[1]))
