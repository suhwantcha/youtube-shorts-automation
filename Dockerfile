FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk fontconfig \
    && fc-cache -f && rm -rf /var/lib/apt/lists/*
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY tech_shorts ./tech_shorts
ENV PYTHONUNBUFFERED=1 SHORTS_OUTPUT_DIR=/tmp/shorts/jobs
EXPOSE 8080
CMD ["python", "-m", "tech_shorts", "serve", "--host", "0.0.0.0"]
