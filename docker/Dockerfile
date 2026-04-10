FROM python:3.13-slim

# Install LibreOffice and required dependencies for PDF handling
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libreoffice \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Create non-root user for security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose Streamlit port
EXPOSE 8501

# Health check - verify Streamlit is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501').read()" || exit 1

# Run Streamlit with explicit configuration
CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--logger.level=info"]
