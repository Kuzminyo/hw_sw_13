# Quotes to Scrape — Django (ДЗ #13, частина 2)

Аналог http://quotes.toscrape.com на Django + PostgreSQL. Продовження ДЗ #10.

## Що додано в ДЗ #13

* **Скидання пароля** для зареєстрованого користувача (вбудовані `PasswordReset*View` Django):
  1. на сторінці логіну посилання **Forgot password?** → `/users/password-reset/` — форма з email;
  2. на пошту приходить лист (текст + HTML) з одноразовим посиланням `/users/reset/<uid>/<token>/`;
  3. за посиланням — форма нового пароля з валідацією → `/users/reset/done/`.

  Посилання діє `PASSWORD_RESET_TIMEOUT` секунд і стає недійсним після зміни пароля. Для неіснуючого email показується та сама сторінка, щоб не розкривати, хто зареєстрований. Email при реєстрації тепер має бути унікальним, бо скидання шукає акаунт за email.
* **Усі змінні середовища у `.env`** і читаються в `settings.py`: `SECRET_KEY` (без запасного значення в коді), `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, Postgres, MongoDB, SMTP (`EMAIL_*`, `DEFAULT_FROM_EMAIL`), `PASSWORD_RESET_TIMEOUT`. Див. [.env.example](.env.example).

## Можливості (з ДЗ #10)

- Реєстрація, вхід, вихід (`/users/register/`, `/users/login/`).
- Додавання автора та цитати (з тегами) — лише для зареєстрованих користувачів.
- Перегляд усіх цитат і сторінок авторів — без автентифікації.
- Пошук за тегом (`/tag/<name>/`), блок **Top Ten tags**, пагінація Next / Previous.
- Скрапінг quotes.toscrape.com кнопкою на головній або `python manage.py scrape_quotes`.
- Міграція даних з MongoDB (ДЗ №9): `python manage.py migrate_from_mongo`.

## Запуск

```bash
pip install -r requirements.txt
cp .env.example .env          # підставте свої значення, згенеруйте SECRET_KEY
docker compose up -d          # Postgres + Mailpit
python manage.py migrate
python manage.py runserver
```

Листи для скидання пароля ловить Mailpit: http://localhost:8026. Для справжньої пошти вкажіть SMTP у `.env` (приклад для Gmail у `.env.example`), або `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`, щоб лист друкувався в терміналі.

Якщо `POSTGRES_DB` у `.env` порожній — використовується SQLite.

## Тести

```bash
python manage.py test
```