# Stage 1: Build environment with CUDA
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04 as builder

ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    build-essential ninja-build libgl-dev \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Install Python dependencies
ENV TORCH_CUDA_ARCH_LIST="3.5;5.0;6.0;6.1;7.0;7.5;8.0;8.6+PTX"
RUN pip install --user torch torchvision --index-url https://download.pytorch.org/whl/cu118 \
    && pip install --user submodules/diff-gaussian-rasterization submodules/simple-knn --no-build-isolation \
    && pip install --user -r requirements.txt \
    && python -m pip cache purge

# Stage 2: Runtime environment
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip libgl1 ffmpeg colmap imagemagick \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages and binaries from builder
COPY --from=builder /root/.local/lib/python3.10/site-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /root/.local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]