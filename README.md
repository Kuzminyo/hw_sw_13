# ДЗ #13 — Python Web

| Частина | Папка | Що зроблено |
|---|---|---|
| 1. REST API (FastAPI, продовження ДЗ #12) | [contacts_api/](contacts_api/README.md) | верифікація email, rate limit (створення контактів — 5/хв на користувача), CORS, аватар у Cloudinary, кеш поточного користувача в Redis, скидання пароля, усе в Docker Compose |
| 2. Django (продовження ДЗ #10) | [quotes_django/](quotes_django/README.md) | скидання пароля через email, усі налаштування з `.env` у `settings.py`, Django + PostgreSQL + Mailpit у Docker Compose |

Швидкий старт:

```bash
cd contacts_api && cp .env.example .env && docker compose up -d --build
# Swagger: http://127.0.0.1:8013/docs, пошта: http://127.0.0.1:8025

cd quotes_django && cp .env.example .env && docker compose up -d --build
# сайт: http://127.0.0.1:8000, пошта: http://127.0.0.1:8026
```