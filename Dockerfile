FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    requests \
    openai \
    google-api-python-client \
    google-auth \
    pypdf \
    pillow \
    pillow-heif

COPY app/ /app/

CMD ["python", "main.py"]
