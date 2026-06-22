"""Currency conversion tool (keyless) — live ECB rates via Frankfurter.app."""

from __future__ import annotations

from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class CurrencyInput(BaseModel):
    amount: float = Field(1.0, description="Amount to convert.")
    from_currency: str = Field(..., description="ISO 4217 code, e.g. 'USD'.")
    to_currency: str = Field(..., description="ISO 4217 code, e.g. 'JPY'.")


class CurrencyTool(BaseTool):
    name: str = "currency_convert"
    description: str = (
        "Convert an amount between currencies using live ECB reference rates "
        "(no API key). Use it to localise budgets and quote costs in the "
        "traveler's home currency. Input: amount, from_currency, to_currency "
        "(ISO codes like USD, EUR, JPY, GBP)."
    )
    args_schema: Type[BaseModel] = CurrencyInput

    def _run(self, amount: float = 1.0, from_currency: str = "USD", to_currency: str = "EUR") -> str:
        src = from_currency.upper().strip()
        dst = to_currency.upper().strip()
        if src == dst:
            return f"{amount:.2f} {src} = {amount:.2f} {dst} (same currency)."
        try:
            resp = httpx.get(
                "https://api.frankfurter.dev/v1/latest",
                params={"amount": amount, "from": src, "to": dst},
                timeout=20,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
            rate_resp = data.get("rates", {})
            if dst not in rate_resp:
                return (
                    f"[Rate {src}->{dst} unavailable from the live source "
                    f"(supported: major currencies). Estimate from knowledge.]"
                )
            converted = rate_resp[dst]
            unit = converted / amount if amount else converted
            return (
                f"{amount:.2f} {src} = {converted:.2f} {dst} "
                f"(live ECB rate: 1 {src} = {unit:.4f} {dst}, date {data.get('date', 'latest')})."
            )
        except Exception as exc:
            return (
                f"[Live currency conversion failed ({exc}). Use an approximate "
                f"{src}->{dst} rate from your knowledge and flag it as approximate.]"
            )
