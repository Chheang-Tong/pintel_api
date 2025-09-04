
FROM python:3.12-slim

# System deps (only if you need to compile wheels)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app (used in prod; in dev you bind-mount over it)
COPY . .

# Default command is prod-safe; dev overrides with compose `command:`
CMD ["gunicorn", "-w", "4", "-k", "gthread", "-t", "60", "-b", "0.0.0.0:5000", "app:create_app()"]