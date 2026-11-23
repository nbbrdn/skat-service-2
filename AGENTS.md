# Codex instructions for SKAT Service MVP

- Language: Python 3.13; Django 6.1.3; PostgreSQL in Docker; SQLite only as a local fallback.
- UI: server-rendered Django Templates, HTMX for progressive enhancements, Bootstrap 5. Do not introduce Vue, React, SPA or Django REST Framework without a concrete requirement.
- Make small, reviewable changes; each business behavior requires a Django test.
- Every browser state-changing request must use POST and CSRF; never trust browser-submitted price or totals.
- Only authenticated users can view the catalog, cart and order history; order detail always filters by request.user.
- Order totals and per-line unit prices are immutable snapshots created in transaction.atomic().
- All money uses DecimalField / decimal.Decimal, never floats.
- Cart is stored in the Django session for the MVP, quantities 1..999.
- New features should fit apps parts/ or orders/ if possible; avoid unnecessary new layers until complexity justifies them.
- Admin may manage users and parts; submitted orders are view-only in admin.
- Do not edit production data or deploy from a development machine without explicit approval.
- Run `python manage.py test` and `python manage.py check` before considering a task complete.
