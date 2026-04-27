FROM python:3.11-slim

# Install system dependencies for ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install fastapi uvicorn python-multipart

COPY . .

# Expose web UI port
EXPOSE 8080

CMD ["python", "web_server.py"]
