# API SleepTrack: FastAPI + SQLAlchemy. Фронтенд собирается отдельно — frontend/Dockerfile.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Зависимости отдельным слоем — при правках кода pip install не повторяется.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY sleep_tracker ./sleep_tracker

# Не запускаем сервер от root.
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "sleep_tracker.main:app", "--host", "0.0.0.0", "--port", "8000"]
