from src.core.exceptions import DomainNotAllowedError


class DomainWhitelist:

    def __init__(self, allowed_domains: list[str], allow_edu_wildcard: bool = False):
        self.allowed_domains = {d.lower().strip() for d in allowed_domains}
        self.allow_edu_wildcard = allow_edu_wildcard

    def extract_domain(self, email: str) -> str:
        if "@" not in email:
            raise DomainNotAllowedError(f"`{email}` is not a valid email address")
        return email.rsplit("@", 1)[-1].lower().strip()

    def is_allowed(self, email: str) -> bool:
        domain = self.extract_domain(email)

        if domain in self.allowed_domains:
            return True

        if self.allow_edu_wildcard and domain.endswith(".edu"):
            return True

        return False

    def validate(self, email: str) -> str:
        """
        Raises DomainNotAllowedError with a clear message if the email's
        domain isn't whitelisted. Returns the validated domain on success
        (callers store this in Users.verified_domain).
        """
        domain = self.extract_domain(email)
        if not self.is_allowed(email):
            raise DomainNotAllowedError(
                f"Email domain '{domain}' is not authorized for this platform. "
                f"Please use your university email address."
            )
        return domain


    