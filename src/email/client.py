from abc import ABC, abstractmethod

class EmailClient(ABC):
    @abstractmethod
    async def send_magic_link(self, to_email: str, link_url: str) -> None:
        ...

class ConsoleEmailClient(EmailClient):
    # TODO: Dev/test stand-in — prints instead of sending. Swap for a real provider (SES, Resend, SMTP) via the same interface later.

    async def send_magic_link(self, to_email: str, link_url: str) -> None:
        print(f"[DEV EMAIL] Magic link for {to_email}: {link_url}")
