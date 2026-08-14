FROM python:3.12-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libxcb1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir flake8 coverage

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . /workspace

WORKDIR /workspace/Pi_controler

COPY docker/entrypoint.sh /usr/local/bin/start-dashboard
RUN chmod +x /usr/local/bin/start-dashboard

EXPOSE 8000

CMD ["/usr/local/bin/start-dashboard"]
