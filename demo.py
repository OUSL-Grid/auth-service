from src.core.exceptions import *

def extract_domain(email: str) -> str:
        if "@" not in email:
            raise DomainNotAllowedError(f"`{email}` is not a valid email address")
        return email.rsplit("@", 1)[-1].lower().strip()

b = "user@ousl.lk"
a = extract_domain(b)
print(a)

