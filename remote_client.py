import os
import time
from functools import lru_cache
from pathlib import Path

import httpx
from gradio_client import Client, handle_file
from gradio_client.utils import Status

OUTPUTS = Path(os.environ.get(
    'MUSE_OUTPUT_DIR',
    str(Path.home() / 'Library/Application Support/MuseTalk Studio/results'),
))


@lru_cache(maxsize=1)
def get_client():
    endpoint = os.environ.get('MUSE_API_URL')
    if not endpoint:
        raise RuntimeError('The generation server is not configured.')
    try:
        return Client(endpoint, verbose=False, max_workers=1, download_files=OUTPUTS,
                      analytics_enabled=False, httpx_kwargs={'timeout': 60})
    except (httpx.HTTPError, OSError, ValueError) as error:
        raise RuntimeError('Cannot reach the DGX. Check Tailscale and the generation service, then try again.') from error


def wait_for_generation(job, progress):
    while not job.done():
        status = job.status()
        if status.progress_data:
            update = status.progress_data[-1]
            progress(update.progress, desc=update.desc)
        elif status.code == Status.IN_QUEUE:
            progress(None, desc='Waiting for the DGX')
        time.sleep(0.25)
    return job.result()


def generate_remote(request, progress):
    progress(0, desc='Sending inputs to the DGX')
    client = get_client()
    try:
        inputs = dict(request['inputs'])
        for name in ('photo', 'audio', 'reference'):
            if inputs.get(name):
                inputs[name] = handle_file(inputs[name])
        job = client.submit(**inputs, api_name=request['endpoint'])
        media_path, message = wait_for_generation(job, progress)
    except (httpx.HTTPError, OSError) as error:
        raise RuntimeError('The DGX connection failed. Check Tailscale and try again.') from error
    progress(1, desc='Downloaded to this Mac')
    return media_path, message
