# Codex instructions for SKAT Service MVP

- Language: Python 3.13; Django 6.1.3; PostgreSQL in Docker; SQLite only as a local fallback.
- UI: server-rendered Django Templates, HTMX for progressive enhancements, Bootstrap 5. Do not introduce Vue, React, SPA or Django REST Framework without a concrete requirement.
- Make small, reviewable changes and cover new behavior and bug fixes with Django tests.
- Preserve the existing architecture unless a change is justified by a concrete need. Change existing business rules only when the task explicitly requires it.
- Every browser state-changing request must use POST and CSRF; never trust browser-submitted price or totals.
- Only authenticated users can view the catalog, cart and order history; order detail always filters by request.user.
- Order totals and per-line unit prices are immutable snapshots created in transaction.atomic().
- All money uses DecimalField / decimal.Decimal, never floats.
- Cart is stored in the Django session for the MVP, quantities 1..999.
- New features should fit apps parts/ or orders/ if possible; avoid unnecessary new layers until complexity justifies them.
- Admin may manage users and parts; submitted orders are view-only in admin.
- Do not access production infrastructure, edit production data, or deploy to production without explicit approval.
- Before completing a task, run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test`. Report any check you could not run and why.
