FROM python:3.12-slim

# Set timezone environment variable
ENV TZ=Asia/Phnom_Penh

# Install minimal build tools + tzdata
RUN apt-get update && apt-get install -y \
    build-essential \
    tzdata \
    --no-install-recommends \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose Flask port
EXPOSE 5000

# Run Flask app via Gunicorn
CMD ["gunicorn", "-w", "4", "-k", "gthread", "-t", "60", "-b", "0.0.0.0:5000", "app:create_app()"]
