import csv
import json
from pathlib import Path
from typing import List, Optional
from user_forge.core.models import Account
from user_forge.core.vault import Vault

class Exporter:
    """
    Exports vault accounts to CSV, JSON, or password manager formats (Bitwarden / 1Password).
    """
    def __init__(self, vault: Optional[Vault] = None):
        self.vault = vault or Vault()

    def export_json(self, accounts: List[Account], output_path: Optional[str] = None, include_passwords: bool = True) -> str:
        data = []
        for acc in accounts:
            acc_data = acc.model_dump()
            if include_passwords:
                acc_data["password"] = self.vault.get_decrypted_password(acc)
            acc_data.pop("password_encrypted", None)
            if acc_data.get("created_at"):
                acc_data["created_at"] = str(acc_data["created_at"])
            if acc_data.get("updated_at"):
                acc_data["updated_at"] = str(acc_data["updated_at"])
            data.append(acc_data)

        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str

    def export_csv(self, accounts: List[Account], output_path: Optional[str] = None) -> str:
        fields = ["id", "project_id", "platform_name", "username", "email", "password", "full_name", "status", "profile_dir"]
        rows = []
        for acc in accounts:
            rows.append({
                "id": acc.id,
                "project_id": acc.project_id,
                "platform_name": acc.platform_name,
                "username": acc.username,
                "email": acc.email,
                "password": self.vault.get_decrypted_password(acc),
                "full_name": acc.full_name or "",
                "status": acc.status,
                "profile_dir": acc.profile_dir or ""
            })

        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        csv_str = output.getvalue()

        if output_path:
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_str)
        return csv_str

    def export_bitwarden(self, accounts: List[Account], output_path: Optional[str] = None) -> str:
        """
        Bitwarden standard CSV format:
        folder,favorite,type,name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp
        """
        import io
        fields = [
            "folder", "favorite", "type", "name", "notes",
            "fields", "reprompt", "login_uri", "login_username", "login_password", "login_totp"
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()

        for acc in accounts:
            writer.writerow({
                "folder": acc.project_id,
                "favorite": 0,
                "type": "login",
                "name": f"{acc.platform_name} - {acc.username}",
                "notes": f"Full name: {acc.full_name or ''}\nEmail: {acc.email}\nBio: {acc.bio or ''}",
                "fields": "",
                "reprompt": 0,
                "login_uri": "",
                "login_username": acc.username or acc.email,
                "login_password": self.vault.get_decrypted_password(acc),
                "login_totp": ""
            })

        csv_str = output.getvalue()
        if output_path:
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                f.write(csv_str)
        return csv_str
