# Safar — production image (readme §15, Phase 3c). Runs the Streamlit app.
# Base app needs only requirements.txt; the optional prod extras (Postgres/Redis
# drivers) come from requirements-prod.txt so a plain build stays lean.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

# Install deps first for layer caching. Prod extras are optional — the base app
# runs on SQLite + in-process bus with no external services.
COPY requirements.txt requirements-prod.txt ./
RUN pip install -r requirements.txt -r requirements-prod.txt

COPY . .

# Non-root runtime user; owns the data dir so the SQLite fallback stays writable.
RUN useradd --create-home safar && mkdir -p /app/data && chown -R safar /app
USER safar

EXPOSE 8501

# Container healthcheck hits Streamlit's built-in endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8501/_stcore/health').status==200 else 1)"

CMD ["streamlit", "run", "app.py"]
