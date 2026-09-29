"""Errors shared by calendar refresh and lifecycle callers."""


class GenerationError(Exception):
    """A requested dashboard update could not be completed."""
