# SKAT Service architecture

SKAT Service is an authenticated parts catalog with a session cart, checkout and personal order history. Staff create accounts and maintain the catalog in Django Admin. The MVP has no self-registration, payments, order lifecycle or public API.

## Stack and application boundaries

Python 3.13 and Django 6.1.3 provide routing, authentication, sessions, the ORM and Django Admin. Docker Compose runs the development server with PostgreSQL 17. SQLite supports local development and GitHub Actions. Django Templates render HTML and Bootstrap 5 styles it. HTMX updates cart fragments, with ordinary HTML form submissions available when JavaScript is disabled.

- `parts` owns the catalog, name search, stock availability and admin management of parts and balances.
- `orders` owns the session cart, checkout, personal order history and the admin order views.

## Data and access

- Django's built-in user model supplies accounts. Django session authentication protects catalog, cart and order views. Order history and order details filter by the authenticated user. Browser operations that change state use POST with CSRF protection.
- `Part` stores a catalog name and a decimal unit price in rubles. Its optional UUID `external_id` identifies a nomenclature entry in 1C and is unique when present. The optional text `code` preserves leading zeros and may repeat across parts. `is_active` defaults to true and is reserved for future catalog rules.
- `StockBalance` stores one balance per part for a single warehouse. `quantity` has three decimal places and accepts positive, zero, negative and null values. Optional `source_version`, `source_updated_at` and `received_at` record the snapshot's version, time in the source and receipt time. Deleting a part deletes its balance.
- `SyncState` stores the last successful synchronization timestamp by type. The `stock` key identifies the one state shared by all parts and leaves room for future synchronization types.
- `Order` belongs to a user and stores the creation time, final total and a unique checkout token for new orders. An order protects its user from deletion. Existing orders can have a null token.
- `OrderItem` belongs to an order and stores the part name, unit price and quantity at checkout. Its optional link to the catalog part becomes null on catalog deletion. Historical names, prices and totals remain available after catalog changes.

Staff with the appropriate permissions manage users, parts and exact stock balances in Django Admin. Synchronization state is view-only there. Orders and line items are view-only there. Customers can change their session carts and view their own submitted orders through the customer interface.

## Stock availability

The catalog compares `SyncState.last_success_at` to Django's `timezone.now()` using `STOCK_SYNC_MAX_AGE_MINUTES` (15 minutes by default). If the last success is at most that old, positive quantities yield **В наличии** and zero or negative quantities yield **Нет в наличии**. A missing balance, null quantity or missing or stale synchronization timestamp yields **Наличие уточняется**. The age of the individual balance does not affect its status.

The catalog reads the global timestamp once and annotates the parts query with text labels. Exact quantities stay in the database during rendering. Cart and checkout rules use order quantities from 1 to 999 independently of the activity flag and warehouse balance.

## Cart and checkout

Django's database-backed session stores the cart as a mapping from part IDs to integer quantities from 1 to 999. The cart displays current catalog prices. If a part is deleted, its row can be removed through the cart and checkout waits until it is removed.

Each cart update changes the checkout token carried by the form. Checkout rejects a stale form unless its token already identifies an order owned by the current user, in which case it opens that order. The database enforces token uniqueness so two submissions of the same form cannot create two orders. This guard is scoped to the submitted cart version. A new cart can place an identical order.

Checkout validates cart quantities, reads the current catalog records and calculates totals using decimal arithmetic. The order and its line snapshots are written in one transaction. PostgreSQL locks the selected catalog rows during that transaction. After success, the cart is cleared and the response redirects to the order detail.

## Planned integration

The HTTP API, data exchange and scheduled jobs for 1C are planned for a future iteration. Tests and development environments can set the global timestamp in Django shell:

```python
from django.utils import timezone
from parts.models import SyncState

SyncState.objects.update_or_create(
    kind=SyncState.Kind.STOCK,
    defaults={"last_success_at": timezone.now()},
)
```

Set this timestamp after a successful complete stock update when implementing the integration. Until the first success is recorded, the catalog shows **Наличие уточняется**.
