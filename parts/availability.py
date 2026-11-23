from datetime import timedelta

from django.conf import settings
from django.db.models import Case, CharField, Value, When
from django.utils import timezone

from .models import SyncState


def with_availability(parts):
    last_success_at = (
        SyncState.objects.filter(pk=SyncState.Kind.STOCK)
        .values_list("last_success_at", flat=True)
        .first()
    )
    cutoff = timezone.now() - timedelta(minutes=settings.STOCK_SYNC_MAX_AGE_MINUTES)
    unknown = Value("Наличие уточняется")
    if last_success_at is None or last_success_at < cutoff:
        return parts.annotate(availability=unknown)

    return parts.annotate(
        availability=Case(
            When(stock_balance__quantity__gt=0, then=Value("В наличии")),
            When(stock_balance__quantity__lte=0, then=Value("Нет в наличии")),
            default=unknown,
            output_field=CharField(),
        )
    )
