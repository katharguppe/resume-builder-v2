from .provider import PaymentProvider, OrderResult


class StripeAdapter(PaymentProvider):
    """Stripe payment adapter — not yet implemented."""

    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        raise NotImplementedError(
            "Stripe adapter not implemented. Set PAYMENT_PROVIDER=razorpay."
        )

    def verify_payment(self, params: dict) -> bool:
        raise NotImplementedError(
            "Stripe adapter not implemented. Set PAYMENT_PROVIDER=razorpay."
        )
