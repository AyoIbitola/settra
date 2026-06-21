"""Custom domain exception classes."""


class InvalidStateTransitionError(Exception):
    """Raised when an invoice status transition is not in the allowed-transitions table."""

    pass


class PaymentTargetGenerationError(Exception):
    """Raised when a Bitnob call to generate a payment target fails."""

    pass


class BitnobAPIError(Exception):
    """Raised when any Bitnob API call returns an unexpected error."""

    pass


class DuplicateResourceError(Exception):
    """Raised when attempting to create a resource that already exists (e.g. duplicate email)."""

    pass
