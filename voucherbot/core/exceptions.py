class VoucherBotException(Exception):
    """Base exception for VoucherBot."""


class DatabaseError(VoucherBotException):
    """Database related error."""


class ConfigurationError(VoucherBotException):
    """Configuration related error."""
