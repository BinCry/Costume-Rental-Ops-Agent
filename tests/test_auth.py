import pytest

from app.auth import require_actor, resolve_actor
from app.errors import AppError


def test_customer_actor_context_is_accepted() -> None:
    actor = resolve_actor("customer-id", "customer,shared")
    assert actor.user_id == "customer-id"
    assert actor.audiences == ("customer", "shared")


def test_staff_actor_context_is_accepted() -> None:
    actor = resolve_actor("staff-id", "staff_internal,shared")
    assert actor.user_id == "staff-id"
    assert actor.audiences == ("staff_internal", "shared")


def test_guest_gets_customer_safe_audiences() -> None:
    actor = resolve_actor("guest", "customer,shared")
    assert actor.user_id == "guest"
    assert actor.audiences == ("customer", "shared")


@pytest.mark.parametrize(
    ("actor_id", "audiences"),
    [
        (None, "customer,shared"),
        ("customer-id", None),
        ("customer-id", "customer,unknown"),
        ("customer-id", "customer,customer,shared"),
        ("customer-id", "shared"),
        ("guest", "staff_internal,shared"),
    ],
)
def test_invalid_actor_context_is_rejected(
    actor_id: str | None,
    audiences: str | None,
) -> None:
    with pytest.raises(AppError) as error:
        resolve_actor(actor_id, audiences)
    assert error.value.status_code == 400
    assert error.value.code == "INVALID_ACTOR_CONTEXT"


def test_internal_search_rejects_guest_context() -> None:
    guest = resolve_actor("guest", "customer,shared")
    with pytest.raises(AppError) as error:
        require_actor(guest)
    assert error.value.status_code == 401
    assert error.value.code == "AUTHENTICATED_ACTOR_REQUIRED"


def test_internal_search_accepts_authenticated_context() -> None:
    customer = resolve_actor("customer-id", "customer,shared")
    assert require_actor(customer) == customer
