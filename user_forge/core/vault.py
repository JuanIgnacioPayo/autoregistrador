import os
import json
import sqlite3
import contextlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from cryptography.fernet import Fernet
from user_forge.config.settings import settings
from user_forge.core.models import Account, Persona

class Vault:
    def __init__(self, db_path: Optional[str] = None, key_path: Optional[str] = None):
        self.db_path = str(db_path or settings.DB_PATH)
        self.key_path = str(key_path or settings.KEY_PATH)
        self.cipher = self._init_cipher()
        self._init_db()

    def _init_cipher(self) -> Fernet:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(key)
        return Fernet(key)

    def encrypt(self, plain_text: str) -> str:
        return self.cipher.encrypt(plain_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, cipher_text: str) -> str:
        return self.cipher.decrypt(cipher_text.encode("utf-8")).decode("utf-8")

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    platform_name TEXT NOT NULL DEFAULT 'custom',
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password_encrypted TEXT NOT NULL,
                    full_name TEXT,
                    bio TEXT,
                    profile_dir TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_project ON accounts(project_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform_name);
            """)
            conn.commit()

    def save_persona_as_account(
        self,
        persona: Persona,
        project_id: str,
        platform_name: str = "custom",
        profile_dir: Optional[str] = None,
        status: str = "PENDING"
    ) -> Account:
        enc_pass = self.encrypt(persona.password)
        meta_dict = persona.metadata or {}
        meta_dict.update({
            "gender": persona.gender,
            "birth_date": persona.birth_date,
            "phone": persona.phone,
            "city": persona.city,
            "country": persona.country
        })
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (
                    project_id, platform_name, username, email, password_encrypted,
                    full_name, bio, profile_dir, status, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                project_id,
                platform_name,
                persona.username,
                persona.email,
                enc_pass,
                persona.full_name,
                persona.bio,
                profile_dir,
                status,
                json.dumps(meta_dict)
            ))
            account_id = cursor.lastrowid
            conn.commit()
            
        return self.get_account_by_id(account_id)

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_account(row)

    def list_accounts(
        self,
        project_id: Optional[str] = None,
        platform_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Account]:
        query = "SELECT * FROM accounts WHERE 1=1"
        params: list = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if platform_name:
            query += " AND platform_name = ?"
            params.append(platform_name)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_account(r) for r in rows]

    def update_account_status(self, account_id: int, status: str, profile_dir: Optional[str] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if profile_dir:
                cursor.execute("""
                    UPDATE accounts 
                    SET status = ?, profile_dir = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (status, profile_dir, account_id))
            else:
                cursor.execute("""
                    UPDATE accounts 
                    SET status = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (status, account_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_account_metadata(self, account_id: int, new_metadata: Dict[str, Any]) -> bool:
        account = self.get_account_by_id(account_id)
        if not account:
            return False
        meta = account.metadata or {}
        meta.update(new_metadata)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts 
                SET metadata_json = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (json.dumps(meta), account_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_account(self, account_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_decrypted_password(self, account: Account) -> str:
        return self.decrypt(account.password_encrypted)

    def _row_to_account(self, row: sqlite3.Row) -> Account:
        meta = {}
        if row["metadata_json"]:
            try:
                meta = json.loads(row["metadata_json"])
            except Exception:
                meta = {}
        return Account(
            id=row["id"],
            project_id=row["project_id"],
            platform_name=row["platform_name"],
            username=row["username"],
            email=row["email"],
            password_encrypted=row["password_encrypted"],
            full_name=row["full_name"],
            bio=row["bio"],
            profile_dir=row["profile_dir"],
            status=row["status"],
            metadata=meta,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
