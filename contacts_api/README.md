# Contacts REST API — ДЗ #13 (частина 1)

FastAPI + SQLAlchemy 2 + PostgreSQL + Alembic + Redis. Продовження ДЗ #12 (JWT авторизація).

Що додано в ДЗ #13:

| Вимога | Реалізація |
|---|---|
| Верифікація email | після `signup` на пошту приходить посилання `GET /api/auth/confirmed_email/{token}`; без підтвердження `login` → 401 `Email not confirmed`; повторно надіслати лист — `POST /api/auth/request_email` |
| Обмеження запитів | [slowapi](https://github.com/laurentS/slowapi), ліміти рахуються **для кожного користувача** (email з токена), сховище — Redis. Створення контакту — `RATE_LIMIT_CREATE_CONTACT` (5/хв), решта `/api/contacts/*` — `RATE_LIMIT_CONTACTS` (30/хв). Перевищення → 429 |
| Захист auth | `signup`, `login`, `request_email`, `forgot_password`, `reset_password` обмежені `RATE_LIMIT_AUTH` (5/хв з однієї IP) — від підбору паролів і спаму листами. `JWT_SECRET_KEY` обов'язковий, значення за замовчуванням у коді немає |
| CORS | `CORSMiddleware`, дозволені origin-и в `CORS_ORIGINS` |
| Аватар | `PATCH /api/users/avatar` (multipart, поле `file`), завантаження в Cloudinary, URL зберігається в `users.avatar` |
| *Кешування (Redis)* | `get_current_user` спочатку читає користувача з Redis (`user:<email>`, TTL `USER_CACHE_TTL_SECONDS`), інакше з БД і кладе в кеш. Пароль і refresh токен у кеш не потрапляють. Кеш скидається після зміни аватара, підтвердження email і скидання пароля |
| *Скидання пароля* | `POST /api/auth/forgot_password` → лист із посиланням на HTML-форму `GET /api/auth/reset_password/{token}` → `POST /api/auth/reset_password`. Токен живе 30 хв і одноразовий (прив'язаний до хешу старого пароля). Після скидання всі refresh токени відкликаються |

Усі секрети та налаштування — у `.env` (див. [.env.example](.env.example)), у коді їх немає.

## Запуск (Docker Compose)

```bash
cp .env.example .env          # змініть паролі, JWT_SECRET_KEY, додайте ключі Cloudinary
docker compose up -d --build
```

Піднімаються 4 сервіси: `postgres`, `redis`, `mailpit` (тестовий SMTP) і `app`. Міграції застосовуються автоматично.

* API / Swagger: http://127.0.0.1:8013/docs
* Листи (підтвердження, скидання пароля): http://127.0.0.1:8025 — Mailpit ловить усю пошту. Для справжньої пошти вкажіть SMTP у `.env` (приклад для Gmail там же).

## Локальний запуск без контейнера app

```bash
docker compose up -d postgres redis mailpit
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8013
```

## Ендпоінти

| Метод | Шлях | Опис | Статуси |
|---|---|---|---|
| POST | `/api/auth/signup` | реєстрація, надсилає лист підтвердження | 201, 409 |
| GET | `/api/auth/confirmed_email/{token}` | підтвердження email (посилання з листа) | 200, 400 |
| POST | `/api/auth/request_email` | надіслати лист підтвердження ще раз | 200 |
| POST | `/api/auth/login` | JSON `{email, password}` або форма → пара токенів | 200, 401 |
| GET | `/api/auth/refresh_token` | `Bearer <refresh_token>` → нова пара | 200, 401 |
| POST | `/api/auth/logout` | відкликає refresh токен | 204, 401 |
| POST | `/api/auth/forgot_password` | надіслати посилання для скидання пароля | 200 |
| GET | `/api/auth/reset_password/{token}` | HTML-форма нового пароля (з листа) | 200, 400 |
| POST | `/api/auth/reset_password` | `{token, new_password}` | 200, 400 |
| GET | `/api/users/me` | поточний користувач (з кешу Redis) | 200, 401 |
| PATCH | `/api/users/avatar` | новий аватар (multipart `file`, image/*, до 5 МБ) | 200, 401, 413, 415, 503 |
| GET | `/api/contacts/` | список, пошук `?first_name=&last_name=&email=`, `skip`, `limit` | 200, 429 |
| GET | `/api/contacts/birthdays?days=7` | дні народження на N днів | 200, 429 |
| GET | `/api/contacts/{id}` | один контакт | 200, 404, 429 |
| POST | `/api/contacts/` | створити контакт (**5 на хвилину**) | 201, 409, 429 |
| PUT | `/api/contacts/{id}` | оновити | 200, 404, 409, 429 |
| DELETE | `/api/contacts/{id}` | видалити | 204, 404, 429 |

`forgot_password` і `request_email` відповідають однаково для існуючих і неіснуючих адрес, щоб не можна було перевірити, хто зареєстрований.

Готові запити: [requests.http](requests.http).

## Структура

```
main.py                    FastAPI, CORS, rate limiter
src/conf/config.py         налаштування з .env
src/database/              підключення до БД, моделі User, Contact
src/repository/            запити до БД
src/services/auth.py       паролі, JWT (access/refresh/email/reset), get_current_user з кешем
src/services/cache.py      кеш користувача в Redis
src/services/email.py      надсилання листів через SMTP
src/services/upload.py     Cloudinary
src/services/limiter.py    slowapi: ліміт на користувача
src/routes/                auth, users, contacts
migrations/                Alembic
tests/                     pytest (SQLite в пам'яті, fakeredis, листи перехоплюються)
```

## Тести

```bash
pytest -q
```

Для тестів не потрібні ні PostgreSQL, ні Redis, ні SMTP, ні Cloudinary.