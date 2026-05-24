"""Tests for ISIN check-digit validation."""

import pytest

from pea_audit.isin import isin_check_digit_valid


# Real-world ISINs that should pass.
VALID = [
    "FR001400U5Q4",  # Amundi PEA Monde
    "FR0011440478",  # Amundi PEA MSCI EM
    "FR0011550185",  # BNP Easy S&P 500
    "FR0013412269",  # Amundi PEA US Tech
    "LU2655993207",  # Amundi MSCI World Swap
    "IE00B5BMR087",  # iShares Core S&P 500
    "IE00B4L5Y983",  # iShares Core MSCI World
    "IE00B3XXRP09",  # Vanguard S&P 500
    "US0378331005",  # Apple
]

# Plausibly-formed but check-digit-invalid (Gemma vision misreads we caught).
INVALID = [
    "FR00140056U4",  # off-by-one from FR001400U5Q4
    "FR0014005GU4",  # another misread of the same
    "AA0000000000",  # all zeros after country code — fails check digit
    "XX1234567890",  # not a real country code, but format-valid
    "FR12345",       # too short
    "fr001400U5Q4",  # lowercase — regex rejects
    "FR001400U5Q!",  # bad char
]


@pytest.mark.parametrize("isin", VALID)
def test_valid_isins(isin: str) -> None:
    assert isin_check_digit_valid(isin), f"{isin} should be valid"


@pytest.mark.parametrize("isin", INVALID)
def test_invalid_isins(isin: str) -> None:
    assert not isin_check_digit_valid(isin), f"{isin} should be invalid"
