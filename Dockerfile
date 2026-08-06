FROM python:3.14-slim

WORKDIR /workspace

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install flake8 coverage

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . /workspace

WORKDIR /workspace/Pi_controler
