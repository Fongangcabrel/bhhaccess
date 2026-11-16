FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml .
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]" "sqlalchemy>=2.0" alembic \
    psycopg2-binary pydantic-settings "pyjwt[crypto]" cryptography argon2-cffi \
    python-multipart openpyxl qrcode pillow tzdata "reportlab>=4.4"
COPY app ./app
COPY assets ./assets
COPY migrations ./migrations
COPY alembic.ini .
RUN useradd -r app && mkdir -p /data/photos && chown -R app /srv /data/photos
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000"]
