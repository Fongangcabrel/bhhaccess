# BHH Access API. Same Python as the development .venv (3.14).
FROM python:3.14-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencies first (cached layer): WHAT to install comes from pyproject.toml (single list),
# the exact versions from requirements.lock (the ones the tests pass with).
COPY pyproject.toml requirements.lock ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" \
        > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt -c requirements.lock \
    && rm /tmp/requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY assets ./assets
COPY app ./app
RUN useradd -r app && mkdir -p /data/photos && chown -R app /srv /data/photos
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
