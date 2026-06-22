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


class LeadNotFoundError(LeadCenterError):
    def __init__(self, lead_id: str) -> None:
        self.lead_id = lead_id
        super().__init__(f"lead {lead_id} not found")


# --- Outreach (step 5) -----------------------------------------------------

class OutreachDisabledError(LeadCenterError):
    """Outreach is behind a feature flag and is currently off."""


class PitchRequiredError(LeadCenterError):
    """A lead must have a drafted pitch before it can be contacted."""


class LowConfidenceError(LeadCenterError):
    """The lead's confidence is below the auto-send threshold."""

    def __init__(self, confidence: int, threshold: int) -> None:
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(f"confidence {confidence} below contact threshold {threshold}")


class EmailNotFoundError(LeadCenterError):
    """No email could be found for the lead."""


class EmailUnverifiedError(LeadCenterError):
    """An email was found but could not be verified — never send to it."""


class SuppressedError(LeadCenterError):
    """The recipient is on the suppression list (opt-out or hard bounce)."""


class ComplianceConfigError(LeadCenterError):
    """Required CAN-SPAM data (e.g. physical address) is not configured."""
