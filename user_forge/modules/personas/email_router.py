import re
from typing import Optional
from user_forge.config.settings import settings

class EmailRouter:
    """
    Handles generating valid emails using either:
    1. Direct domain catch-all: {alias}@{domain}
    2. Plus-addressing: {user}+{alias}@{domain} (ideal for Gmail, Fastmail, Proton, Cloudflare Email Routing)
    """
    def __init__(
        self,
        domain: Optional[str] = None,
        catchall_base: Optional[str] = None,
        strategy: Optional[str] = None
    ):
        self.domain = domain or settings.DEFAULT_EMAIL_DOMAIN
        self.catchall_base = catchall_base or settings.DEFAULT_CATCHALL_BASE
        self.strategy = strategy or settings.EMAIL_STRATEGY

    def clean_alias(self, raw_str: str) -> str:
        # Lowercase and replace non-alphanumeric with dots or hyphens
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', raw_str.lower())
        return cleaned or "usr"

    def generate_email(self, username: str, project_id: Optional[str] = None) -> str:
        tag_parts = []
        if project_id:
            tag_parts.append(self.clean_alias(project_id))
        tag_parts.append(self.clean_alias(username))
        alias = ".".join(tag_parts)

        if self.strategy == "plus":
            if "@" in self.catchall_base:
                base_user, base_domain = self.catchall_base.split("@", 1)
                return f"{base_user}+{alias}@{base_domain}"
            return f"{self.catchall_base}+{alias}@{self.domain}"
        else:
            return f"{alias}@{self.domain}"
