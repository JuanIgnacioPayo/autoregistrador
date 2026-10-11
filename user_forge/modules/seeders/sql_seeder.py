import sqlite3
from typing import List, Optional
import bcrypt

from user_forge.core.models import Persona, Account
from user_forge.core.vault import Vault
from user_forge.modules.seeders.base import BaseSeeder

class SQLSeeder(BaseSeeder):
    """
    Direct SQL seeder supporting SQLite and PostgreSQL (via connection string / sqlite db).
    Inserts users into the target users table with bcrypt-hashed passwords,
    and registers the created accounts into the UserForge Vault.
    """
    def __init__(
        self,
        project_id: str,
        db_url: str,
        table_name: str = "users",
        vault: Optional[Vault] = None,
        **kwargs
    ):
        super().__init__(project_id, **kwargs)
        self.db_url = db_url
        self.table_name = table_name
        self.vault = vault or Vault()

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def _ensure_sqlite_table(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                bio TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

    def seed_personas(self, personas: List[Persona]) -> List[Account]:
        created_accounts: List[Account] = []
        
        # Support sqlite filepath or sqlite:/// URI
        clean_path = self.db_url
        if clean_path.startswith("sqlite:///"):
            clean_path = clean_path.replace("sqlite:///", "")

        conn = sqlite3.connect(clean_path)
        try:
            self._ensure_sqlite_table(conn)
            cursor = conn.cursor()

            for persona in personas:
                hashed = self.hash_password(persona.password)
                try:
                    cursor.execute(f"""
                        INSERT INTO {self.table_name} (username, email, password_hash, full_name, bio)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        persona.username,
                        persona.email,
                        hashed,
                        persona.full_name,
                        persona.bio
                    ))
                    conn.commit()
                    target_db_id = cursor.lastrowid

                    # Save to local UserForge Vault
                    meta = persona.metadata or {}
                    meta["target_db_id"] = target_db_id
                    meta["seeder"] = "SQLSeeder"
                    persona.metadata = meta

                    account = self.vault.save_persona_as_account(
                        persona=persona,
                        project_id=self.project_id,
                        platform_name=f"sql:{self.table_name}",
                        status="SEEDED"
                    )
                    created_accounts.append(account)
                except Exception as e:
                    # Account might already exist or constraint violation
                    meta = persona.metadata or {}
                    meta["error"] = str(e)
                    persona.metadata = meta
                    account = self.vault.save_persona_as_account(
                        persona=persona,
                        project_id=self.project_id,
                        platform_name=f"sql:{self.table_name}",
                        status="FAILED"
                    )
                    created_accounts.append(account)
        finally:
            conn.close()

        return created_accounts
