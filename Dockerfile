FROM nvcr.io/nvidia/pytorch:25.11-py3
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-build-isolation --no-cache-dir 'numpy==1.26.4' 'diffusers==0.30.2' 'accelerate==0.28.0' 'transformers==4.39.2' 'huggingface_hub==0.30.2' 'opencv-python==4.9.0.80' 'soundfile==0.12.1' 'librosa==0.11.0' 'einops==0.8.1' omegaconf ffmpeg-python imageio gdown 'mmengine==0.10.7' 'mmdet==3.2.0' 'mmpose==1.3.2' chumpy
RUN MAX_JOBS=2 MMCV_WITH_OPS=1 pip install --no-build-isolation --no-cache-dir 'mmcv==2.1.0'
WORKDIR /workspace
CMD ["sleep", "infinity"]
