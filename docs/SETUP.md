# Server setup

These steps reproduce the layout used by the running interface. Run them on a Linux ARM64 NVIDIA GPU server with Docker Compose and NVIDIA container support.

## Get the source

```bash
git clone https://github.com/arDaraz/musetalk-studio.git "$HOME/musetalk-studio"
export STUDIO_DIR="$HOME/musetalk-studio"
git clone https://github.com/TMElyralab/MuseTalk.git "$STUDIO_DIR/runtime"
git -C "$STUDIO_DIR/runtime" checkout 0a89dec45a0192b824e3cf4daf96c239440c5ed8
git -C "$STUDIO_DIR/runtime" apply --check --unidiff-zero "$STUDIO_DIR/patches/inference-video-copy.patch"
git -C "$STUDIO_DIR/runtime" apply --unidiff-zero "$STUDIO_DIR/patches/inference-video-copy.patch"
cp "$STUDIO_DIR/webui.py" "$STUDIO_DIR/clipboard.js" "$STUDIO_DIR/speech.py" "$STUDIO_DIR/runtime/"
```

The application uses `/workspace` inside the container. Compose mounts the runtime directory at that path.
The upstream checkout supplies `scripts/inference.py` and the `musetalk` package.
The patch preserves the encoded video stream when adding audio. Apply it once to the pinned upstream revision.

## Build the images

```bash
docker build -f "$STUDIO_DIR/Dockerfile" -t musetalk:gx10 "$STUDIO_DIR"
docker build -f "$STUDIO_DIR/Dockerfile.web" -t musetalk:web "$STUDIO_DIR"
docker build -f "$STUDIO_DIR/Dockerfile.voice" -t musetalk:voice "$STUDIO_DIR"
```

MMCV compilation can take time. The three images keep the inference, web, and speech dependencies separate.
The speech subprocess removes `LD_LIBRARY_PATH` so the base image's PyTorch libraries do not override its own CUDA libraries.
The package snapshot in `voice-requirements.lock` records the tested speech environment. The Dockerfile installs the dependencies, and some transitive versions are not pinned.

## Download the models

Start a temporary shell with the runtime directory mounted.

```bash
docker run --rm -it -v "$STUDIO_DIR/runtime:/workspace" musetalk:voice bash
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
/opt/voice/bin/hf download ResembleAI/chatterbox --revision 5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18 --local-dir /workspace/models/chatterbox --include ve.pt t3_mtl23ls_v3.safetensors s3gen.pt grapheme_mtl_merged_expanded_v1.json conds.pt Cangjie5_TC.json
exit
```

The Chatterbox source revision is pinned in `Dockerfile.voice`. MuseTalk model downloads use their repositories' default revisions.
Model hosts can require access approval or authentication under their own terms. Keep credentials outside the repository.

## Prepare a private reference voice

Copy a clear recording onto the server. Convert a clean segment of about 10 seconds to mono, 24 kHz WAV.
The current code reads `voices/badr.wav`. This is a fixed filename, and the repository includes no recording.

```bash
mkdir -p "$STUDIO_DIR/runtime/voices"
chmod 700 "$STUDIO_DIR/runtime/voices"
ffmpeg -i /absolute/path/to/reference.m4a -t 10 -ac 1 -ar 24000 "$STUDIO_DIR/runtime/voices/badr.wav"
chmod 600 "$STUDIO_DIR/runtime/voices/badr.wav"
```

The conversion command requires FFmpeg on the host. The container also includes FFmpeg if you prefer to convert a mounted recording there.
Audio upload mode does not use the saved voice.

## Start the page

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
ssh -N -L 7860:127.0.0.1:7860 user@server
```

Open [the local page](http://127.0.0.1:7860) on the MacBook.
Upload a clear portrait, select an audio recording or enter a short script, and select **Generate video**.
Hover over either upload box before pasting media. Clicking the box still opens the file picker.

## Outputs and limits

Each job writes to `results/web/<job-id>/`. The output video is `v15/video.mp4`.
The job directory also contains `render.log` and, for script mode, the submitted script and generated speech.

Use the original full-resolution portrait with one visible face. The page shows its dimensions and flags images with a side smaller than 512 pixels.
Preparation preserves RGB pixels and image dimensions, adding at most one pixel of padding per side for video encoding.
MuseTalk still generates a 256 by 256 face region, so a larger photo cannot remove every mouth or beard artifact.
Start with a short clip to check memory use alongside other GPU services.
The interface does not impose a script length limit or delete old jobs automatically.
The queue allows one video job at a time, but other containers can still compete for GPU memory.

To update the interface, copy the three application files into the runtime directory and restart only the Compose `musetalk` service.
The upstream `entrypoint.sh` is not used. `Dockerfile.web` starts `/workspace/webui.py` directly.

## Verify photo preparation

Run the checks in the web image with the upstream runtime and this repository mounted.

```bash
docker run --rm -v "$STUDIO_DIR/runtime:/workspace" -v "$STUDIO_DIR:/studio:ro" -w /studio -e PYTHONPATH=/studio musetalk:voice /opt/web/bin/python -m unittest discover -s /studio/tests -v
```

The tests compare decoded RGB pixels with the original photo and check odd dimensions, large photos, and the small-image guidance.
For an existing installation, apply the inference patch before restarting the web service. If the patch check reports a mismatch, inspect the upstream revision and whether the patch is already present.
