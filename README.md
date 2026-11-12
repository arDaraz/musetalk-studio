# MuseTalk Studio

Generate a talking portrait from a photo and audio, or type a script and use a saved voice sample.
The web app runs locally on your MacBook. It calls the NVIDIA server over HTTP to generate speech and video.

## What the page does

- Upload a photo and an audio recording. The page shows photo dimensions and flags small images.
- Paste a photo or audio file from the clipboard. Hover over the target box, then press Command+V or Ctrl+V.
- Show a purple outline when a media box has hover or focus.
- Replace an uploaded file by pasting another file.
- Generate English or Arabic speech from a script with Chatterbox Multilingual and a private reference recording.
- Generate a MuseTalk v1.5 video, show progress, and provide playback and download.

Clipboard support depends on the browser providing an actual media file. Pasted text and file paths do not upload a file.

## Read the code

| File | Purpose |
| --- | --- |
| [webui.py](webui.py) | Local Gradio page, clipboard controls, photo guidance, and CSS. |
| [remote_client.py](remote_client.py) | Uploads inputs to the server, forwards progress, and downloads finished videos. |
| [backend.py](backend.py) | Queued generation API and speech-option validation. |
| [engine.py](engine.py) | Server media preparation, speech subprocess, and video generation. |
| [clipboard.js](clipboard.js) | Clipboard uploads, file replacement, and focus on hover. |
| [patches/portrait-quality.patch](patches/portrait-quality.patch) | Preserves the beard outside the mouth region and avoids duplicate video encoding. |
| [speech.py](speech.py) | Script splitting and speech generation from a saved voice. |
| [Dockerfile](Dockerfile) | MuseTalk inference dependencies for the NVIDIA ARM64 server. |
| [Dockerfile.web](Dockerfile.web) | Separate Gradio environment. |
| [Dockerfile.voice](Dockerfile.voice) | Separate Chatterbox environment with CUDA 13 PyTorch. |
| [compose.yaml](compose.yaml) | GPU container, network binding, memory limit, and local storage. |
| [voice-requirements.lock](voice-requirements.lock) | Installed speech package versions from the tested server, for reference. |

The video engine comes from [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk).
The speech engine comes from [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox).
This repository contains the custom interface and deployment files. It does not include the upstream engines, model weights, or personal media.

## Run it

See [setup](docs/SETUP.md) for the DGX service and local Mac app. See [API usage](docs/API.md) to call the service from another client.
The tested system is an ARM64 NVIDIA GB10 machine with 128 GB unified memory.
The local app needs Python and FFmpeg. The model containers require a Linux NVIDIA GPU server.

Qwen and vLLM are separate services. This application does not call them or change their containers.
It processes one video job at a time. Speech generation finishes before MuseTalk loads, which reduces concurrent model memory use.
The Docker memory limit does not reserve or isolate GPU memory.

## Data and access

The local app temporarily caches uploads, then sends the selected photo and audio or script to the configured server.
The server retains render logs, scripts, generated speech, and videos under `results/web/`.
The local app downloads finished videos to `~/Library/Application Support/MuseTalk Studio/results/`.
Set `MUSE_OUTPUT_DIR` to choose another download directory. Neither service deletes old job output automatically.
Initial model or tokenizer downloads can access external model hosts.

The local page binds to `127.0.0.1`. The generation API has no login and the Compose example also binds to localhost by default.
Connect the Mac through an SSH tunnel or a trusted private network such as Tailscale.
Keep private recordings and generated output outside Git.

## Verification

The deployed source was tested with photo and audio uploads, native Mac clipboard paste, file replacement, hover focus, and video downloads.
English and Arabic script generation also produced playable videos while a separate vLLM service remained running.
The split deployment also has API validation and file-transfer tests. Run instructions are in the setup guide.
A clean installation from this repository has not yet been tested.

## Third-party terms

MuseTalk, Chatterbox, the NVIDIA base image, and downloaded models retain their own licenses and terms.
Review the upstream terms before redistributing those components or their weights.
