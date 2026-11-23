# SKAT Service — MVP 1

Django 6.1.3 + PostgreSQL + Django Templates + HTMX + Bootstrap 5. The first increment implements:

1. Users are created by admins in Django Admin.
2. Admins create parts with name and price.
3. Authorized users browse/search parts and add up to 999 units of each part to a cart.
4. The cart supports updating quantities, deleting rows, and checkout.
5. Users see only their own order history and order details.
6. Admins inspect all orders and their line items in Django Admin (read-only).

## Run using Docker (recommended on Ubuntu 24.04)

Requirements: Docker Engine and `docker compose` plugin. On your machine:

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Put the generated string in `DJANGO_SECRET_KEY` in `.env`. Replace `POSTGRES_PASSWORD` too.

```bash
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

The web container applies migrations at startup.

Web app: http://localhost:8000/login/ ; order history: http://localhost:8000/orders/ ; admin: http://localhost:8000/admin/ .
Ports bind **only to 127.0.0.1**, so on a remote VM use an SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 your-user@your-server
```

Then visit http://localhost:8000 on your own computer. Create regular accounts using Admin → Users; they should have `is_staff=False`. Create parts using Admin → Parts. Regular users can log in and place orders. Default database survives `docker compose down` because it uses a named volume. **Do not run `docker compose down -v` unless you intend to delete the database.**

## Run locally without Docker

Use Python 3.13 with SQLite for local development. Django reads the environment directly. The `.env` file is used by Docker Compose. Ensure `DATABASE_ENGINE` is set to `sqlite` when running locally.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export DJANGO_DEBUG=1 DATABASE_ENGINE=sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

On Windows PowerShell, use `py -3.13 -m venv .venv` and activate with `.\.venv\Scripts\Activate.ps1`. Set `$env:DJANGO_DEBUG = "1"` and `$env:DATABASE_ENGINE = "sqlite"` before running Django commands.

## Architecture

See [Architecture](docs/architecture.md) for the data model, session cart and checkout flow.

- Django built-in User (no self-registration) and session authentication.
- Parts: name, price. No SKU, stock, groups or file attachments yet.
- Session cart with quantity 1..999. Prices are **never** accepted from browser input.
- On checkout, new Order + OrderItem snapshots are saved atomically, including item name, price and quantity. History survives edits/deletions of catalog parts.
- Orders are read-only in Django Admin; no statuses, payment processing, stock reservation, emails or external API yet.
- No separate frontend build step; HTML forms work without JavaScript, HTMX enhances updates. Bootstrap/HTMX are currently loaded from public CDNs. Bundle them locally before offline or restricted-network production use.
- Docker Compose launches Django's *development* `runserver`, not a production-ready HTTP stack. Before publishing: DEBUG=0, hardened Nginx+Gunicorn, HTTPS, static files, backups, logging, rate limiting and proper ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS. No Docker publication port is exposed to the internet in this MVP.

## Tests

Run the same checks as GitHub Actions in the local environment configured above.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

To verify with PostgreSQL, prefix each command with `docker compose exec web`. Django creates a separate test database, so the configured PostgreSQL user needs permission to create databases.

## Next planned iterations (not implemented)

- Parts categories and search/filter refinement.
- Equipment models, assembly diagrams and diagram positions.
- Orders lifecycle, admin order processing, notifications and integrations.
- Integration with 1C, external APIs and advanced access roles.
