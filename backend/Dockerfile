FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.prod
WORKDIR /app

RUN useradd --create-home --uid 1000 app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .
RUN chown -R app:app /app
USER app

EXPOSE 8000
# Overridden by the worker and beat services in docker-compose.yml.
CMD ["./docker-entrypoint.sh"]
