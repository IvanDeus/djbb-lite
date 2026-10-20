# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

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
