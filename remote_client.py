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


def generate_remote(photo, audio, speech, progress):
    progress(0, desc='Sending inputs to the DGX')
    client = get_client()
    try:
        job = client.submit(handle_file(photo) if photo else None,
                            handle_file(audio) if audio else None,
                            speech, api_name='/generate')
        while not job.done():
            status = job.status()
            if status.progress_data:
                update = status.progress_data[-1]
                progress(update.progress, desc=update.desc)
            elif status.code == Status.IN_QUEUE:
                progress(None, desc='Waiting for the DGX')
            time.sleep(0.25)
        video_path, message = job.result()
    except (httpx.HTTPError, OSError) as error:
        raise RuntimeError('The DGX connection failed. Check Tailscale and try again.') from error
    progress(1, desc='Video downloaded to this Mac')
    return video_path, message
