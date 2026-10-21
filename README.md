# DJBB-lite: Django Bulletin Board

A deliberately small bulletin board built with Django — read it as a working reference for
models, class-less function views, `ModelForm`s, and session auth, with nothing extra in the way.

There is no Bootstrap, no DRF, no Celery. Supports Neon Postgres 18 or SQLite (fallback).

![Python](https://img.shields.io/badge/python-3.12-blue) ![Django](https://img.shields.io/badge/django-6.1-green)

## Features

- **Posts** — title + body, newest first, on the index page.
- **Comments** — threaded under each post, created by logged-in users.
- **Author-only editing** — you can edit or delete your own posts.
- **Staff override** — staff users can edit or delete *anyone's* post.
- **Django admin** — posts and comments are registered and manageable at `/admin/`.
- **Anonymous read access** — browsing needs no account; writing does.
- **Self-registration** — new users can sign up with username, email, and password (min 6 chars).
- **Avatars** — every user carries one: pick from four presets, or upload a picture that is
  centre-cropped to 100×100. `/profile/` changes it later.

## Requirements

- Python 3.12+
- Django 6.1

```bash
pip install "django>=6.1" "psycopg2-binary>=2.9.9" "python-dotenv>=1.0" "Pillow>=10.0"
```

### Environment variables

Create `.env.local` in the project root (copy `.env.example` and fill it in):

```bash
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key as k; print(k())">
DATABASE_URL=postgresql://user:password@host:5432/neondb?sslmode=require&channel_binding=require
```

`config/settings.py` loads `.env.local` / `.env` via `python-dotenv`. `SECRET_KEY` is required
and no longer lives in the settings file. `DATABASE_URL` is optional — omit it and the app
falls back to SQLite (`db.sqlite3`); the URL's query params (`sslmode`, `channel_binding`, …)
pass through to `psycopg2` as connection `OPTIONS`. `.env.*` files are gitignored — secrets
never enter the repo.

#### Getting the DB URL from the Neon console

The Neon CLI signs in through a browser OAuth callback on `127.0.0.1`, which never arrives on
a headless server / VDS — `neon login` just times out there. Fetch the connection string from
the web console instead:

1. Sign in at <https://console.neon.tech>.
2. Open your **project** (e.g. `green-boat-82574724`) → the **Connection Details** panel on the
   project dashboard — this is the "Connect" flow.
3. Pick the **branch** (production) and copy the **pooled** connection string (the endpoint
   ending in `-pooler…` — right choice for serverless/app hosting; use the direct one only if
   you manage your own connection pooling).
4. Paste it into `.env.local` as `DATABASE_URL=`. The console URI already carries
   `?sslmode=require`; append `&channel_binding=require` for SCRAM channel binding.

If you need CLI/agent access on such a host later, skip browser login and use an API key
(`neon projects list --api-key "$KEY"` or `NEON_API_KEY` in the environment) instead.

#### Deploying the schema to Neon

The schema is applied with Django's standard migrations — there is no separate schema file to
push. Against the `DATABASE_URL` in `.env.local`:

```bash
# 1. apply all migrations to Neon (creates the 12 tables: auth_*, board_*, django_*)
python manage.py migrate

# 2. confirm Django is talking to Postgres, not SQLite
python manage.py shell -c "
from django.db import connection
print('vendor:', connection.vendor)
with connection.cursor() as c:
    c.execute(\"select count(*) from information_schema.tables where table_schema='public'\")
    print('tables in Neon:', c.fetchone()[0])
"

# 3. seed a real superuser (the createsuperuser wizard enforces strong passwords)
python manage.py createsuperuser
```

Notes:

- Re-run `python manage.py migrate` after every model change and new migration — Neon does not
  apply them automatically.
- Migrations are **per branch**: each Neon branch has its own database copy. Point
  `DATABASE_URL` at the branch you want to change (production by default here).
- Use the pooled (`-pooler`) endpoint for app traffic; it accepts the same migrations.
- If you deploy with the `config/settings_prod.py` overlay, add `--settings=config.settings_prod`
  to both commands.
- Roll-forward only: `board/0001_initial` and the stock auth/sessions/admin migrations are the
  whole schema. A fresh empty branch migrates cleanly in one step.

### Avatars and uploads

A stored avatar is one of exactly two shapes, both relative to `AVATARS_ROOT`
(`board/static/avatars`, which `runserver` serves under `/static/`):

| Stored value             | Meaning                                       |
| ------------------------ | --------------------------------------------- |
| `fem-a1.png` and friends | one of the four presets committed to the repo |
| `uploads/<user id>.jpeg` | the user's own picture, cropped to 100×100    |

Signup requires a preset pick, and an upload in the same submission wins over the radio button it
came with. `/profile/` accepts an empty submission and keeps whatever is stored — that is the only
way to keep an uploaded avatar, since the whitelist names presets alone.

Uploads are decoded, centre-cropped and re-encoded by Pillow **before** the row is written, and in
their own container, so a transparent PNG is not flattened into a lossy one. A file is only ever
deleted when the stored value matches `uploads/<digits>.<jpeg|png|webp>`, so no row can name a
preset, a traversal path, or somebody else's picture.

`board_profile.avatar` is `NOT NULL`: `0002_profile` fills existing users with
`avatars.preset_for_id(user_id)` — the four presets rotated by primary key — and the `post_save`
receiver calls the same function for new ones, so an account never appears without a picture.
Deleting an account takes its uploaded picture with it, through the same guarded `forget()`.

## Quick start

```bash
# from the repository root — create .env.local first (SECRET_KEY required)
cp .env.example .env.local   # then set SECRET_KEY, and DATABASE_URL from the Neon console
                             # (see "Getting the DB URL from the Neon console" above)

python manage.py migrate

# the two documented accounts, plus two more writers and twenty notes on 17th-century poetry
python manage.py seed_board

python manage.py runserver 0.0.0.0:7111
```

Then open <http://127.0.0.1:7111/>.

> `seed_board` sets passwords directly, so Django's built-in validators never see them. The plain
> `manage.py createsuperuser` wizard would reject these passwords as too short and too common —
> that is expected, not a bug in the project. Running it again is a no-op: existing accounts and
> post titles are kept.

## Test accounts

| Username   | Password  | Type    | Can                                               |
| ---------- | --------- | ------- | ------------------------------------------------- |
| `admin`    | `pass123` | staff   | Everything, plus `/admin/` and other users' posts |
| `user`     | `zxc123`  | regular | Own posts only, no `/admin/`                      |
| `cleric`   | `zxc123`  | regular | Own posts only, no `/admin/`                      |
| `cavalier` | `zxc123`  | regular | Own posts only, no `/admin/`                      |

Each of the four writes five posts, one theme at a time — Metaphysical conceit, Cavalier and
Royalist, Epic and sacred verse — and leaves replies on each other's threads, so every page has
avatars to look at. These are seeded for manual testing only. They are weak by design — do not run
this instance somewhere reachable from the internet.

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
| `GET/POST` | `/profile/`              | `profile`        | Login required; avatar picker      |
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
│   ├── avatars.py                    # presets, the upload shape, Pillow crop, disk writes
│   ├── forms.py                      # PostForm, CommentForm, RegistrationForm, ProfileForm
│   ├── models.py                     # Post, Comment, Profile
│   ├── signals.py                    # every new user gets a profile row
│   ├── views.py                      # list, detail, create, update, delete, signup, profile
│   ├── admin.py
│   ├── management/commands/seed_board.py
│   ├── templatetags/avatars.py       # {{ stored_value|avatar_url }}
│   ├── tests.py                      # the avatar rules, end to end
│   ├── static/avatars/               # four committed presets + uploads/ (gitignored)
│   └── templates/
│       ├── base.html                 # header, nav, inline CSS
│       ├── board/                    # post_list, post_detail, post_form, post_confirm_delete, profile
│       ├── partials/                 # avatar_picker.html
│       └── registration/             # login.html, signup.html
├── config/
│   ├── settings.py                   # SQLite or Neon Postgres (via DATABASE_URL), AVATARS_ROOT
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── db.sqlite3                        # SQLite fallback (gitignored if DATABASE_URL set)
└── manage.py
```

Database backend configured by `DATABASE_URL` environment variable: PostgreSQL if present, SQLite otherwise.

`Post` and `Comment` are three fields plus a timestamp; `Comment` has a `related_name='comments'`
so templates iterate `post.comments.all` directly. `Profile` is the one-to-one that holds the
avatar, because Django's `auth.User` cannot take a column without swapping `AUTH_USER_MODEL`.

## Configuration

Everything lives in `config/settings.py`. The parts worth knowing about:

- `SECRET_KEY` — read from the environment (`config/settings.py` does `os.environ["SECRET_KEY"]`); supply it via `.env.local` or the process environment.
- `DATABASES` — PostgreSQL if `DATABASE_URL` is set (Neon.tech format), otherwise SQLite at `BASE_DIR / 'db.sqlite3'`. Delete the SQLite file for a clean slate or unset `DATABASE_URL` to fall back.
- `DEBUG = True` and `ALLOWED_HOSTS = ['*']` — development posture, bound to all interfaces.
- `AVATARS_ROOT` — the folder holding the four presets and receiving uploads, `BASE_DIR / 'board' / 'static' / 'avatars'`. Stored values stay relative to it, so moving it needs no migration.
- `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL` — auth flow lands back on the index.

## Running in production

The repo is in development posture on purpose: `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, the
console email backend, and two weak seeded accounts. None of that survives a real host — the
`SECRET_KEY` already lives outside the code, in `.env.local` (or the process environment).
Everything below is additive — leave `config/settings.py` for local work and add an overlay
module that production loads instead.

### 1. Settings overlay

```python
# config/settings_prod.py
from .settings import *  # noqa: F403  (BASE_DIR and SECRET_KEY come in with the star-import)

DEBUG = False
ALLOWED_HOSTS = ["board.example.com"]          # exact hosts, no wildcard
STATIC_ROOT = BASE_DIR / "staticfiles"
AVATARS_ROOT = STATIC_ROOT / "avatars"         # uploads land in the served copy, beside the collected presets

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 15        # raise it only once TLS is proven
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # TLS ends at the proxy
```

`SECRET_KEY` is read from the environment by `config/settings.py`, so production just exports
it (a systemd `EnvironmentFile` or the host's `.env.local`). Treat any key that ever sat in
this repo as public and rotate it — generate a fresh one:

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

All CSS is inline in `base.html`, so the assets in question are the four avatar presets, the uploads
written next to them, and `/admin/` styling — all three break the moment `DEBUG` is off. Either
collect and serve them yourself:

```bash
python manage.py collectstatic --noinput --settings=config.settings_prod
```

```nginx
location /static/ { alias /srv/djbb/staticfiles/; }
```

or install `whitenoise` and put `whitenoise.middleware.WhiteNoiseMiddleware` at the *front* of
`MIDDLEWARE` in the overlay.

`collectstatic` is what puts the four presets into `STATIC_ROOT / 'avatars'`, which is why the
overlay points `AVATARS_ROOT` at that folder: uploads then land where the server already publishes
them. Never run `collectstatic --clear` against it — that is how you delete what users uploaded.

### 4. Back up the database

`db.sqlite3` is gitignored, so deploys never carry content — the board is only as durable as
the file on that machine. Keep it out of any nginx docroot, make sure the service user can
write to it and to its directory (SQLite journals next to the file), and back up with a tool
that takes the lock properly:

```bash
sqlite3 /srv/djbb/db.sqlite3 ".backup /backups/djbb-$(date +%F).sqlite3"
```

`manage.py dumpdata board auth.User > backup.json` gives you the same data in a form you can
`loaddata` onto a different engine later. Avatar uploads are files, not rows: back up
`AVATARS_ROOT / 'uploads'` alongside the database, or a row whose picture is gone renders a broken
image.

### 5. Retire the test accounts

```bash
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username__in=['admin','user','cleric','cavalier']).delete()"
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
EnvironmentFile=/etc/djbb/env              # SECRET_KEY=...
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
- [ ] Fresh `SECRET_KEY` in the environment (the previously committed key is burned — rotate it)
- [ ] Concrete `ALLOWED_HOSTS`
- [ ] HTTPS only, with `SECURE_PROXY_SSL_HEADER` matching what the proxy sends
- [ ] Loopback-bound app server, single worker on SQLite
- [ ] Seeded accounts deleted; `admin` is not the superuser name
- [ ] `MAILERS` on a real backend, so `check --deploy` passes
- [ ] Backups scheduled and restore-tested

## Not included

Deliberately left out to keep the project readable:

- Tests — `board/tests.py` covers the avatar rules (presets, cropping, the shapes a row may hold,
  what may be deleted); nothing else is tested.
- Pagination, post editing history, nested replies, markdown, attachments.
- `requirements.txt`, Docker, CI.
- Any rate limiting or spam control on comments.

---

2026 [ ivan deus ]
