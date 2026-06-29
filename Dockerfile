FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3.10 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY fonts/ fonts/
COPY pyproject.toml .
COPY README.md .

RUN pip3 install --no-cache-dir -e ".[dev]"

ENTRYPOINT ["opusclip"]
CMD ["--help"]
