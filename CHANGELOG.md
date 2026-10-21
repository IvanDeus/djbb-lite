# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- **Board counts in the footer** — a small bordered panel above the credit line on every page:
  `5 users · 8 comments · 20 topics`. A topic is a post, since this board has no separate
  thread or category model, so the three figures are members, replies and topics.
  `board/context_processors.py:board_stats` puts them in the template context site-wide, which
  keeps `base.html` honest without each view remembering to pass a count, and the numbers are
  queried per request rather than cached: three indexed `COUNT`s on tables this small cost less
  than anything that could go stale.
- **A page per member** — `/user/<username>/` shows one writer's avatar at its full 100×100 beside
  their name, and every avatar on the board (post author, comment author, on the index and on a
  thread) now links to it. The e-mail line on that page renders only for `request.user.is_staff`,
  so anonymous visitors and fellow writers see a face and a name.
- **A 404 that speaks board** — `/post/<pk>/` with no post behind it now renders
  `board/post_missing.html` ("That topic does not exist, or it has been deleted") with a
  two-second `<meta http-equiv="refresh">` back to the index, plus a link for anyone who wants it
  sooner. `post_detail` returns the page instead of raising `Http404`, because Django's technical
  404 page replaces any `handler404` while `DEBUG` is on; the response still carries status 404.
- **Read-only profiles in the admin** — `/admin/board/profile/` lists every writer's avatar, name
  and e-mail, searchable, with the one-to-one joined so the list does not fetch users row by row.
  `ProfileAdmin` refuses add, change and delete, which is what puts Django's change page into its
  view-only mode: no save button, the fields rendered as text, and every field declared in
  `readonly_fields` because that is the only way a method column reaches the form at all. Editing
  accounts stays with Django's own user admin.
- **Change password on `/profile/`** — Django's `PasswordChangeForm` (current password checked
  against the stored hash, `AUTH_PASSWORD_VALIDATORS` run over the new one) rendered under the
  avatar picker. The page now holds two forms and the pressed button decides which is bound, so a
  rejected password leaves the picker alone and saving an avatar never asks for the old one;
  `update_session_auth_hash` keeps the visitor signed in through their own change, and the result
  is announced through `django.contrib.messages`, which `base.html` now renders.
- **`Deploying to Neon` walkthrough in `README.md`** — one ordered pass from an empty project to a
  running board: link the project and apply the policy, hand the app its two variables, migrate,
  seed, and keep the schema in sync afterwards. It says plainly that `neon deploy` applies
  `neon.ts` to a branch and is not app hosting, that the CLI's browser callback never lands on a
  headless host so an API key carries the auth, that the pulled `.env` can supply `DATABASE_URL`
  while `.env.local` keeps `SECRET_KEY`, and that a project IP allow list fails as a timeout
  rather than an auth error. The production section gains a `pg_dump` backup against the direct
  endpoint and two Neon items in its checklist.
- **Avatars for every user** — the four 100×100 presets committed to `board/static/avatars` are the
  floor: signup requires a pick, an upload submitted with it wins and is centre-cropped and
  re-encoded by Pillow in its own container, and `/profile/` changes either later. Stored values are
  kept to two shapes — a whitelisted preset basename or `uploads/{id}.{jpeg,png,webp}` — and that
  regex is what gates deletion, so no row can ever name a traversal path or another user's file.
  The column lives on `board.Profile`, because `auth.User` cannot take one without swapping
  `AUTH_USER_MODEL`; it is `NOT NULL` behind a backfill that rotates the presets by `id % 4`, the
  same rule `preset_for_id()` applies in the `post_save` receiver. Avatars render beside every
  author on the board, in the header (which now links to `/profile/`) and in the admin's author
  column. Pillow is a new requirement, and `seed_board` fills an empty database with four writers,
  twenty notes on 17th-century poetry across three themes, and replies between them.
- **Footer on every page** — "Designed and developed by Ivan Deus" with a link to
  `https://github.com/IvanDeus`, rendered in `base.html` below the content block.
- **Signup view** — new user registration at `/signup/` with username, email (no confirmation needed), and password fields (min 6 chars). Auto-log in after successful registration. `RegistrationForm` validates uniqueness of usernames.
- **`SECRET_KEY` moved to the environment** — `config/settings.py` now reads
  `os.environ["SECRET_KEY"]`; the literal is gone from the file. A fresh key lives in the
  gitignored `.env.local`, and `.env.example` documents both required values. The previously
  committed key is burned — rotate it on any real host.
- **Neon Postgres 18 support** — the database is selected by the `DATABASE_URL` environment
  variable (Neon pooled connection string). `config/settings.py` loads `.env.local` / `.env`
  through `python-dotenv`, parses the URL, and passes query params (`sslmode=require`,
  `channel_binding=require`) through to `psycopg2` as connection `OPTIONS`. Without
  `DATABASE_URL` the app falls back to SQLite (`db.sqlite3`). `neon.ts` + `package.json`
  added by `neon init`; `npm run build` runs Django's system check. Verified against a live
  Neon project: `migrate` applied all 12 tables, signup / login / post / comment round-tripped
  over HTTP on `PostgreSQL 18.6`. `README.md` documents pulling the connection string from the
  Neon console (project → Connection Details) — the CLI's browser OAuth callback never lands
  on a headless VDS, where `neon login` times out; an API key is the non-interactive fallback.
  A "Deploying the schema to Neon" section covers `migrate` + vendor/table verification +
  `createsuperuser`, and the per-branch, re-run-after-every-model-change caveats.
- **Production run guide** — a "Running in production" section in `README.md` covering the
  `config/settings_prod.py` overlay pattern, uvicorn against `config.asgi:application`, static
  files, SQLite backups, retiring the seeded accounts, systemd, nginx, and `check --deploy`.
- **`.gitignore`** — Python caches, virtualenvs, the SQLite database and its journals, local
  settings, environment files and keys, coverage and packaging output, editor and OS droppings.

## 0.1.0 - 2026-10-20

Initial working release: a complete, minimal bulletin board running on Django 6.1 with SQLite.

### Added

- **`board` app** — the whole application, scaffolded with `startapp`.
- **`Post` model** — `title`, `body`, `author` FK to `AUTH_USER_MODEL` (`CASCADE`), and an
  `auto_now_add` `created_at`. Migration `board/0001_initial` creates it.
- **`Comment` model** — `post` FK with `related_name='comments'`, `author` FK, `body`, and
  `created_at`. Deleting a post removes its comments.
- **Post index** at `/` — newest first, showing author, timestamp, comment count, and a body
  truncated to 240 characters.
- **Post detail** at `/post/<pk>/` — full body plus the comment thread.
- **Commenting** — `CommentForm` on the detail page; the author is taken from `request.user`,
  never from the submitted form, so a crafted `author=` field cannot impersonate anyone.
- **Create / edit / delete** — `POST /post/new/`, `/post/<pk>/edit/`, and `/post/<pk>/delete/`
  with a confirmation step before removal.
- **Author-or-staff permission rule** — a single `_can_manage()` helper in `board/views.py`
  gates editing and deleting. Unauthorised requests redirect to the post instead of returning
  403, so URLs do not disclose which posts belong to other people.
- **Login and logout** — Django's `LoginView` with a `registration/login.html` template, and
  `LogoutView` reached through a POST form as Django 5+ requires.
- **Session-based auth gating** — `@login_required` on write views; anonymous visitors can read
  but are redirected to `/login/?next=...` when they try to post.
- **Django admin registration** — `PostAdmin` with `title / author / created_at` list display and
  `Comment` inlined; standalone `CommentAdmin` too.
- **Base template with inline CSS** — header, navigation, and authenticated-user strip. No static
  assets, no CSS framework.
- **`README.md`** — setup, routes, permissions model, and project layout.

### Changed

- `config/settings.py` — registered `board` in `INSTALLED_APPS`, set `ALLOWED_HOSTS = ['*']` for
  all-interface binding, pinned `DEFAULT_AUTO_FIELD` to `BigAutoField` to silence the
  `startapp` warning, and added `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL`.
- `config/urls.py` — replaced the starter admin-only URLconf with the board routes and auth views.

### Notes

- Database is a single SQLite file, `db.sqlite3`, at the repository root.
- The server is intended to run as `python manage.py runserver 0.0.0.0:7111`.
- `DEBUG = True`, weak seeded passwords, and no rate limiting make this development-only. It was
  verified working but never hardened.
- `board/tests.py` remains the empty `startapp` stub — no automated tests yet.

### Verified

Behaviour was checked against a live server over HTTP, not just by reading the code:

- Anonymous `GET /` → 200; anonymous `GET /post/new/` → 302 to the login page.
- Correct credentials log in; a wrong password re-renders the form with an error and no session.
- `user` created a post, added a comment, and edited their own post.
- A spoofed `author=` field in the comment POST was ignored — the comment stayed attributed to
  the logged-in user.
- `admin` saw edit/delete links on `user`'s post and could reach `/admin/`; `user` could not.
- `user` requesting edit or delete on an admin-owned post was redirected away.
- `admin` deleting a post removed it, and the detail page then returned 404.
