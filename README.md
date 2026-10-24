# DJBB-lite: Django Bulletin Board

A deliberately small bulletin board built with Django.
There is no Bootstrap, no DRF, no Celery. Runs on PostgreSQL — Neon or a local cluster — and on
nothing else.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Django](https://img.shields.io/badge/django-6.1-green)

## Features

- **Posts** — title + body, newest first, on the index page.
- **Comments** — threaded under each post, created by logged-in users, ten to a page with the oldest
  first.
- **Author-only editing** — you can edit or delete your own posts.
- **Staff override** — staff users can edit or delete *anyone's* post.
- **Django admin** — posts and comments are registered and manageable at `/admin/`. The comment list
  pages ten replies at a time, in the order the thread prints them.
- **Read-only profiles in the admin** — `/admin/board/profile/` lists every writer's name, avatar
  and e-mail. That section grants view and nothing else: no add, no change, no delete.
- **Anonymous read access** — browsing needs no account; writing does.
- **Self-registration** — new users can sign up with username, email, and password (min 6 chars).
- **Avatars** — every user carries one: pick from four presets, or upload a picture that is
  centre-cropped to 100×100. `/profile/` changes it later and shows the current one at that size.
- **Change password** — `/profile/` takes a new password too, against the current one, and keeps you
  signed in across the change instead of bouncing you back to the login form.
- **A 404 that knows where it is** — a post id with nothing behind it renders the board's own page
  and carries the visitor back to the index two seconds later.
- **A page per member** — every avatar on the board links to `/user/<name>/`, which shows the
  picture at its full 100×100. The e-mail address on that page is visible to staff only.
- **A members list** — `/members/` is a table of every writer — face, name, whether they are an
  admin or a member, and when they last did something here — with whoever wrote most recently at the
  top. Staff only, and the users figure in the footer is the only way there. Every row but the
  admin's own carries a button that switches that account between the two types.
- **Footer counts** — a small panel above the credit line on every page, holding three numbers:
  members, replies, and topics. A topic is a post here.

## Requirements

- Python 3.12+
- Django 6.1
- PostgreSQL 16+ — Neon, or a local cluster ([Setting up a local PostgreSQL
  database](#1b-setting-up-a-local-postgresql-database))

```bash
pip install "django>=6.1" "psycopg2-binary>=2.9.9" "python-dotenv>=1.0" "Pillow>=10.0"
```

### Environment variables

Create `.env.local` in the project root (copy `.env.example` and fill it in):

```bash
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key as k; print(k())">
DATABASE_URL=postgresql://user:password@host:5432/neondb?sslmode=require&channel_binding=require
```

`config/settings.py` loads `.env.local` / `.env` via `python-dotenv`. Both values are required:
`SECRET_KEY` is read straight from the environment, and `DATABASE_URL` is what the settings import builds
its one PostgreSQL connection from — without it, or with it left empty, the import raises
`ImproperlyConfigured` before any command runs, so nothing ever starts against a database nobody chose.
The URL's query params (`sslmode`, `channel_binding`, …) pass through to `psycopg2` as connection
`OPTIONS`. `.env.*` files are gitignored — secrets never enter the repo.

#### Getting the DB URL from the Neon console

The Neon CLI signs in through a browser OAuth callback on `127.0.0.1`, which never arrives on
a headless server / VDS — `neon login` just times out there. Fetch the connection string from
the web console instead:

1. Sign in at <https://console.neon.tech>.
2. Open your **project** → the **Connection Details** panel on the
   project dashboard — this is the "Connect" flow.
3. Pick the **branch** (production) and copy the **pooled** connection string.
4. Paste it into `.env.local` as `DATABASE_URL=`. The console URI already carries
   `?sslmode=require`; append `&channel_binding=require` for SCRAM channel binding.

If you need CLI/agent access on such a host later, skip browser login and use an API key
(`neon projects list --api-key "$KEY"` or `NEON_API_KEY` in the environment) instead.

This is one of the two ways to get a `DATABASE_URL`. The other is a cluster on the same machine, built in
[Setting up a local PostgreSQL database](#1b-setting-up-a-local-postgresql-database) — the board speaks
the same SQL either way, and no setting changes between them.

#### Deploying the schema to DB

The schema is applied with Django's standard migrations — there is no separate schema file to
push. The ordered pass from an empty project to a running board is
[Deploying to Neon](#deploying-to-neon).

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

### Looking at profiles in the admin

`/admin/board/profile/` is a read-only window onto the board's people: avatar, name, e-mail, with a
search box over the two text fields. `ProfileAdmin` refuses add, change and delete, and Django
renders what is left in its view mode — no save button, the fields as plain text. The cost of that
mode is that every field has to be listed in `readonly_fields` to appear at all, since the model
itself only holds the avatar string; name and e-mail are methods reading through the one-to-one, and
`get_queryset` follows it with a `select_related` so the list does not fetch each user separately.

Django's own user admin is left alone: accounts, e-mail and passwords are still edited there, and
this page exists only for looking. The one rank the board changes for itself is `is_staff`, and it
does that from `/members/` rather than from `/admin/`.

### Who is on the board

`/members/` is the roll-call — one row per writer, holding their face, their name, whether they are
an `admin` or a `member`, and when they last did something here — with whoever did something most
recently at the top.

The ordering is one annotation:

```python
last_activity = Coalesce(
    Greatest(Max('post__created_at'), Max('comment__created_at')),
    F('date_joined'),
)
```

so a writer is placed by their newest post or their newest reply, and someone who has never written
at all by the day they joined. The join date sits in the `Coalesce` rather than as a third argument
to `Greatest` on purpose: `Greatest` ignores NULLs and returns the largest value it is given, so
folding the signup day in would make every account at least as recent as itself, and a writer whose
only topic is a year old would never fall below someone who joined last week.

The same annotation is printed in the `Last action` column — it was always computed, only never
shown — so the column and the order are one value and cannot disagree. It renders with the board's
one timestamp format, `Y-m-d H:i`, and can never be empty: the join date inside the `Coalesce` is
NOT NULL.

Staff only, with the two refusals split the way the admin splits them: `login_required` sends a
guest to `/login/?next=/members/`, and a writer who is not staff gets a `403` from a
`raise PermissionDenied` in the view. That raise is written out because Django 6's
`user_passes_test` no longer takes `raise_exception` — on its own it redirects, which would tell a
logged-in writer to log in again.

The only link to it is the users figure in the footer panel, and `partials/stats.html` wraps that in
an `<a>` only when `user.is_staff`. Guests and plain writers see exactly the panel they saw before.
`base.html` carries `table` and `th, td` rules now, which no page on the board needed until this one.

### Switching a member's type

Every row of that table but the visitor's own ends in a button — `make admin` on a member, `make
member` on an admin — posting to `POST /members/<pk>/role/`. `member_role` is the board's only write
to the user table, and `is_staff` the only thing it moves: `save(update_fields=['is_staff'])` means
neither password, nor e-mail, nor `date_joined`, nor `is_superuser` can ride along. A superuser is
not a rank the board hands out, and `/admin/auth/user/` stays the place where one is.

The refusals are the two `member_list` itself already makes, not `post_update`'s redirect: that
redirect exists to hide which post ids exist, and nothing is hidden on a page that already lists every
account — where a quiet bounce back would read as success to a forged request. `require_POST` sits
under `login_required`, so a logged-in GET is a `405` rather than a second way to
write. The row of the admin who is clicking offers no button at all, and a POST naming that pk is a
third `403`: switching themselves off would end their own right to this page, so the failure is
designed out rather than warned about. The surviving row gets a message — `donne is now an admin.` —
through Django's messages framework, which `base.html` already renders.

### Changing a password

`/profile/` carries two forms, and the button that came back picks which one is bound:
`change_password` is the name of the second submit, so a rejected password never paints errors over
the avatar picker next to it, and saving an avatar never has to know the current password.

The form is Django's own `PasswordChangeForm`, which checks `old_password` against the stored hash
and runs `AUTH_PASSWORD_VALIDATORS` over the new one — so 8 characters minimum, nothing common,
nothing entirely numeric. `board/forms.py` only relabels the fields and adds the `field` class. The
view then calls `update_session_auth_hash`, without which the change would log the visitor out: the
session row is keyed to the password hash, so a new hash invalidates the cookie that just arrived.

### When a post is gone

`/post/7/` with nothing behind it answers with `board/post_missing.html` — "That topic does not
exist, or it has been deleted" — and a `<meta http-equiv="refresh" content="2;url=/">` in the head
carries the visitor to the index two seconds later, with a plain link for anyone who wants it sooner.

Two choices are worth knowing about. The view **returns** that page rather than raising `Http404`,
because with `DEBUG = True` Django swaps any `handler404` for its own technical page, so a raised 404
would show a stack trace on exactly the machine most likely to be running this repo. And the response
still **carries status 404**: the redirect is a courtesy to the person reading the page, not a lie to
the crawler, the monitoring check, or `curl`.

### Ten replies to a page

A thread shows ten comments at a time, oldest first, and `/admin/board/comment/` pages the same way.
`Comment.PER_PAGE` is the number. The ordering is not written into each query — `Comment.Meta.ordering`
is `('created_at', 'id')`, so the thread, the staff list and the inline under a post all read one
definition and cannot disagree about which reply came first. `id` is in it because a comment has no
`updated_at`: two replies stamped the same instant would otherwise drift across a page boundary between
one look and the next.

`Paginator(...).get_page(request.GET.get('page'))` is what keeps a hand-typed address honest. Django
answers a page that does not exist with the last page that does, and one that is not a number with the
first, so `?page=99` on a three-reply thread shows those three replies rather than an empty list under
the words "No comments yet." The pager is four ends around one figure — `«` to the first page,
`‹ previous`, `next ›`, `»` to the last — and whichever of them has nowhere to go prints as a dimmed
`pager-off` word rather than a link back to the page already on screen. A thread of ten or fewer prints
no pager at all. A reply redirects to the page that holds it, so its author is not sent back to replies
they have already read, and the URL keeps the `page` out of it while one page is all there is.

Two lists differ from that hand-built pager, both because they belong to Django rather than to this
board: the staff changelist gets its paging from `list_per_page` and so renders Django's own markup and
its own answer to a bad `?p=` — a bounce to the first page with a message — and the comment inline under
a post cannot be paged at all, since an inline is rendered whole.

### The three footer numbers

Every page closes with a small bordered panel above the credit line: `5 users · 8 comments ·
20 topics`. **A topic is a post** — this board has no separate thread or category model — so the
three figures are members, replies, and topics.

`board/context_processors.py:board_stats` supplies them, registered under
`TEMPLATES → OPTIONS → context_processors`. That is how all eight board views and the login page get
the same footer without each of them passing three counts, and without the next view added forgetting
to. They are counted on every request rather than cached: three indexed `COUNT`s over tables this
small are cheaper than a cache that can report a member who has since left.

## Quick start

```bash
# from the repository root — create .env.local first (both values are required to boot)
cp .env.example .env.local   # then set SECRET_KEY, and DATABASE_URL to a PostgreSQL connection string
                             # (see "Getting the DB URL from the Neon console" above, or build a local
                             # cluster per §1b)

python manage.py migrate

# the two documented accounts, plus two more writers and twenty notes on 17th-century poetry
python manage.py seed_board

python manage.py runserver 0.0.0.0:7111
```

Then open <http://127.0.0.1:7111/>. Without a `DATABASE_URL` the first command stops at the settings
import rather than starting on some other database; for the path from an empty Neon project to a live
board, see [Deploying to Neon](#deploying-to-neon).

> `seed_board` sets passwords directly, so Django's built-in validators never see them. The plain
> `manage.py createsuperuser` wizard would reject these passwords as too short and too common —
> that is expected, not a bug in the project. Running it again is a no-op: existing accounts and
> post titles are kept.

### Running the tests

`board/tests.py` holds 79 cases over the board's own rules — avatars, posts and comments, signup and
login, the profile page, password changes, the footer counts, the members list and the type switch on it,
and the paged replies. They need a database: Django's runner creates a fresh one and applies every
migration to it before the first test runs.

This repo configures no such database, and there is no second connection string to configure — the
runner takes host, port and role from the very `DATABASE_URL` the app itself uses. So the suite runs
against a cluster whose role may create databases, which is the local one
[§1b](#1b-setting-up-a-local-postgresql-database) builds:

```bash
DATABASE_URL=postgresql://djbb_user:your_password@127.0.0.1:5432/djbb_db python manage.py test
```

The exported value wins over `.env.local`, because `python-dotenv` loads without overriding what the
environment already holds.

What not to do: run `manage.py test` with the Neon URL that `.env.local` carries. The runner would ask
that server for `CREATE DATABASE test_neondb` on the branch the live board runs on, and the owner role
reports `rolcreatedb`, so the request is one the database can honour rather than one that fails safely.
Django 6.1 has no `--collect-only` to list cases without a database; to see them anyway, build the suite —
importing tests opens no connection:

```bash
python manage.py shell -c "from django.conf import settings; from django.test.utils import get_runner; \
print(get_runner(settings)(verbosity=0).build_suite().countTestCases())"
```

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
| `GET`      | `/post/<pk>/`            | `post_detail`    | Public; comment form if logged in; `?page=` takes a page of ten replies; missing id gets `post_missing.html` |
| `GET/POST` | `/post/new/`             | `post_create`    | Login required                     |
| `GET/POST` | `/post/<pk>/edit/`       | `post_update`    | Author or staff                    |
| `GET/POST` | `/post/<pk>/delete/`     | `post_delete`    | Author or staff                    |
| `GET`      | `/user/<username>/`      | `user_detail`    | Public; e-mail only for staff      |
| `GET`      | `/members/`              | `member_list`    | Staff only; linked from the footer |
| `POST`     | `/members/<pk>/role/`    | `member_role`    | Staff only; never the admin's own row |
| `GET/POST` | `/login/`                | Django `LoginView` |                                   |
| `GET/POST` | `/signup/`               | `signup`         | New user registration              |
| `GET/POST` | `/profile/`              | `profile`        | Login required; avatar and password |
| `POST`     | `/logout/`               | Django `LogoutView` | POST only, as of Django 5        |
| `*`        | `/admin/`                | Django admin     | Staff only; `/admin/board/comment/` pages ten replies with `?p=` |

## Permissions model

The rule that decides who may edit a post is one helper in `board/views.py`:

```python
def _can_manage(user, post):
    return user.is_staff or post.author_id == user.pk
```

Users who fail the check are redirected to the post rather than shown a 403, so the edit and
delete URLs do not leak which post IDs exist versus which are simply yours.

Two smaller rules sit beside it: `/user/<name>/` prints the e-mail line only for
`request.user.is_staff`, and `ProfileAdmin` in `board/admin.py` refuses add, change and delete, so
the profiles section is a window rather than a door. A third keeps `/members/` behind staff: a guest
is redirected to the login page, a writer who is not staff is refused with `403`, and the footer
figure that links there is rendered as a link for staff alone. The `POST /members/<pk>/role/` that
switches a type takes that third rule whole and adds one refusal of its own — the pk of the admin who
is clicking is a `403` too, because no path from this page may end the right to use it.

## Project layout

```
.
├── board/
│   ├── avatars.py                    # presets, the upload shape, Pillow crop, disk writes
│   ├── forms.py                      # PostForm, CommentForm, RegistrationForm, ProfileForm
│   ├── models.py                     # Post, Comment, Profile
│   ├── signals.py                    # every new user gets a profile row
│   ├── context_processors.py         # the footer's three counts, on every page
│   ├── views.py                      # list, detail, member, members, role, create, update, delete, signup, profile
│   ├── admin.py                      # posts, comments, and read-only profiles
│   ├── management/commands/seed_board.py
│   ├── templatetags/avatars.py       # {{ stored_value|avatar_url }}
│   ├── tests.py                      # the board's rules, end to end: avatars, posts, auth,
│   │                                 #   profiles, passwords, the footer, the members list,
│   │                                 #   the paged replies
│   ├── static/avatars/               # four committed presets + uploads/ (gitignored)
│   └── templates/
│       ├── base.html                 # header, nav, footer, inline CSS
│       ├── board/                    # post_list, post_detail, post_form, post_confirm_delete,
│       │                             #   post_missing, profile, user_detail, member_list
│       ├── partials/                 # avatar_picker.html, stats.html
│       └── registration/             # login.html, signup.html
├── config/
│   ├── settings.py                   # PostgreSQL only (via DATABASE_URL), AVATARS_ROOT
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── manage.py
```

There is one database engine: `DATABASE_URL` names the PostgreSQL database the board runs on, and the
settings import fails rather than guessing at another.

`Post` and `Comment` are three fields plus a timestamp; `Comment` has a `related_name='comments'` so
templates iterate `post.comments.all` directly, a `Meta.ordering` of `('created_at', 'id')` so every list
of them runs oldest first, and a `PER_PAGE` of 10 that is the size those lists are cut at. `Profile` is
the one-to-one that holds the avatar, because Django's `auth.User` cannot take a column without swapping
`AUTH_USER_MODEL`.

## Configuration

Everything lives in `config/settings.py`. The parts worth knowing about:

- `SECRET_KEY` — read from the environment (`config/settings.py` does `os.environ["SECRET_KEY"]`); supply it via `.env.local` or the process environment.
- `DATABASES` — one PostgreSQL connection, built from `DATABASE_URL` at import. Either endpoint format works: the pooled URI copied from the Neon console, or a local cluster ([§1b](#1b-setting-up-a-local-postgresql-database)). A missing or empty `DATABASE_URL` raises `ImproperlyConfigured` where the settings are imported, so no command — `check`, `migrate`, `runserver`, the WSGI entry — can start against a database nobody picked. The URL's query params pass through to `psycopg2` as `OPTIONS`.
- The test database is not configured, because Django takes its host from this same connection. Point `DATABASE_URL` at a cluster your role may create databases on to run the suite — see [Running the tests](#running-the-tests).
- `DEBUG = True` and `ALLOWED_HOSTS = ['*']` — development posture, bound to all interfaces. In production, update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to reflect your public URL (if you get Forbidden (403) CSRF verification failed. Request aborted).
- `AVATARS_ROOT` — the folder holding the four presets and receiving uploads, `BASE_DIR / 'board' / 'static' / 'avatars'`. Stored values stay relative to it, so moving it needs no migration.
- `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL` — auth flow lands back on the index.

## Deploying to Neon

Neon holds the database; the Django process runs wherever you put it, and that half is
[Running in production](#running-in-production). Two things are worth settling first:

- **`neon deploy` does not publish the app.** It applies `neon.ts` — the declared services and the
  branch policy — to a branch, then pulls that branch's env variables into a local `.env`. The
  name is about the branch, not the site.
- **The CLI signs in through a browser callback on `127.0.0.1`**, which never arrives on a
  headless server: `neon status` and `neon projects list` sit there printing an auth URL until
  they time out. Run the CLI somewhere a browser can open that URL, or pass `--api-key "$KEY"`
  (a key from your Neon account's API keys) / export `NEON_API_KEY`. Every command below assumes
  the key.

### 1a. Link the project, apply the policy

Create the project in the console (<https://console.neon.tech>) and note the organization ID and the project ID. From the repository root:

```bash
npm install                                                     # @neon/config, @neon/env
neon init -y --services postgres --org-id <org> --project-id <project>
neon deploy -y                                                  # apply neon.ts to the branch
```

`neon init` writes `neon.ts` plus a gitignored `.neon/` context file that pins the project and
branch, so the commands after it need no IDs. `neon deploy` ends in an env pull by default
(`--no-env-pull` to skip), writing the branch's `DATABASE_URL` into `.env`. Check which endpoint
it picked — an app with short-lived connections wants the pooled one, whose host ends in
`-pooler…`:

```bash
neon connection-string production --pooled
```

The committed `neon.ts` gives every new non-default branch a 7-day TTL, so a branch made with
`neon checkout` is a testing branch that will be deleted — do not put anything on it you intend
to keep.

### 1b. Setting up a local PostgreSQL database

Neon is not a requirement. PostgreSQL is the only engine either way, so a cluster on the same machine is a
straight stand-in for every command in this project — and it is the one place the test suite can run,
since that needs a role allowed to create a database of its own
([Running the tests](#running-the-tests)).

1.  **Install PostgreSQL** — 16 or newer is what the board is written against:

    ```bash
    apt install postgresql
    ```

2.  **Create the role and the database**, as the `postgres` superuser — `sudo -u postgres psql`:

    ```sql
    CREATE ROLE djbb_user LOGIN PASSWORD 'your_password';
    CREATE DATABASE djbb_db OWNER djbb_user;
    ```

    The role owns the database it is handed to `python manage.py migrate`, because the migrations create,
    alter and drop tables. A `GRANT` over somebody else's schema is where a run stops halfway, having
    left the earlier tables behind.

3.  **Point `.env.local` at it**:

    ```bash
    DATABASE_URL=postgresql://djbb_user:your_password@127.0.0.1:5432/djbb_db
    ```

    Django asks for no TLS unless the URL says so, so a cluster running `ssl = off` is reached by exactly
    this string — nothing like `?sslmode=disable` is needed, because there is no default to disable.
    Against a cluster that does speak TLS, append `?sslmode=require&channel_binding=require`, and note
    that the role's password must be stored as `scram-sha-256`, which has been `password_encryption`'s
    default since PostgreSQL 14.

4.  **Migrate & seed**:

    ```bash
    python manage.py migrate
    python manage.py seed_board
    ```

### 2. Give the app its two variables

`config/settings.py` loads `.env.local` before `.env`, and `python-dotenv` never overrides a
variable that is already set, so the pulled `.env` can carry `DATABASE_URL` while `SECRET_KEY`
stays in your own file. Both are gitignored.

```bash
cp .env.example .env.local     # set SECRET_KEY; DATABASE_URL may come from the pulled .env
```

Either way, append `&channel_binding=require` to the console's URI if it is not there — the
console path is documented under
[Getting the DB URL from the Neon console](#getting-the-db-url-from-the-neon-console).

If the project has an IP allow list (`neon ip-allow list`, or the network section of the project's
settings in the console), add the app host's egress address to it now, or every connection from
that host is refused and the failure looks like a timeout rather than a wrong password.

### 3. Apply the schema

```bash
pip install -r requirements.txt

python manage.py migrate       # tables: auth_*, board_*, django_*
python manage.py check         # same check `npm run build` runs
```

Then confirm the app reached the branch you meant. There is no second engine to fall back to any more —
a missing `DATABASE_URL` stops at the settings import, and `python manage.py check`, which is what
`npm run build` runs, is the cheap proof of that, since `check` never opens a connection — but a
*_wrong* Postgres string still boots and answers happily against somebody else's data:

```bash
python manage.py shell -c "
from django.db import connection
print('vendor:', connection.vendor)
with connection.cursor() as c:
    c.execute(\"select count(*) from information_schema.tables where table_schema='public'\")
    print('tables in Neon:', c.fetchone()[0])
"
```

### 4. Put data in it

```bash
python manage.py seed_board    # four writers, twenty posts, eight replies — testing only
python manage.py createsuperuser
```

`seed_board` writes the demo passwords straight into the rows, so the `createsuperuser` validators
never see them; delete those four accounts before the board is reachable from anywhere
([Retire the test accounts](#5-retire-the-test-accounts)).

### 5. Keep it in sync afterwards

- Re-run `python manage.py migrate` after every model change — Neon does not apply migrations by
  itself, and a row written against a stale schema is a broken deploy.
- Migrations are **per branch**: each branch is its own database. Point `DATABASE_URL` at the
  branch you mean to change, and remember the pooled endpoint takes migrations exactly as well as
  the direct one.
- `neon diff <branch>` shows the schema gap between two branches before you trust a test branch to
  represent production.
- Roll-forward only. `board/0001_initial`, `board/0002_profile` and the stock
  auth/sessions/admin migrations are the whole schema, and a fresh empty branch migrates cleanly
  in one step.
- With the `config/settings_prod.py` overlay, add `--settings=config.settings_prod` to `migrate`,
  `seed_board` and `createsuperuser`.

## Running in production

The database side is settled by [Deploying to Neon](#deploying-to-neon); this section is the
process, the TLS, and the files. The repo is in development posture on purpose: `DEBUG = True`,
`ALLOWED_HOSTS = ['*']`, the console email backend, and four weak seeded accounts. None of that
survives a real host — the `SECRET_KEY` already lives outside the code, in `.env.local` (or the
process environment). Everything below is additive — leave `config/settings.py` for local work and
add an overlay module that production loads instead.

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

Bind to loopback and let the proxy be the only thing reachable. How many workers to run is no longer a
correctness question: Postgres serves concurrent writers, so the `OperationalError: database is locked`
that once capped this board at a single process has nothing left to cap. The limit that remains is the
one the database sets — Neon's pooled endpoint hands every worker connections out of the same pool, so
plan the pool size rather than the process count.

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

The database is not a file on this machine, so there is nothing beside the app to keep out of a docroot
or to hand write permission to. The durable artefact is a dump. On Neon, restore points and scheduled
backups belong to the project rather than to this repo, so read them as a convenience you have to confirm
rather than a guarantee. The copy that is yours is a plain dump, and it wants the **direct** endpoint — a
pooler multiplexes sessions, and a dump holds one open for its whole run:

```bash
pg_dump "$DATABASE_URL_DIRECT" -Fc -f /backups/djbb-$(date +%F).dump
```

`manage.py dumpdata board auth.User > backup.json` gives you the same data in a form you can
`loaddata` onto another PostgreSQL later — a fresh branch, or the local cluster of §1b. Avatar uploads
are files, not rows: back up `AVATARS_ROOT / 'uploads'` alongside the database, or a row whose picture is
gone renders a broken image.

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
EnvironmentFile=/etc/djbb/env              # SECRET_KEY=…, DATABASE_URL=… (0600)
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
- [ ] Loopback-bound app server
- [ ] Seeded accounts deleted; `admin` is not the superuser name
- [ ] `MAILERS` on a real backend, so `check --deploy` passes
- [ ] `DATABASE_URL` points at the pooled endpoint, and the host's egress IP is on the project's
      allow list
- [ ] `migrate` run against the branch you just deployed, and `vendor: postgres` printed by the
      check in [Deploying to Neon](#deploying-to-neon)
- [ ] Backups scheduled and restore-tested

## Not included

Deliberately left out to keep the project readable:

- Full test coverage — `board/tests.py` exercises the flows this board has (avatars, posts and
  comments, signup and login, profile editing, password changes, the footer counts, the members
  list and the type switch on it, the paged replies), not every branch of the Django forms and views
  those pages sit on.
- Paged topic lists — `/` still prints every post, and the admin's comment inline prints every reply of
  a post; only the comment lists themselves are cut into pages.
- Post editing history, nested replies, markdown, attachments.
- Docker, CI.
- Any rate limiting or spam control on comments.

---

2026 [ ivan deus ]
