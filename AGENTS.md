# Repository Guidelines

## Project structure

- `webui.py` and `clipboard.js` implement the local Gradio interface. `remote_client.py` transfers files and calls the DGX API.
- `backend.py` validates API requests. `engine.py` prepares media and coordinates speech and video generation.
- `speech.py` runs Chatterbox. `cosy_speech.py` runs CosyVoice in a separate Python environment.
- `tests/` contains automated checks. `patches/` holds changes to pinned upstream engines. `docs/SETUP.md` and `docs/API.md` describe installation and API usage.
- The ignored `runtime/` directory contains the upstream checkout, models, private media, and generated outputs. These assets are not bundled with this repository.

## Build, test, and development commands

Set `STUDIO_DIR` to the absolute checkout path. The Mac interface requires Python 3.14 and FFmpeg.

```bash
python3.14 -m venv "$STUDIO_DIR/.venv"
"$STUDIO_DIR/.venv/bin/python" -m pip install -r "$STUDIO_DIR/requirements-ui.txt"
MUSE_API_URL=http://your-dgx-host:7860 "$STUDIO_DIR/.venv/bin/python" "$STUDIO_DIR/webui.py"
```

These commands install and launch the local interface. Run the API tests with:

```bash
PYTHONPATH="$STUDIO_DIR" "$STUDIO_DIR/.venv/bin/python" -m unittest discover -s "$STUDIO_DIR/tests" -p test_remote_api.py -v
```

On the NVIDIA ARM64 server, follow `docs/SETUP.md` for prerequisite images, models, and configuration before building and starting the service:

```bash
docker build -f "$STUDIO_DIR/Dockerfile.cosyvoice" -t musetalk:cosyvoice "$STUDIO_DIR"
docker compose --env-file "$STUDIO_DIR/.env" -f "$STUDIO_DIR/compose.yaml" up -d
```

## Coding style

Use four-space indentation. Use `snake_case` for Python functions and variables, `PascalCase` for classes, and `UPPER_CASE` for constants. Match the JavaScript file's camelCase names and semicolons. No repository formatter or linter is configured. Check whitespace with `git diff --check`.

## Testing guidelines

Use `unittest`, `unittest.mock`, `test_*.py` files, and `test_*` methods. No coverage threshold is configured. Add behavioral checks for changed validation, file transfer, and media preparation.

Run voice-cloning tests in the UI environment, CosyVoice tests in `/opt/cosyvoice`, and mouth-blending tests in the inference environment. Follow the environment-specific commands in `docs/SETUP.md`. For UI or generation changes, verify upload, generation, playback, and download in a browser.

## Commits and pull requests

Use short imperative subjects, matching history such as `Add CosyVoice cloning and voice previews`. Keep changes focused. Describe the problem, resulting behavior, validation, and remaining limits. Link relevant issues and include redacted screenshots for UI changes. State checks that were not run. No CI workflow is configured.

## Configuration and privacy

Keep credentials, recordings, photos, outputs, and weights outside Git. Configure the Mac through environment variables and Compose through `.env`. Keep the unauthenticated API on localhost or a trusted private network. Preserve separate speech environments and the shared single-job queue. Leave unrelated model services unchanged.
