FROM python:3.9-slim

WORKDIR /app



COPY requirements.txt .

# Install dependencies. Using --no-cache-dir keeps the image size smaller.
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user (Required by Hugging Face Spaces security policy)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Copy the entire ml-engine folder into the docker container
COPY --chown=user . $HOME/app

# Hugging Face exposes exactly port 7860
EXPOSE 7860

# Start Uvicorn on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
