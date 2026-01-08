# Dockerfile for the Bot service
FROM python:3.11-slim

# Ensure output is unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
