FROM python:3.11-slim

# Prevents Python from writing pyc files and ensures logs show up immediately
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1


# Set working directory
WORKDIR /app

# Install dependencies first (for faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else, including static + templates
COPY . .

# ✅ Explicitly copy static assets (this guarantees your /static/js/ files are inside the container)
COPY static ./static
COPY templates ./templates

# Expose port 8080 for Cloud Run
ENV PORT=8080
EXPOSE 8080

# Run with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
