from typing import Literal

import gradio as gr
from pydantic import BaseModel, ValidationError, model_validator

import engine


class SpeechOptions(BaseModel):
    source: Literal['audio', 'script']
    text: str = ''
    language: Literal['en', 'ar'] = 'en'
    engine: Literal['chatterbox', 'cosyvoice'] = 'chatterbox'

    @model_validator(mode='after')
    def check_voice_language(self):
        if self.source == 'script' and self.engine == 'cosyvoice' and self.language != 'en':
            raise ValueError('CosyVoice supports English here. Choose Chatterbox for Arabic.')
        return self


def speech_options(speech):
    try:
        return SpeechOptions.model_validate(speech).model_dump()
    except ValidationError as error:
        raise gr.Error(error.errors()[0]['msg']) from error


def generate(photo, audio, speech, reference=None, progress=gr.Progress()):
    # Gradio injects progress after the four API inputs.
    request = {'photo': photo, 'audio': audio, 'reference': reference, **speech_options(speech)}
    try:
        return engine.generate(request, progress)
    except (ValueError, RuntimeError) as error:
        raise gr.Error(str(error)) from error


def generate_voice(speech, reference=None, progress=gr.Progress()):
    request = {'reference': reference, **speech_options(speech)}
    if request['source'] != 'script':
        raise gr.Error('Choose Type a script to generate a voice preview.')
    try:
        return engine.generate_voice(request, progress)
    except (ValueError, RuntimeError) as error:
        raise gr.Error(str(error)) from error


with gr.Blocks(title='MuseTalk generation API') as app:
    gr.Markdown('Generation service. Use the local Studio interface for photos and scripts.')
    photo = gr.Image(type='filepath')
    audio = gr.Audio(type='filepath')
    speech = gr.JSON(label='Speech options')
    reference = gr.Audio(type='filepath', label='Reference voice')
    video_output = gr.File(label='Generated video')
    voice_output = gr.Audio(type='filepath', label='Generated voice')
    status = gr.Textbox(label='Status')
    gr.Button('Generate video').click(
        generate, inputs=[photo, audio, speech, reference], outputs=[video_output, status],
        api_name='generate', concurrency_id='generation', concurrency_limit=1,
    )
    gr.Button('Generate voice').click(
        generate_voice, inputs=[speech, reference], outputs=[voice_output, status],
        api_name='generate_voice', concurrency_id='generation', concurrency_limit=1,
    )

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='0.0.0.0', server_port=7860,
        allowed_paths=[str(engine.OUTPUTS)], footer_links=[],
    )
