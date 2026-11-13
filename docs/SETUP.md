# Setup

Set up the generation service on a Linux ARM64 NVIDIA GPU server with Docker Compose and NVIDIA container support. Then install the local Mac app below.

## Get the source

```bash
git clone https://github.com/arDaraz/musetalk-studio.git "$HOME/musetalk-studio"
export STUDIO_DIR="$HOME/musetalk-studio"
git clone https://github.com/TMElyralab/MuseTalk.git "$STUDIO_DIR/runtime"
git -C "$STUDIO_DIR/runtime" checkout 0a89dec45a0192b824e3cf4daf96c239440c5ed8
git -C "$STUDIO_DIR/runtime" apply --check --unidiff-zero "$STUDIO_DIR/patches/portrait-quality.patch"
git -C "$STUDIO_DIR/runtime" apply --unidiff-zero "$STUDIO_DIR/patches/portrait-quality.patch"
cp "$STUDIO_DIR/backend.py" "$STUDIO_DIR/engine.py" "$STUDIO_DIR/photo_detail.py" "$STUDIO_DIR/mouth_restore.py" "$STUDIO_DIR/speech.py" "$STUDIO_DIR/cosy_speech.py" "$STUDIO_DIR/runtime/"
```

The application uses `/workspace` inside the container. Compose mounts the runtime directory at that path.
The upstream checkout supplies `scripts/inference.py` and the `musetalk` package.
The patch makes `scripts/inference.py` call `photo_detail.py` and `mouth_restore.py` for a single photo, saves the face width for the status message, encodes the video at a higher quality, and keeps the encoded video stream when it adds audio. Apply it once to the pinned upstream revision.

## Build the images

```bash
docker build -f "$STUDIO_DIR/Dockerfile" -t musetalk:gx10 "$STUDIO_DIR"
docker build -f "$STUDIO_DIR/Dockerfile.web" -t musetalk:web "$STUDIO_DIR"
docker build -f "$STUDIO_DIR/Dockerfile.voice" -t musetalk:voice "$STUDIO_DIR"
docker build -f "$STUDIO_DIR/Dockerfile.cosyvoice" -t musetalk:cosyvoice "$STUDIO_DIR"
```

MMCV compilation can take time. The images keep video, web, Chatterbox, and CosyVoice dependencies in separate Python environments.
CosyVoice copies the tested Chatterbox environment before installing its own package versions. This reuses CUDA packages without modifying Chatterbox.
The CosyVoice source is pinned in `Dockerfile.cosyvoice`. Its audio patch uses SoundFile because TorchAudio 2.9 changed file decoding to TorchCodec.
ONNX reference-audio processing uses the CPU package. The speech model runs on the GPU with plain PyTorch.
The speech subprocess removes `LD_LIBRARY_PATH` so the base image's PyTorch libraries do not override its own CUDA libraries.
The package snapshot in `voice-requirements.lock` records the tested speech environment. The Dockerfile installs the dependencies, and some transitive versions are not pinned.

## Download the models

Start a temporary shell with the runtime directory mounted.

```bash
docker run --rm -it -v "$STUDIO_DIR/runtime:/workspace" musetalk:cosyvoice bash
```

Run these commands inside that container.

```bash
huggingface-cli download TMElyralab/MuseTalk --local-dir /workspace/models --include 'musetalkV15/*'
huggingface-cli download stabilityai/sd-vae-ft-mse --local-dir /workspace/models/sd-vae --include config.json diffusion_pytorch_model.bin
huggingface-cli download openai/whisper-tiny --local-dir /workspace/models/whisper --include config.json pytorch_model.bin preprocessor_config.json
huggingface-cli download yzd-v/DWPose --local-dir /workspace/models/dwpose --include dw-ll_ucoco_384.pth
mkdir -p /workspace/models/face-parse-bisent
gdown 154JgKpzCPW82qINcVieuPH3fZ2e0P812 -O /workspace/models/face-parse-bisent/79999_iter.pth
curl --fail -L https://download.pytorch.org/models/resnet18-5c106cde.pth -o /workspace/models/face-parse-bisent/resnet18-5c106cde.pth
mkdir -p /workspace/models/gfpgan
curl --fail -L https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth -o /workspace/models/gfpgan/GFPGANv1.4.pth
echo 'e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad  /workspace/models/gfpgan/GFPGANv1.4.pth' | sha256sum --check
/opt/voice/bin/hf download ResembleAI/chatterbox --revision 5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18 --local-dir /workspace/models/chatterbox --include ve.pt t3_mtl23ls_v3.safetensors s3gen.pt grapheme_mtl_merged_expanded_v1.json conds.pt Cangjie5_TC.json
/opt/cosyvoice/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', revision='29e01c4e8d000f4bcd70751be16fa94bf3d85a18', local_dir='/workspace/models/cosyvoice3', allow_patterns=['CosyVoice-BlankEN/*', 'cosyvoice3.yaml', 'campplus.onnx', 'speech_tokenizer_v3.onnx', 'llm.pt', 'flow.pt', 'hift.pt'])"
/opt/cosyvoice/bin/python -c "import whisper; whisper.load_model('base', device='cpu', download_root='/workspace/models/whisper-asr')"
exit
```

The Chatterbox source revision is pinned in `Dockerfile.voice`. MuseTalk model downloads use their repositories' default revisions.
Model hosts can require access approval or authentication under their own terms. Keep credentials outside the repository.

## Prepare a private reference voice

Copy a clear recording onto the server. Convert a clean segment of about 10 seconds to mono, 24 kHz WAV.
When the user uploads no reference, the code reads `voices/badr.wav`. The repository includes no recording.
Uploaded references apply to the current request and do not replace the saved voice.

```bash
mkdir -p "$STUDIO_DIR/runtime/voices"
chmod 700 "$STUDIO_DIR/runtime/voices"
ffmpeg -i /absolute/path/to/reference.m4a -t 10 -ac 1 -ar 24000 "$STUDIO_DIR/runtime/voices/badr.wav"
chmod 600 "$STUDIO_DIR/runtime/voices/badr.wav"
```

The conversion command requires FFmpeg on the host. The container also includes FFmpeg if you prefer to convert a mounted recording there.
Audio upload mode does not use the saved voice.

## Start the generation service

```bash
cp "$STUDIO_DIR/.env.example" "$STUDIO_DIR/.env"
```

Edit `.env` and set `MUSE_WORKSPACE` to the full runtime path, such as `/home/user/musetalk-studio/runtime`.
Keep `BIND_ADDRESS=127.0.0.1` for access through an SSH tunnel.
To use a private network directly, set it to the server's private interface address.

```bash
docker compose --env-file "$STUDIO_DIR/.env" -f "$STUDIO_DIR/compose.yaml" up -d
docker compose --env-file "$STUDIO_DIR/.env" -f "$STUDIO_DIR/compose.yaml" logs --tail 50 musetalk
```

For localhost binding, run this on the MacBook. Replace `user@server` with the SSH destination.

```bash
ssh -N -L 7861:127.0.0.1:7860 user@server
```

## Run the local Mac app

Install Python 3.14 and FFmpeg, then clone this repository on the Mac. Set `STUDIO_DIR` to that checkout.

```bash
export STUDIO_DIR="$HOME/musetalk-studio"
python3.14 -m venv "$STUDIO_DIR/.venv"
"$STUDIO_DIR/.venv/bin/python" -m pip install -r "$STUDIO_DIR/requirements-ui.txt"
export MUSE_API_URL="http://your-dgx-host:7860"
export GRADIO_ANALYTICS_ENABLED=False
"$STUDIO_DIR/.venv/bin/python" "$STUDIO_DIR/webui.py"
```

Use the DGX's private network address in `MUSE_API_URL`. With the SSH tunnel above, use `http://127.0.0.1:7861` instead.
The shell must be able to find FFmpeg. On Apple Silicon with Homebrew, include `/opt/homebrew/bin` in `PATH`.
The app reads environment variables directly. It does not load the Compose `.env` file.
Set `MUSE_UI_PORT` to change the local port from 7860.

For automatic startup, use a macOS user LaunchAgent with the venv Python and `webui.py` as its `ProgramArguments`.
Set `MUSE_API_URL`, `PATH`, and `GRADIO_ANALYTICS_ENABLED` in its `EnvironmentVariables`, with `RunAtLoad` and `KeepAlive` enabled.
The local app starts even when the DGX is offline. Generation shows a connection error until the service is reachable.

Open [the local page](http://127.0.0.1:7860) on the MacBook.
Upload a clear portrait, select an audio recording or enter a short script, and select **Generate video**.
Hover over either upload box before pasting media. Clicking the box still opens the file picker.

## Clone and preview a voice

Choose **Type a script**, then select **CosyVoice 3** or **Chatterbox** as the voice engine.
Use a clear recording between 3 and 30 seconds long with one speaker. Upload it under **Reference voice**, or leave the field empty to use the saved voice.
CosyVoice uses the first five seconds of the reference recording. Start the recording with clear speech. Longer prompts caused omitted or repeated words in testing.
The server transcribes that clip with Whisper base, then uses zero-shot inference at full precision. Enter only the new words in **Script**. No reference transcript is needed.
The first CosyVoice request downloads Whisper base to `models/whisper-asr` if it is missing. Recordings stay on the server. A reference with no recognized speech stops generation with an error.
Enter the new script, then select **Generate voice preview**. No photo is needed for an audio preview.
Play or download the generated audio. To make a talking video, upload a photo and select **Generate video**.
CosyVoice supports English in this app. Use Chatterbox for Arabic, which is outside CosyVoice's documented language list.
Reference uploads support the same hover-and-paste interaction as the other media boxes.

## Outputs and limits

Each server job writes to `results/web/<job-id>/`. The output video is `v15/video.mp4`.
The Mac downloads generated audio and videos to `~/Library/Application Support/MuseTalk Studio/results/`, or the directory in `MUSE_OUTPUT_DIR`.
The job directory also contains `render.log` and, for script mode, the submitted script, normalized reference recording, and generated speech.

Use the original full-resolution portrait with one visible face that looks at the camera, in even light, with the mouth closed and nothing over it.
The page lists these requirements, shows the photo dimensions, and flags images with a side smaller than 512 pixels.
Preparation preserves the RGB pixels of a photo whose shorter side is at least 720 pixels, adding at most one pixel of padding per side for video encoding.
Preparation enlarges a smaller photo by a whole factor until its shorter side is at least 720 pixels. The enlarged frame keeps more of the mouth that MuseTalk paints, but it adds no detail to the photo.
MuseTalk repaints the lower half of the face at 256 by 256 pixels, which softens beard and skin texture.
`photo_detail.py` measures how each part of the generated face moves and moves the photo detail with it. The beard, the skin, and the lips stay as sharp as the photo while the mouth moves.
`mouth_restore.py` sharpens the lips and the inside of the mouth with GFPGAN v1.4, loaded through `spandrel`. It uses only the fine detail of the restored face, and only where GFPGAN kept the shape of the mouth, so the mouth opening and the lip color stay as generated.
The restoration adds about 0.1 second for each video frame. The head does not move.
A face narrower than 256 pixels gives the model little mouth detail, so the lips look less exact. The status message then reports the face width and asks for a larger photo.
Start with a short clip to check memory use alongside other GPU services.
The interface does not impose a script length limit or delete old jobs automatically.
The queue allows one video job at a time, but other containers can still compete for GPU memory.

To update the server, copy `backend.py`, `engine.py`, `photo_detail.py`, `mouth_restore.py`, `speech.py`, and `cosy_speech.py` into the runtime directory and recreate only the Compose `musetalk` service.
To update the Mac, copy `webui.py`, `remote_client.py`, and `clipboard.js` into its app directory and restart the local process.
The upstream `entrypoint.sh` is not used. The container starts `/workspace/backend.py`.

## Verify the split and photo preparation

Run API boundary and connection-error checks on the Mac.

```bash
PYTHONPATH="$STUDIO_DIR" "$STUDIO_DIR/.venv/bin/python" -m unittest discover -s "$STUDIO_DIR/tests" -p test_remote_api.py -v
PYTHONPATH="$STUDIO_DIR" "$STUDIO_DIR/.venv/bin/python" -m unittest discover -s "$STUDIO_DIR/tests" -p test_voice_cloning.py -v
```

Run the checks in the web image with the upstream runtime and this repository mounted.

```bash
docker run --rm -v "$STUDIO_DIR/runtime:/workspace" -v "$STUDIO_DIR:/studio:ro" -w /studio -e PYTHONPATH=/studio musetalk:cosyvoice /opt/web/bin/python -m unittest discover -s /studio/tests -p test_photo_quality.py -v
```

The tests compare decoded RGB pixels with the original photo and check odd dimensions, large photos, and the small-image guidance.

Run the CosyVoice prompt tests in its speech environment.

```bash
docker run --rm -v "$STUDIO_DIR:/studio:ro" -e PYTHONPATH=/studio:/opt/CosyVoice:/opt/CosyVoice/third_party/Matcha-TTS musetalk:cosyvoice env -u LD_LIBRARY_PATH /opt/cosyvoice/bin/python -m unittest discover -s /studio/tests -p test_cosy_speech.py -v
```

Run the photo-detail and mouth-restoration tests in the inference environment.

```bash
docker run --rm -v "$STUDIO_DIR/runtime:/workspace" -v "$STUDIO_DIR:/studio:ro" -e PYTHONPATH=/studio musetalk:cosyvoice /usr/bin/python -m unittest discover -s /studio/tests -p test_photo_detail.py -v
docker run --rm -v "$STUDIO_DIR/runtime:/workspace" -v "$STUDIO_DIR:/studio:ro" -e PYTHONPATH=/studio musetalk:cosyvoice /usr/bin/python -m unittest discover -s /studio/tests -p test_mouth_restore.py -v
```

To upgrade an installation with an earlier portrait patch, rebuild the `musetalk:cosyvoice` image, download the GFPGAN weights as shown above, and copy the server files. Then restore the two upstream files, apply the current patch, and recreate the service.

```bash
git -C "$STUDIO_DIR/runtime" checkout 0a89dec45a0192b824e3cf4daf96c239440c5ed8 -- scripts/inference.py musetalk/utils/face_parsing/__init__.py
git -C "$STUDIO_DIR/runtime" apply --check --unidiff-zero "$STUDIO_DIR/patches/portrait-quality.patch"
git -C "$STUDIO_DIR/runtime" apply --unidiff-zero "$STUDIO_DIR/patches/portrait-quality.patch"
```

If the patch check reports a mismatch, inspect the upstream revision and whether the patch is already present.
