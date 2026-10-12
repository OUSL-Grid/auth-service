from src.core.exceptions import *

def extract_domain(self, email: str) -> str:
    if "@" not in email:
        raise DomainNotAllowedError(f"`{email}` is not a valid email address")
    return email.rsplit("@", 1)[-1].lower().strip()

def extract_domain01(email: str) -> str:
    if "@" not in email:
        raise DomainNotAllowedError(f"`{email}` is not a valid email address")
    return email.rsplit("@", 1)[-1].lower().strip()

b = "user@ousl.lk"
a = extract_domain(b)
print(a)

