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
        self.catchall_base = catchall_base or settings.DEFAULT_CATCHALL_BASE
        if not domain and catchall_base and "@" in catchall_base:
            self.domain = catchall_base.split("@", 1)[1]
        else:
            self.domain = domain or settings.DEFAULT_EMAIL_DOMAIN
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

        # If user provides a full email (e.g. 'proyecto.beta.de@gmail.com'), always use plus-addressing
        if "@" in self.domain:
            target_user, target_domain = self.domain.split("@", 1)
            return f"{target_user}+{alias}@{target_domain}"

        if self.strategy == "plus":
            target_user = "user"
            target_domain = self.domain
            if "@" in self.catchall_base:
                base_u, base_d = self.catchall_base.split("@", 1)
                target_user = base_u
                if self.domain == settings.DEFAULT_EMAIL_DOMAIN:
                    target_domain = base_d
            return f"{target_user}+{alias}@{target_domain}"
        else:
            return f"{alias}@{self.domain}"

