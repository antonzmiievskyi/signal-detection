FROM python:3.10-slim

WORKDIR /app

# Install deps as a cached layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code. In docker-compose the project root is bind-mounted over /app
# so this layer mainly serves standalone `docker run` invocations.
COPY scripts/ ./scripts/
COPY companies.json ./
COPY prospects.json ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "scripts/loop.py"]
