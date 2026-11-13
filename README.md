# MuseTalk Studio

Generate a talking portrait from a photo and audio, or type a script and use a saved voice sample.
The web app runs locally on your MacBook. It calls the NVIDIA server over HTTP to generate speech and video.

## What the page does

- Guide you through four steps: Photo, Voice, Script, and Video. A side panel shows your choices and tips for the current step.
- Upload a photo. The page shows photo dimensions and flags small images.
- Choose the speech source. A cloned voice reads a typed script, and the video uses an uploaded recording as it is. A recording skips the Script step.
- Stop you at a step, with a warning, when it is missing a photo, a recording, or a script.
- Paste a photo or audio file from the clipboard. Hover over the target box, then press Command+V or Ctrl+V.
- Show a teal outline when a media box has hover or focus.
- Replace an uploaded file by pasting another file.
- Clone a voice with CosyVoice 3 for English, or Chatterbox for English and Arabic.
- Use the saved voice or clone a reference recording. Preview and download the speech before making a video.
- Show the script length and estimated speech duration. Flag a voice preview that no longer matches the script or voice.
- Generate a MuseTalk v1.5 video, show progress, and provide playback and download.
- Keep each video from the session as a take, and switch between takes.

Clipboard support depends on the browser providing an actual media file. Pasted text and file paths do not upload a file.

## Read the code

| File | Purpose |
| --- | --- |
| [webui.py](webui.py) | Local Gradio page: the four-step flow, clipboard controls, photo guidance, voice previews, and takes. |
| [studio.css](studio.css) | Page layout, stepper, step card, side panel, choice cards, and the video stage. |
| [remote_client.py](remote_client.py) | Uploads inputs to the server, forwards progress, and downloads finished videos. |
| [backend.py](backend.py) | Queued generation API and speech-option validation. |
| [engine.py](engine.py) | Server media preparation, speech subprocess, and video generation. |
| [clipboard.js](clipboard.js) | Clipboard uploads, file replacement, and focus on hover. |
| [patches/portrait-quality.patch](patches/portrait-quality.patch) | Preserves the beard outside the mouth region and avoids duplicate video encoding. |
| [speech.py](speech.py) | Chatterbox speech generation from a reference voice. |
| [cosy_speech.py](cosy_speech.py) | CosyVoice speech generation with automatic reference transcription. |
| [Dockerfile.cosyvoice](Dockerfile.cosyvoice) | Isolated CosyVoice environment on the NVIDIA ARM64 server. |
| [Dockerfile](Dockerfile) | MuseTalk inference dependencies for the NVIDIA ARM64 server. |
| [Dockerfile.web](Dockerfile.web) | Separate Gradio environment. |
| [Dockerfile.voice](Dockerfile.voice) | Separate Chatterbox environment with CUDA 13 PyTorch. |
| [compose.yaml](compose.yaml) | GPU container, network binding, memory limit, and local storage. |
| [voice-requirements.lock](voice-requirements.lock) | Installed speech package versions from the tested server, for reference. |

The video engine comes from [TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk).
The speech engines come from [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) and [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice).
This repository contains the custom interface and deployment files. It does not include the upstream engines, model weights, or personal media.

## Run it

See [setup](docs/SETUP.md) for the DGX service and local Mac app. See [API usage](docs/API.md) to call the service from another client.
The tested system is an ARM64 NVIDIA GB10 machine with 128 GB unified memory.
The local app needs Python and FFmpeg. The model containers require a Linux NVIDIA GPU server.

Qwen and vLLM are separate services. This application does not call them or change their containers.
It processes one video job at a time. Speech generation finishes before MuseTalk loads, which reduces concurrent model memory use.
The Docker memory limit does not reserve or isolate GPU memory.

## Data and access

The local app temporarily caches uploads, then sends the selected photo, reference recording, and audio or script to the configured server.
The server retains reference recordings, render logs, scripts, generated speech, and videos under `results/web/`.
The local app downloads generated audio and videos to `~/Library/Application Support/MuseTalk Studio/results/`.
Set `MUSE_OUTPUT_DIR` to choose another download directory. Neither service deletes old job output automatically.
Initial model or tokenizer downloads can access external model hosts.

The local page binds to `127.0.0.1`. The generation API has no login and the Compose example also binds to localhost by default.
Connect the Mac through an SSH tunnel or a trusted private network such as Tailscale.
Keep private recordings and generated output outside Git.

## Verification

The deployed source was tested with photo and audio uploads, native Mac clipboard paste, file replacement, hover focus, and video downloads.
English and Arabic script generation also produced playable videos while a separate vLLM service remained running.
CosyVoice cloning was verified through the local page with an uploaded reference, audio playback, video generation, and reference clipboard paste.
A browser check covered the four-step flow against the DGX: a voice preview, a video, another take, the recording path that skips the Script step, and the warnings for missing inputs.
API validation, reference-duration boundaries, and file-transfer tests also passed. Run instructions are in the setup guide.
A clean installation from this repository has not yet been tested.

## Third-party terms

MuseTalk, Chatterbox, CosyVoice, the NVIDIA base image, and downloaded models retain their own licenses and terms.
Review the upstream terms before redistributing those components or their weights.
