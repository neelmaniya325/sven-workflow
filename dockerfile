# Use official Python image from the Docker Hub
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV MISTRAL_API_KEY=${MISTRAL_API_KEY}
ENV MISTRAL_API_URL=${MISTRAL_API_URL}
ENV MISTRAL_MODEL=${MISTRAL_MODEL}

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install dependencies from the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code to the container
COPY . /app

# Expose port 8080 (or 8000 depending on your FastAPI config)
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
