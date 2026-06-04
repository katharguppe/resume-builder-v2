import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OrderResult:
    link_id: str    # Razorpay payment_link_id — store in DB
    short_url: str  # rzp.io/i/xxx — open in browser


class PaymentProvider(ABC):
    @abstractmethod
    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        """Create a hosted payment link. Returns link_id and short_url."""

    @abstractmethod
    def verify_payment(self, params: dict) -> bool:
        """Verify payment callback params. Returns True if signature valid.

        Expected param keys (Razorpay):
            razorpay_payment_id, razorpay_payment_link_id,
            razorpay_payment_link_reference_id,
            razorpay_payment_link_status, razorpay_signature
        """


def get_payment_provider() -> PaymentProvider:
    """Factory: reads PAYMENT_PROVIDER env var, returns the correct adapter."""
    provider = os.getenv("PAYMENT_PROVIDER", "razorpay").lower()
    if provider == "razorpay":
        from .razorpay_adapter import RazorpayAdapter
        return RazorpayAdapter()
    if provider == "stripe":
        from .stripe_adapter import StripeAdapter
        return StripeAdapter()
    raise ValueError(f"Unknown PAYMENT_PROVIDER: {provider!r}. Expected 'razorpay' or 'stripe'.")
