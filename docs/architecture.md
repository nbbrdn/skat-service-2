# SKAT Service architecture

SKAT Service is an authenticated parts catalog with a session cart, checkout and personal order history. Staff create accounts and maintain the catalog in Django Admin. The MVP has no self-registration, inventory tracking, payments, order lifecycle or public API.

## Stack and application boundaries

Python 3.13 and Django 6.1.3 provide routing, authentication, sessions, the ORM and Django Admin. Docker Compose runs the development server with PostgreSQL 17. SQLite supports local development and GitHub Actions. Django Templates render HTML and Bootstrap 5 styles it. HTMX updates cart fragments, with ordinary HTML form submissions available when JavaScript is disabled.

- `parts` owns the catalog, name search and admin management of `Part`.
- `orders` owns the session cart, checkout, personal order history and the admin order views.

## Data and access

- Django's built-in user model supplies accounts. Django session authentication protects catalog, cart and order views. Order history and order details filter by the authenticated user. Browser operations that change state use POST with CSRF protection.
- `Part` stores a catalog name and a decimal unit price in rubles.
- `Order` belongs to a user and stores the creation time, final total and a unique checkout token for new orders. An order protects its user from deletion. Existing orders can have a null token.
- `OrderItem` belongs to an order and stores the part name, unit price and quantity at checkout. Its optional link to the catalog part becomes null on catalog deletion. Historical names, prices and totals remain available after catalog changes.

Staff with the appropriate permissions manage users and parts in Django Admin. Orders and line items are view-only there. Customers can change their session carts and view their own submitted orders through the customer interface.

## Cart and checkout

Django's database-backed session stores the cart as a mapping from part IDs to integer quantities from 1 to 999. The cart displays current catalog prices. If a part is deleted, its row can be removed through the cart and checkout waits until it is removed.

Each cart update changes the checkout token carried by the form. Checkout rejects a stale form unless its token already identifies an order owned by the current user, in which case it opens that order. The database enforces token uniqueness so two submissions of the same form cannot create two orders. This guard is scoped to the submitted cart version. A new cart can place an identical order.

Checkout validates cart quantities, reads the current catalog records and calculates totals using decimal arithmetic. The order and its line snapshots are written in one transaction. PostgreSQL locks the selected catalog rows during that transaction. After success, the cart is cleared and the response redirects to the order detail.

## Planned integration

Integration with 1C is planned. The design of data exchange will be determined in a future iteration.
