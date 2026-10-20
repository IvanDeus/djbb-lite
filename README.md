# DJBB-lite: Django Bulletin Board

A deliberately small bulletin board built with Django — read it as a working reference for
models, class-less function views, `ModelForm`s, and session auth, with nothing extra in the way.

There is no Bootstrap, no DRF, no Celery, no migrations beyond the initial one. SQLite and
Django's own auth are the whole stack.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Django](https://img.shields.io/badge/django-6.1-green)

## Features

- **Posts** — title + body, newest first, on the index page.
- **Comments** — threaded under each post, created by logged-in users.
- **Author-only editing** — you can edit or delete your own posts.
- **Staff override** — staff users can edit or delete *anyone's* post.
- **Django admin** — posts and comments are registered and manageable at `/admin/`.
- **Anonymous read access** — browsing needs no account; writing does.
- **Self-registration** — new users can sign up with username, email, and password (min 6 chars).

## Requirements

- Python 3.12+
- Django 6.1

```bash
pip install "django>=6.1"
```

## Quick start

```bash
# from the repository root
python manage.py migrate

# create the two test accounts (see table below)
python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.create_user('user', password='zxc123')
a = User.objects.create_superuser('admin', password='pass123')
"

python manage.py runserver 0.0.0.0:7111
```

Then open <http://127.0.0.1:7111/>.

> `create_user` / `create_superuser` set the password directly. The plain `manage.py
> createsuperuser` wizard would reject these two passwords through Django's built-in
> validators (too short, too common) — that is expected, not a bug in the project.

## Test accounts

| Username | Password | Type    | Can                                              |
| -------- | -------- | ------- | ------------------------------------------------ |
| `admin`  | `pass123` | staff   | Everything, plus `/admin/` and other users' posts |
| `user`    | `zxc123` | regular | Own posts only, no `/admin/`                      |

These are seeded for manual testing only. They are weak by design — do not run this instance
somewhere reachable from the internet.

## Routes

| Method     | Path                     | View             | Notes                              |
| ---------- | ------------------------ | ---------------- | ---------------------------------- |
| `GET`      | `/`                      | `post_list`      | Public                             |
| `GET`      | `/post/<pk>/`            | `post_detail`    | Public; comment form if logged in  |
| `GET/POST` | `/post/new/`             | `post_create`    | Login required                     |
| `GET/POST` | `/post/<pk>/edit/`       | `post_update`    | Author or staff                    |
| `GET/POST` | `/post/<pk>/delete/`     | `post_delete`    | Author or staff                    |
| `GET/POST` | `/login/`                | Django `LoginView` |                                   |
| `GET/POST` | `/signup/`               | `signup`         | New user registration              |
| `POST`     | `/logout/`               | Django `LogoutView` | POST only, as of Django 5        |
| `*`        | `/admin/`                | Django admin     | Staff only                         |

## Permissions model

One helper in `board/views.py` decides everything:

```python
def _can_manage(user, post):
    return user.is_staff or post.author_id == user.pk
```

Users who fail the check are redirected to the post rather than shown a 403, so the edit and
delete URLs do not leak which post IDs exist versus which are simply yours.

## Project layout

```
.
├── board/
│   ├── forms.py                      # PostForm, CommentForm, RegistrationForm
│   ├── models.py                     # Post, Comment
│   ├── views.py                      # list, detail, create, update, delete, signup
│   ├── admin.py
│   └── templates/
│       ├── base.html                 # header, nav, inline CSS
│       ├── board/                    # post_list, post_detail, post_form, post_confirm_delete
│       └── registration/             # login.html, signup.html
├── config/
│   ├── settings.py                   # SQLite, board app, login redirects
│   └── urls.py
├── db.sqlite3
└── manage.py
```

Both models are three fields plus a timestamp; `Comment` has a `related_name='comments'` so
templates iterate `post.comments.all` directly.

## Configuration

Everything lives in `config/settings.py`. The parts worth knowing about:

- `DATABASES` — SQLite file at `BASE_DIR / 'db.sqlite3'`. Delete the file for a clean slate.
- `DEBUG = True` and `ALLOWED_HOSTS = ['*']` — development posture, bound to all interfaces.
- `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL` — auth flow lands back on the index.

## Running in production

The repo is in development posture on purpose: `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, a
`SECRET_KEY` committed to the file, the console email backend, and two weak seeded accounts.
None of that survives a real host. Everything below is additive — leave `config/settings.py`
for local work and add an overlay module that production loads instead.

### 1. Settings overlay

```python
# config/settings_prod.py
import os

from .settings import *  # noqa: F403  (BASE_DIR comes in with the star-import)

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]   # never a literal in a file
ALLOWED_HOSTS = ["board.example.com"]          # exact hosts, no wildcard
STATIC_ROOT = BASE_DIR / "staticfiles"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 15        # raise it only once TLS is proven
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # TLS ends at the proxy
```

The key in `config/settings.py` is public the moment this repo is, so generate a fresh one:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

If `POST` starts returning 403 after the proxy rewrites `Host`, add the public origin to
`CSRF_TRUSTED_ORIGINS`. Nothing else about CSRF needs touching — every form here already
carries `{% csrf_token %}`.

### 2. Serve it with a real server

`runserver` is a development tool and must not be what faces the network. `config/asgi.py`
already exposes an ASGI application, so uvicorn is the smallest thing that runs it:

```bash
pip install uvicorn
export DJANGO_SETTINGS_MODULE=config.settings_prod
uvicorn config.asgi:application --host 127.0.0.1 --port 7111
```

Bind to loopback and let the proxy be the only thing reachable. Stay on **one worker** while
SQLite is the database: separate processes contend for the write lock and surface as
`OperationalError: database is locked`. Scale by moving `DATABASES` to Postgres, not by adding
workers.

### 3. Static files

The app ships no static assets of its own — all CSS is inline in `base.html` — so this is only
about `/admin/` styling, which breaks the moment `DEBUG` is off. Either collect and serve them
yourself:

```bash
python manage.py collectstatic --noinput --settings=config.settings_prod
```

```nginx
location /static/ { alias /srv/djbb/staticfiles/; }
```

or install `whitenoise` and put `whitenoise.middleware.WhiteNoiseMiddleware` at the *front* of
`MIDDLEWARE` in the overlay.

### 4. Back up the database

`db.sqlite3` is gitignored, so deploys never carry content — the board is only as durable as
the file on that machine. Keep it out of any nginx docroot, make sure the service user can
write to it and to its directory (SQLite journals next to the file), and back up with a tool
that takes the lock properly:

```bash
sqlite3 /srv/djbb/db.sqlite3 ".backup /backups/djbb-$(date +%F).sqlite3"
```

`manage.py dumpdata board auth.User > backup.json` gives you the same data in a form you can
`loaddata` onto a different engine later.

### 5. Retire the test accounts

```bash
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username__in=['admin','user']).delete()"
python manage.py createsuperuser          # strong password; passes the validators this time
```

There is a signup view and `Register` route for new user registration, which auto-logs users in after successful signup. That is the real access control here — protect `/admin/` and those credentials.

### 6. Supervise the process

```ini
# /etc/systemd/system/djbb.service
[Unit]
Description=django bulletin board
After=network.target

[Service]
User=djbb
WorkingDirectory=/srv/djbb
Environment=DJANGO_SETTINGS_MODULE=config.settings_prod
EnvironmentFile=/etc/djbb/env              # DJANGO_SECRET_KEY=...
ExecStart=/srv/djbb/.venv/bin/uvicorn config.asgi:application --host 127.0.0.1 --port 7111
Restart=always

[Install]
WantedBy=multi-user.target
```

`nginx` then proxies `/` to `127.0.0.1:7111` with `proxy_set_header Host $host;` and
`X-Forwarded-Proto $scheme;`, and terminates TLS.

### 7. Confirm the deployment

```bash
python manage.py check --deploy --settings=config.settings_prod
python manage.py migrate --settings=config.settings_prod
```

The cookie, HSTS, SSL-redirect and `SECRET_KEY` warnings above should clear once the overlay is
loaded. One item will not, and it is a hard error rather than a warning:

```
mail.E001  Your MAILERS setting uses a development-only email backend in the 'default' entry
```

`MAILERS` points at `console.EmailBackend`, which prints mail to stdout instead of sending it.
Swap in `django.core.mail.backends.smtp.EmailBackend` with real credentials ([email
docs](https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration)) — that
also unlocks Django's built-in error mailing to `ADMINS`, since with `DEBUG = False` an
unhandled exception is a bare error page with no traceback anywhere unless mail or logging is
configured.

### Production checklist

- [ ] `DJANGO_SETTINGS_MODULE=config.settings_prod`, and `DEBUG = False` is actually in effect
- [ ] Fresh `SECRET_KEY` from the environment, not from `config/settings.py`
- [ ] Concrete `ALLOWED_HOSTS`
- [ ] HTTPS only, with `SECURE_PROXY_SSL_HEADER` matching what the proxy sends
- [ ] Loopback-bound app server, single worker on SQLite
- [ ] Seeded accounts deleted; `admin` is not the superuser name
- [ ] `MAILERS` on a real backend, so `check --deploy` passes
- [ ] Backups scheduled and restore-tested

## Not included

Deliberately left out to keep the project readable:

- Tests — `board/tests.py` is the empty stub from `startapp`.
- Pagination, post editing history, nested replies, markdown, attachments.
- `requirements.txt`, Docker, CI.
- Any rate limiting or spam control on comments.

---

2026 [ ivan deus ]
