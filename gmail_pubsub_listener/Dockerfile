FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy service-specific requirements and install dependencies
COPY gmail_pubsub_listener/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY gmail_pubsub_listener/ ./gmail_pubsub_listener/
COPY common/ ./common/
COPY .env .env
COPY .secrets/ ./.secrets/

# Set Python path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Expose port (if you add a health check endpoint)
EXPOSE 8083

# Run the listener service
CMD ["python", "gmail_pubsub_listener/gmail_listener_service.py"]