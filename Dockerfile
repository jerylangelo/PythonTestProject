FROM python:3.12-slim

WORKDIR /app

# No external dependencies needed.
COPY *.py ./
COPY .env* ./

# Create data directory
RUN mkdir -p data

# Default: run the main application
CMD ["python", "main.py"]
