import os

# До импорта приложения: lifespan не должен создавать sleeptrack.db в папке проекта.
os.environ.setdefault("SLEEPTRACK_DATABASE_URL", "sqlite://")
