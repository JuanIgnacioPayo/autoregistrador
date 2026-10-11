from typing import List, Optional
import httpx

from user_forge.core.models import Persona, Account
from user_forge.core.vault import Vault
from user_forge.modules.seeders.base import BaseSeeder

class SupabaseSeeder(BaseSeeder):
    """
    Direct seeder for Supabase projects using the GoTrue / Auth Admin API.
    Can use either:
    1. Service Role Key (Admin signup: /auth/v1/admin/users) - auto-confirms email.
    2. Public Anon Key (User signup: /auth/v1/signup)
    """
    def __init__(
        self,
        project_id: str,
        supabase_url: str,
        service_role_key: Optional[str] = None,
        anon_key: Optional[str] = None,
        auto_confirm_email: bool = True,
        vault: Optional[Vault] = None,
        **kwargs
    ):
        super().__init__(project_id, **kwargs)
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.anon_key = anon_key
        self.auto_confirm_email = auto_confirm_email
        self.vault = vault or Vault()

    def seed_personas(self, personas: List[Persona]) -> List[Account]:
        created_accounts: List[Account] = []
        is_admin = bool(self.service_role_key)
        api_key = self.service_role_key or self.anon_key

        if not api_key:
            raise ValueError("Either service_role_key or anon_key must be provided for SupabaseSeeder.")

        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        with httpx.Client(timeout=15.0) as client:
            for persona in personas:
                payload = {
                    "email": persona.email,
                    "password": persona.password,
                    "user_metadata": {
                        "full_name": persona.full_name,
                        "username": persona.username,
                        "bio": persona.bio,
                        "gender": persona.gender,
                        "city": persona.city,
                        "country": persona.country
                    }
                }

                if is_admin:
                    endpoint = f"{self.supabase_url}/auth/v1/admin/users"
                    if self.auto_confirm_email:
                        payload["email_confirm"] = True
                else:
                    endpoint = f"{self.supabase_url}/auth/v1/signup"

                try:
                    res = client.post(endpoint, json=payload, headers=headers)
                    if res.status_code in (200, 201):
                        data = res.json()
                        supa_id = data.get("id") or (data.get("user") and data["user"].get("id"))
                        meta = persona.metadata or {}
                        meta["supabase_uid"] = supa_id
                        meta["seeder"] = "SupabaseSeeder"
                        persona.metadata = meta

                        account = self.vault.save_persona_as_account(
                            persona=persona,
                            project_id=self.project_id,
                            platform_name="supabase",
                            status="SEEDED"
                        )
                    else:
                        meta = persona.metadata or {}
                        meta["error"] = res.text
                        persona.metadata = meta
                        account = self.vault.save_persona_as_account(
                            persona=persona,
                            project_id=self.project_id,
                            platform_name="supabase",
                            status="FAILED"
                        )
                except Exception as ex:
                    meta = persona.metadata or {}
                    meta["error"] = str(ex)
                    persona.metadata = meta
                    account = self.vault.save_persona_as_account(
                        persona=persona,
                        project_id=self.project_id,
                        platform_name="supabase",
                        status="FAILED"
                    )

                created_accounts.append(account)

        return created_accounts
