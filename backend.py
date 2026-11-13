from typing import Literal

import gradio as gr
from pydantic import BaseModel, ValidationError

import engine


class SpeechOptions(BaseModel):
    source: Literal['audio', 'script']
    text: str = ''
    language: Literal['en', 'ar'] = 'en'


def generate(photo, audio, speech, progress=gr.Progress()):
    try:
        options = SpeechOptions.model_validate(speech)
    except ValidationError as error:
        raise gr.Error('Choose an audio or script source and an English or Arabic language.') from error
    request = {'photo': photo, 'audio': audio, **options.model_dump()}
    try:
        return engine.generate(request, progress)
    except (ValueError, RuntimeError) as error:
        raise gr.Error(str(error)) from error


app = gr.Interface(
    generate,
    inputs=[gr.Image(type='filepath'), gr.Audio(type='filepath'), gr.JSON(label='Speech options')],
    outputs=[gr.File(label='Generated video'), gr.Textbox(label='Status')],
    api_name='generate', title='MuseTalk generation API',
    description='Generation service. Use the local Studio interface for photo uploads and scripts.',
    flagging_mode='never', concurrency_limit=1, analytics_enabled=False,
)

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(
        server_name='0.0.0.0', server_port=7860,
        allowed_paths=[str(engine.OUTPUTS)], footer_links=[],
    )
