import os
import logging
import razorpay
import razorpay.errors

from .provider import PaymentProvider, OrderResult

logger = logging.getLogger(__name__)


class RazorpayAdapter(PaymentProvider):
    """Razorpay Payment Links implementation."""

    def __init__(self):
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self._client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(
        self,
        amount_paise: int,
        currency: str,
        reference_id: str,
        callback_url: str,
    ) -> OrderResult:
        """Create a Razorpay Payment Link. Returns link_id and hosted short_url."""
        data = {
            "amount": amount_paise,
            "currency": currency,
            "reference_id": reference_id,
            "callback_url": callback_url,
            "callback_method": "get",
        }
        response = self._client.payment_link.create(data)
        logger.info("Created Razorpay payment link %s", response["id"])
        return OrderResult(link_id=response["id"], short_url=response["short_url"])

    def verify_payment(self, params: dict) -> bool:
        """Verify Razorpay callback signature. Returns True if valid, False if tampered.

        params keys expected (from st.query_params after redirect):
            razorpay_payment_id, razorpay_payment_link_id,
            razorpay_payment_link_reference_id,
            razorpay_payment_link_status, razorpay_signature
        """
        sdk_params = {
            "payment_link_id": params.get("razorpay_payment_link_id"),
            "payment_link_reference_id": params.get("razorpay_payment_link_reference_id"),
            "payment_link_status": params.get("razorpay_payment_link_status"),
            "razorpay_payment_id": params.get("razorpay_payment_id"),
            "razorpay_signature": params.get("razorpay_signature"),
        }
        try:
            self._client.utility.verify_payment_link_signature(sdk_params)
            logger.info("Payment verified: %s", params.get("razorpay_payment_id"))
            return True
        except razorpay.errors.SignatureVerificationError:
            logger.warning("Payment signature verification failed for params: %s", params)
            return False
