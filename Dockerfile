# Stage 1: Build environment with CUDA
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04 AS builder

ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev python-is-python3 \
    build-essential ninja-build libgl-dev git cmake curl ca-certificates \
    libboost-program-options-dev libboost-graph-dev libboost-system-dev libeigen3-dev libflann-dev \
    libfreeimage-dev libmetis-dev libgoogle-glog-dev libgtest-dev libgmock-dev libsqlite3-dev \
    libglew-dev qtbase5-dev libqt5opengl5-dev libcgal-dev libceres-dev gcc-10 g++-10 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --user torch torchvision --index-url https://download.pytorch.org/whl/cu118 

WORKDIR /app

COPY submodules submodules

ENV TORCH_CUDA_ARCH_LIST="3.5;5.0;6.0;6.1;7.0;7.5;8.0;8.6+PTX"
RUN pip install --user submodules/diff-gaussian-rasterization submodules/simple-knn --no-build-isolation 

# Устанавливаем GCC-10 как компилятор для совместимости с CUDA
ENV CC=/usr/bin/gcc-10
ENV CXX=/usr/bin/g++-10
ENV CUDAHOSTCXX=/usr/bin/g++-10

# Клонируем репозиторий COLMAP и компилируем
RUN git clone https://github.com/colmap/colmap.git /colmap
WORKDIR /colmap
RUN mkdir build && cd build \
    && cmake .. -DCUDA_ENABLED=ON -DCMAKE_CUDA_ARCHITECTURES="70;72;75;80;86" -GNinja \
    && ninja \
    && ninja install

COPY requirements.txt .

# Install Python dependencies
RUN pip install --user -r requirements.txt \
    && python -m pip cache purge


# Stage 2: Runtime environment
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python-is-python3 colmap libcurl4 libboost-program-options-dev\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


# Copy Python packages and binaries from builder
COPY --from=builder /root/.local/lib/python3.10/site-packages /usr/local/lib/python3.10/dist-packages
COPY --from=builder /root/.local/bin /usr/local/bin

# Копируем скомпилированные бинарники и библиотеки из этапа builder
COPY --from=builder /usr/local/bin/colmap /usr/local/bin/colmap
COPY --from=builder /usr/local/lib/libcolmap* /usr/local/lib/
COPY --from=builder /usr/local/share/colmap /usr/local/share/colmap

# Добавляем библиотеки CUDA (минимальный runtime)
COPY --from=builder /usr/local/cuda/lib64/libcudart_static.a /usr/local/cuda/lib64/libcudart_static.a
COPY --from=builder /usr/local/cuda/lib64/libcudart.so	/usr/local/cuda/lib64/libcudart.so
COPY --from=builder /usr/local/cuda/lib64/libcudart.so.11.0 /usr/local/cuda/lib64/libcudart.so.11.0
COPY --from=builder /usr/local/cuda/lib64/libcudart.so.11.8.89	/usr/local/cuda/lib64/libcudart.so.11.8.89
#COPY --from=builder /usr/local/cuda/lib64/libcublas.so.11 /usr/local/cuda/lib64/libcublas.so.11
#COPY --from=builder /usr/local/cuda/lib64/libcudnn.so.8 /usr/local/cuda/lib64/libcudnn.so.8


# Настройте переменные окружения для CUDA и библиотек
ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/local/cuda/lib64:$LD_LIBRARY_PATH
ENV PATH=/usr/local/cuda/bin:$PATH

COPY . .

# Install Python dependencies
#RUN pip install --user -r requirements.txt \
#    && python -m pip cache purge

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout","3600", "app:app"]
#CMD ["python", "app.py"]