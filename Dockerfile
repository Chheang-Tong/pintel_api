
# FROM python:3.12-slim

# # System deps (only if you need to compile wheels)
# RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# # Install deps first to leverage cache
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy app (used in prod; in dev you bind-mount over it)
# COPY . .

# # Default command is prod-safe; dev overrides with compose `command:`
# CMD ["gunicorn", "-w", "4", "-k", "gthread", "-t", "60", "-b", "0.0.0.0:5000", "app:create_app()"]
# Use official Python 3.12 slim image
# Use Python 3.12 slim
FROM python:3.12-slim

# Install only minimal build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Flask port
EXPOSE 5000

# Run Flask app via Gunicorn
CMD ["gunicorn", "-w", "4", "-k", "gthread", "-t", "60", "-b", "0.0.0.0:5000", "app:create_app()"]

