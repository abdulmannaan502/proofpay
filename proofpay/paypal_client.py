"""PayPal Orders v2 + Payments v2 client used by ProofPay's escrow flow.

Money flow per milestone
------------------------
1. create_order(intent=AUTHORIZE)  -> client approves on PayPal (payer-action link)
2. authorize_order(order_id)       -> funds are HELD on the client's account
3a. capture_authorization(auth_id) -> AI verified the work, freelancer is paid
3b. void_authorization(auth_id)    -> milestone cancelled, hold released to client

If no sandbox credentials are configured the client runs in DEMO mode: every
call returns a response with the same shape as the real API so the rest of
the app (and the AI agent's tool calls) behave identically.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from dataclasses import dataclass, field

import requests

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE = "https://api-m.paypal.com"


class PayPalError(RuntimeError):
    pass


def _rand_id(prefix: str = "", n: int = 17) -> str:
    return (prefix + uuid.uuid4().hex.upper())[: n + len(prefix)]


@dataclass
class PayPalClient:
    client_id: str | None = None
    client_secret: str | None = None
    environment: str = "sandbox"
    timeout: int = 20
    _token: str | None = field(default=None, repr=False)
    _token_expiry: float = field(default=0.0, repr=False)
    _demo_orders: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ setup
    @classmethod
    def from_env(cls, secrets: dict | None = None) -> "PayPalClient":
        secrets = secrets or {}
        get = lambda k: secrets.get(k) or os.getenv(k)  # noqa: E731
        return cls(
            client_id=get("PAYPAL_CLIENT_ID"),
            client_secret=get("PAYPAL_CLIENT_SECRET"),
            environment=(get("PAYPAL_ENV") or "sandbox").lower(),
        )

    @property
    def demo(self) -> bool:
        return not (self.client_id and self.client_secret)

    @property
    def base(self) -> str:
        return LIVE_BASE if self.environment == "live" else SANDBOX_BASE

    @property
    def mode_label(self) -> str:
        if self.demo:
            return "Demo mode (simulated PayPal responses)"
        return f"PayPal {self.environment.title()} (live API calls)"

    # ------------------------------------------------------------------ auth
    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = requests.post(
            f"{self.base}/v1/oauth2/token",
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "client_credentials"},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise PayPalError(f"OAuth failed ({r.status_code}): {r.text[:300]}")
        body = r.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + int(body.get("expires_in", 3000))
        return self._token

    def _call(self, method: str, path: str, json: dict | None = None, idem: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if idem:
            headers["PayPal-Request-Id"] = idem
        r = requests.request(method, f"{self.base}{path}", headers=headers, json=json, timeout=self.timeout)
        if r.status_code >= 400:
            raise PayPalError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        return r.json() if r.text else {}

    # ------------------------------------------------------------ orders API
    def create_order(
        self,
        *,
        amount: float,
        currency: str,
        reference_id: str,
        description: str,
        return_url: str,
        cancel_url: str,
    ) -> dict:
        """Create an AUTHORIZE-intent order. Returns {id, status, approve_url, raw}."""
        payload = {
            "intent": "AUTHORIZE",
            "purchase_units": [
                {
                    "reference_id": reference_id[:256],
                    "custom_id": reference_id[:127],
                    "description": description[:127],
                    "soft_descriptor": "PROOFPAY ESCROW",
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": "ProofPay",
                        "user_action": "PAY_NOW",
                        "shipping_preference": "NO_SHIPPING",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }
        if self.demo:
            oid = _rand_id(n=17)
            self._demo_orders[oid] = {"amount": amount, "currency": currency}
            raw = {
                "id": oid,
                "intent": "AUTHORIZE",
                "status": "PAYER_ACTION_REQUIRED",
                "links": [{"rel": "payer-action", "href": f"{return_url}?token={oid}&demo=1"}],
                "request": payload,
            }
        else:
            raw = self._call("POST", "/v2/checkout/orders", payload, idem=f"create-{reference_id}-{uuid.uuid4().hex[:8]}")
        approve = next((l["href"] for l in raw.get("links", []) if l.get("rel") in ("payer-action", "approve")), None)
        return {"id": raw["id"], "status": raw.get("status"), "approve_url": approve, "raw": raw}

    def get_order(self, order_id: str) -> dict:
        if self.demo:
            return {"id": order_id, "status": "APPROVED"}
        return self._call("GET", f"/v2/checkout/orders/{order_id}")

    def authorize_order(self, order_id: str) -> dict:
        """Place the hold after the payer approved. Returns {authorization_id, status, expires, raw}."""
        if self.demo:
            info = self._demo_orders.get(order_id, {"amount": 0, "currency": "USD"})
            auth_id = _rand_id(n=17)
            raw = {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "authorizations": [
                                {
                                    "id": auth_id,
                                    "status": "CREATED",
                                    "amount": {"currency_code": info["currency"], "value": f"{info['amount']:.2f}"},
                                    "expiration_time": time.strftime(
                                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 29 * 86400)
                                    ),
                                }
                            ]
                        }
                    }
                ],
            }
        else:
            raw = self._call("POST", f"/v2/checkout/orders/{order_id}/authorize", {}, idem=f"auth-{order_id}")
        auth = raw["purchase_units"][0]["payments"]["authorizations"][0]
        return {
            "authorization_id": auth["id"],
            "status": auth.get("status"),
            "expires": auth.get("expiration_time"),
            "raw": raw,
        }

    # ---------------------------------------------------------- payments API
    def capture_authorization(self, authorization_id: str, note: str = "") -> dict:
        """Release held funds to the freelancer (merchant account)."""
        payload = {"final_capture": True, "note_to_payer": note[:255] or "Milestone verified by ProofPay"}
        if self.demo:
            raw = {"id": _rand_id(n=17), "status": "COMPLETED", "final_capture": True}
        else:
            raw = self._call(
                "POST", f"/v2/payments/authorizations/{authorization_id}/capture", payload, idem=f"cap-{authorization_id}"
            )
        return {"capture_id": raw.get("id"), "status": raw.get("status"), "raw": raw}

    def void_authorization(self, authorization_id: str) -> dict:
        """Cancel the hold so the client gets their money back."""
        if self.demo:
            raw = {"id": authorization_id, "status": "VOIDED"}
        else:
            raw = self._call("POST", f"/v2/payments/authorizations/{authorization_id}/void", None, idem=f"void-{authorization_id}")
            raw = raw or {"id": authorization_id, "status": "VOIDED"}
        return {"status": raw.get("status", "VOIDED"), "raw": raw}

    def get_authorization(self, authorization_id: str) -> dict:
        if self.demo:
            return {"id": authorization_id, "status": "CREATED"}
        return self._call("GET", f"/v2/payments/authorizations/{authorization_id}")
