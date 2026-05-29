# Use official lightweight Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Set working directory inside container directly in the backend folder context
WORKDIR /app/backend

# Install system dependencies (needed for PDF processing and general system stability)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the rest of the backend files
COPY backend/ .

# Expose port
EXPOSE 7860

# Start FastAPI application using uvicorn from the backend working directory
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
