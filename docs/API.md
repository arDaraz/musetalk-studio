# Generation API

The DGX runs `backend.py` on port 7860. The local app uses Gradio's HTTP API for file uploads, queued jobs, progress, and downloads.
Use a private address or an SSH tunnel. The service has no authentication.

## Python client

Install `requirements-ui.txt`, then call the named endpoint. Files must exist on the client machine.

```python
from gradio_client import Client, handle_file

client = Client("http://your-dgx-host:7860", download_files="/absolute/path/to/results")
video, status = client.predict(
    photo=handle_file("/absolute/path/to/photo.png"),
    audio=handle_file("/absolute/path/to/audio.wav"),
    speech={"source": "audio"},
    api_name="/generate",
)
print(video, status)
```

For a script, set `audio=None` and pass `speech={"source": "script", "text": "Hello", "language": "en"}`.
Use `ar` for Arabic. Script mode uses the private reference voice already configured on the DGX.
The returned video path points to the downloaded file on the client.
Use `client.submit` and inspect the returned job's status for asynchronous progress, as `remote_client.py` does.

## HTTP requests

The installed service publishes its schema and client examples at `GET /gradio_api/info`.
The generation API uses this sequence:

1. Upload each file with `POST /gradio_api/upload` and multipart field `files`. The response is a list of server file paths.
2. Submit `POST /gradio_api/call/v2/generate` with the JSON object below. Replace the paths with the upload responses.
3. Read the returned `event_id`, then open `GET /gradio_api/call/generate/<event_id>` as a server-sent event stream.
4. On a `complete` event, download the URL in the returned file object. An `error` event means the job failed.

```json
{
  "photo": {"path": "<uploaded-photo-path>", "meta": {"_type": "gradio.FileData"}},
  "audio": {"path": "<uploaded-audio-path>", "meta": {"_type": "gradio.FileData"}},
  "speech": {"source": "audio"}
}
```

For scripts, send `null` for `audio` and use the script options described above.
Missing media, empty scripts, and unsupported source or language values return user-facing errors.
The service processes one generation at a time. Keep the connection open while the job runs.
A disconnected client can leave a job running on the server. Check the existing job before resubmitting a long generation.
