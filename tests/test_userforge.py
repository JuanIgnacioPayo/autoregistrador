import os
import tempfile
import pytest
from user_forge.core.models import Persona
from user_forge.core.vault import Vault
from user_forge.modules.personas.generator import PersonaGenerator
from user_forge.modules.personas.email_router import EmailRouter
from user_forge.modules.seeders.sql_seeder import SQLSeeder
from user_forge.modules.export.exporter import Exporter

def test_persona_generation():
    router = EmailRouter(catchall_base="team@startup.com", strategy="plus")
    gen = PersonaGenerator(email_router=router)
    personas = gen.generate_batch(count=5, project_id="testproj")
    
    assert len(personas) == 5
    for p in personas:
        assert len(p.first_name) > 0
        assert len(p.last_name) > 0
        assert len(p.password) == 16
        assert "team+testproj." in p.email
        assert "@startup.com" in p.email
        assert any(c.isupper() for c in p.password)
        assert any(c.islower() for c in p.password)
        assert any(c.isdigit() for c in p.password)

def test_vault_encryption_and_crud():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_vault.db")
        key_path = os.path.join(tmp_dir, ".key")
        vault = Vault(db_path=db_path, key_path=key_path)

        gen = PersonaGenerator()
        persona = gen.generate_one(project_id="portal")

        account = vault.save_persona_as_account(persona, project_id="portal")
        assert account.id is not None
        assert account.username == persona.username
        
        # Verify encryption in db vs decrypted password
        assert account.password_encrypted != persona.password
        decrypted = vault.get_decrypted_password(account)
        assert decrypted == persona.password

        # Update status
        vault.update_account_status(account.id, status="ACTIVE", profile_dir="/tmp/prof")
        updated = vault.get_account_by_id(account.id)
        assert updated.status == "ACTIVE"
        assert updated.profile_dir == "/tmp/prof"

def test_sql_seeder():
    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_db = os.path.join(tmp_dir, "vault.db")
        vault_key = os.path.join(tmp_dir, ".key")
        target_db = os.path.join(tmp_dir, "app_users.db")
        
        vault = Vault(db_path=vault_db, key_path=vault_key)
        seeder = SQLSeeder(project_id="app_v1", db_url=target_db, vault=vault)
        
        gen = PersonaGenerator()
        personas = gen.generate_batch(count=3, project_id="app_v1")
        accounts = seeder.seed_personas(personas)
        
        assert len(accounts) == 3
        for acc in accounts:
            assert acc.status == "SEEDED"

def test_exporter():
    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_db = os.path.join(tmp_dir, "vault.db")
        vault_key = os.path.join(tmp_dir, ".key")
        vault = Vault(db_path=vault_db, key_path=vault_key)
        
        gen = PersonaGenerator()
        p = gen.generate_one(project_id="export_test")
        vault.save_persona_as_account(p, project_id="export_test")
        
        accounts = vault.list_accounts(project_id="export_test")
        exporter = Exporter(vault)
        
        json_out = exporter.export_json(accounts)
        assert p.username in json_out
        assert p.password in json_out
        
        csv_out = exporter.export_csv(accounts)
        assert p.username in csv_out
        
        bw_out = exporter.export_bitwarden(accounts)
        assert "login" in bw_out
        assert p.username in bw_out
