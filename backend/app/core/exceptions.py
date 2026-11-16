"""Domain exceptions. Services raise these; the API layer maps them to HTTP codes."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class ForbiddenError(DomainError):
    status_code = 403


class AuthenticationError(DomainError):
    status_code = 401


class InvalidTokenError(DomainError):
    """The scanned QR token is malformed, forged or expired."""

    status_code = 400


class TooManyAttemptsError(DomainError):
    status_code = 429
