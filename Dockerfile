FROM --platform=linux/amd64 python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OCR_DEVICE=cpu

WORKDIR /srv/pure-ai
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
