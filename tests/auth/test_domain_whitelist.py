import pytest

from src.auth.domain_whitelist import DomainWhitelist
from src.core.exceptions import DomainNotAllowedError


@pytest.fixture
def whitelist() -> DomainWhitelist:
    return DomainWhitelist(allowed_domains=["ousl.lk", "student.ousl.lk"])


@pytest.fixture
def whitelist_with_edu_wildcard() -> DomainWhitelist:
    return DomainWhitelist(allowed_domains=["ousl.lk"], allow_edu_wildcard=True)


def test_validate_allowed_domain_success(whitelist: DomainWhitelist):
    domain = whitelist.validate("student@ousl.lk")
    assert domain == "ousl.lk"


def test_validate_rejects_non_whitelisted_domain(whitelist: DomainWhitelist):
    with pytest.raises(DomainNotAllowedError):
        whitelist.validate("someone@gmail.com")


def test_validate_error_message_is_clear(whitelist: DomainWhitelist):
    with pytest.raises(DomainNotAllowedError) as exc_info:
        whitelist.validate("someone@gmail.com")
    assert "gmail.com" in str(exc_info.value)


def test_validate_case_insensitive(whitelist: DomainWhitelist):
    """Emails with mixed-case domains should still match."""
    domain = whitelist.validate("student@OUSL.LK")
    assert domain == "ousl.lk"


def test_validate_rejects_malformed_email(whitelist: DomainWhitelist):
    with pytest.raises(DomainNotAllowedError):
        whitelist.validate("not-an-email")


def test_edu_wildcard_allows_any_edu_domain(whitelist_with_edu_wildcard: DomainWhitelist):
    domain = whitelist_with_edu_wildcard.validate("student@mit.edu")
    assert domain == "mit.edu"


def test_edu_wildcard_still_rejects_non_edu(whitelist_with_edu_wildcard: DomainWhitelist):
    with pytest.raises(DomainNotAllowedError):
        whitelist_with_edu_wildcard.validate("someone@gmail.com")


def test_edu_wildcard_disabled_by_default():
    """When allow_edu_wildcard isn't set, arbitrary .edu domains should NOT pass
    unless explicitly whitelisted."""
    strict_whitelist = DomainWhitelist(allowed_domains=["ousl.lk"])
    with pytest.raises(DomainNotAllowedError):
        strict_whitelist.validate("student@mit.edu")


def test_is_allowed_returns_bool_without_raising(whitelist: DomainWhitelist):
    assert whitelist.is_allowed("student@ousl.lk") is True
    assert whitelist.is_allowed("someone@gmail.com") is False