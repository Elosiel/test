"""Domain/application errors. Framework-free so any layer can raise/catch them."""
from __future__ import annotations


class LeadCenterError(Exception):
    """Base class for all expected, handled errors."""


class InsufficientCreditsError(LeadCenterError):
    def __init__(self, account_id: str, required: int, available: int) -> None:
        self.account_id = account_id
        self.required = required
        self.available = available
        super().__init__(
            f"account {account_id} needs {required} credits but has {available}"
        )


class ConfirmationRequiredError(LeadCenterError):
    """Raised by confirm-before-spend gates when the caller has not confirmed the
    estimated cost. Carries the estimate so the UI can show "N leads = N credits".
    """

    def __init__(self, estimated_cost: int) -> None:
        self.estimated_cost = estimated_cost
        super().__init__(f"confirmation required: this will spend {estimated_cost} credits")
