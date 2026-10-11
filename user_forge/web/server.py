import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
import time
import threading
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_file

from user_forge.config.settings import settings
from user_forge.core.vault import Vault
from user_forge.modules.personas.generator import PersonaGenerator
from user_forge.modules.seeders.sql_seeder import SQLSeeder
from user_forge.modules.seeders.supabase_seeder import SupabaseSeeder
from user_forge.modules.browser_bot.browser_manager import BrowserManager
from user_forge.modules.browser_bot.form_filler import FormFiller, copy_to_windows_clipboard
from user_forge.modules.browser_bot.session_saver import SessionSaver
from user_forge.modules.export.exporter import Exporter

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static")
)

# Global active registration session tracking for UI interaction
active_sessions = {}

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response

@app.route("/api/<path:dummy>", methods=["OPTIONS"])
def handle_options(dummy):
    return "", 200

def get_vault():
    return Vault()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary", methods=["GET"])
def api_summary():
    vault = get_vault()
    accounts = vault.list_accounts()
    projects = list(set(a.project_id for a in accounts))
    status_counts = {}
    for a in accounts:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1
    return jsonify({
        "total_accounts": len(accounts),
        "projects_count": len(projects),
        "projects": projects,
        "status_counts": status_counts
    })

@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    project = request.args.get("project")
    status = request.args.get("status")
    vault = get_vault()
    accounts = vault.list_accounts(project_id=project or None, status=status or None)
    
    result = []
    for a in accounts:
        dec_pass = vault.get_decrypted_password(a)
        data = a.model_dump()
        data["password"] = dec_pass
        data.pop("password_encrypted", None)
        data["has_session"] = False
        if a.profile_dir:
            summary = SessionSaver.get_state_summary(Path(a.profile_dir))
            data["has_session"] = summary.get("exists", False)
            data["cookies_count"] = summary.get("cookies", 0)
        else:
            data["cookies_count"] = 0
        result.append(data)
    return jsonify(result)

@app.route("/api/accounts/create", methods=["POST"])
def api_create_account():
    payload = request.json or {}
    project = payload.get("project_id", "default").strip() or "default"
    email = payload.get("email", "").strip()
    username = payload.get("username", "").strip()
    password = payload.get("password", "").strip()
    full_name = payload.get("full_name", "").strip() or username or (email.split("@")[0] if "@" in email else "Master")
    platform_name = payload.get("platform_name", "custom").strip()
    status = payload.get("status", "ACTIVE").strip() or "ACTIVE"

    if not email:
        return jsonify({"success": False, "error": "El email es obligatorio"}), 400

    if not username:
        username = email.split("@")[0].replace(".", "_")

    if not password:
        from user_forge.modules.personas.generator import PersonaGenerator
        password = PersonaGenerator().generate_secure_password(16)

    vault = get_vault()
    account = vault.save_account(
        project_id=project,
        username=username,
        email=email,
        password=password,
        full_name=full_name,
        platform_name=platform_name,
        status=status,
        metadata={"is_master": payload.get("is_master", True)}
    )

    dec_pass = vault.get_decrypted_password(account)
    acc_data = account.model_dump()
    acc_data["password"] = dec_pass
    acc_data.pop("password_encrypted", None)
    return jsonify({"success": True, "account": acc_data})

@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
def api_delete_account(account_id: int):
    vault = get_vault()
    success = vault.delete_account(account_id)
    return jsonify({"success": success})

@app.route("/api/accounts/<int:account_id>", methods=["PUT", "POST"])
def api_update_account(account_id: int):
    payload = request.json or {}
    vault = get_vault()
    account = vault.update_account(
        account_id=account_id,
        username=payload.get("username"),
        email=payload.get("email"),
        password=payload.get("password") or None,
        full_name=payload.get("full_name"),
        project_id=payload.get("project_id"),
        status=payload.get("status"),
        birth_date=payload.get("birth_date"),
        metadata=payload.get("metadata")
    )
    if not account:
        return jsonify({"success": False, "error": "Cuenta no encontrada"}), 404

    dec_pass = vault.get_decrypted_password(account)
    acc_data = account.model_dump()
    acc_data["password"] = dec_pass
    acc_data.pop("password_encrypted", None)
    return jsonify({"success": True, "account": acc_data})

@app.route("/api/accounts/<int:account_id>/password", methods=["POST"])
def api_update_account_password(account_id: int):
    payload = request.json or {}
    new_pass = payload.get("password", "").strip()
    if not new_pass:
        return jsonify({"success": False, "error": "Contraseña vacía"}), 400
    vault = get_vault()
    enc_pass = vault.encrypt(new_pass)
    with vault._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET password_encrypted = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (enc_pass, account_id))
        conn.commit()
    return jsonify({"success": True})

@app.route("/api/personas/generate", methods=["POST"])
def api_generate_personas():
    payload = request.json or {}
    project = payload.get("project", "default").strip()
    count = int(payload.get("count", 1))
    role_hint = payload.get("role_hint") or None
    email_domain = payload.get("email_domain") or None
    email_strategy = payload.get("email_strategy") or None

    gen = PersonaGenerator()
    personas = gen.generate_batch(
        count=count,
        project_id=project,
        role_hint=role_hint,
        email_domain=email_domain,
        email_strategy=email_strategy
    )

    vault = get_vault()
    created = []
    for p in personas:
        acc = vault.save_persona_as_account(
            persona=p,
            project_id=project,
            platform_name="custom",
            status="PENDING"
        )
        dec_pass = vault.get_decrypted_password(acc)
        acc_dict = acc.model_dump()
        acc_dict["password"] = dec_pass
        created.append(acc_dict)

    return jsonify({"success": True, "count": len(created), "accounts": created})

@app.route("/api/seed/sql", methods=["POST"])
def api_seed_sql():
    payload = request.json or {}
    project = payload.get("project", "default").strip()
    count = int(payload.get("count", 5))
    db_path = payload.get("db_path", "test_app.db").strip()
    table = payload.get("table", "users").strip()

    gen = PersonaGenerator()
    personas = gen.generate_batch(count=count, project_id=project)
    
    vault = get_vault()
    seeder = SQLSeeder(project_id=project, db_url=db_path, table_name=table, vault=vault)
    created = seeder.seed_personas(personas)
    
    successful = [a for a in created if a.status == "SEEDED"]
    return jsonify({
        "success": True,
        "seeded_count": len(successful),
        "total_requested": count,
        "db_path": db_path
    })

@app.route("/api/seed/supabase", methods=["POST"])
def api_seed_supabase():
    payload = request.json or {}
    project = payload.get("project", "default").strip()
    count = int(payload.get("count", 5))
    url = payload.get("url", "").strip()
    key = payload.get("key", "").strip()

    if not url or not key:
        return jsonify({"success": False, "error": "Supabase URL y Service Key son requeridos"}), 400

    gen = PersonaGenerator()
    personas = gen.generate_batch(count=count, project_id=project)
    
    vault = get_vault()
    seeder = SupabaseSeeder(project_id=project, supabase_url=url, service_role_key=key, vault=vault)
    try:
        created = seeder.seed_personas(personas)
        successful = [a for a in created if a.status == "SEEDED"]
        return jsonify({
            "success": True,
            "seeded_count": len(successful),
            "total_requested": count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/browser/start-assisted", methods=["POST"])
def api_start_assisted():
    payload = request.json or {}
    account_id = int(payload.get("account_id"))
    url = payload.get("url", "").strip()
    platform_label = payload.get("platform_name", "").strip()

    if not url:
        return jsonify({"success": False, "error": "URL requerida"}), 400

    vault = get_vault()
    account = vault.get_account_by_id(account_id)
    if not account:
        return jsonify({"success": False, "error": "Cuenta no encontrada"}), 404

    browser_channel = payload.get("browser_channel", "system_default").strip()

    if browser_channel == "system_default":
        import webbrowser
        copy_to_windows_clipboard(account.email)
        try:
            webbrowser.open(url)
        except Exception:
            os.system(f'start "" "{url}"')
        return jsonify({
            "success": True,
            "mode": "system_default",
            "message": "Enlace abierto en tu navegador habitual y email copiado al portapapeles."
        })

    session_key = str(account_id)
    if session_key in active_sessions:
        old_sess = active_sessions[session_key]
        try:
            if old_sess.get("context"):
                old_sess["context"].close()
            if old_sess.get("playwright"):
                old_sess["playwright"].stop()
        except Exception:
            pass
        del active_sessions[session_key]

    active_sessions[session_key] = {
        "status": "RUNNING",
        "account_id": account_id,
        "username": account.username,
        "url": url,
        "platform_label": platform_label or urlparse(url).netloc or "web",
        "step": f"Lanzando {browser_channel.upper()} con perfil aislado...",
        "context": None,
        "playwright": None,
        "profile_dir": None,
        "fill_report": {}
    }

    def run_browser():
        try:
            print(f"[BROWSER] Starting assisted registration for {account.username} ({url}) with channel={browser_channel}...", flush=True)
            password = vault.get_decrypted_password(account)
            manager = BrowserManager()
            prof_dir = manager.get_profile_path(account.project_id, account.username)
            active_sessions[session_key]["profile_dir"] = prof_dir

            print(f"[BROWSER] Launching Playwright persistent context (channel={browser_channel})...", flush=True)
            pw, ctx = manager.launch_persistent_context(
                project_id=account.project_id,
                username=account.username,
                headless=False,
                channel=browser_channel
            )
            active_sessions[session_key]["playwright"] = pw
            active_sessions[session_key]["context"] = ctx

            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # Clean shutdown listener when user closes the window manually
            def on_page_close(p):
                print(f"[BROWSER] User closed window for {account.username}.")
                try:
                    ctx.close()
                except Exception:
                    pass
                try:
                    pw.stop()
                except Exception:
                    pass
                if session_key in active_sessions:
                    active_sessions[session_key]["status"] = "IDLE"
                    active_sessions[session_key]["step"] = "Ventana cerrada"

            page.on("close", on_page_close)

            print(f"[BROWSER] Navigating to {url}...")
            active_sessions[session_key]["step"] = "Cargando página..."
            filler = FormFiller(page)
            filler.inject_copilot_bar(account, password)
            copy_to_windows_clipboard(account.email)

            try:
                page.goto(url, timeout=35000, wait_until="domcontentloaded")
            except Exception as nav_e:
                print(f"[BROWSER] Initial goto notice: {nav_e}")

            print(f"[BROWSER] Page loaded! Filling form fields...")
            report = filler.fill_signup_form(account, password)
            active_sessions[session_key]["fill_report"] = report
            active_sessions[session_key]["step"] = "Copilot activo en la ventana. Completa los pasos en el navegador..."
            print(f"[BROWSER] Ready! Report: {report}")

            # Keep watching page to auto-fill subsequent steps as user navigates
            def watch_and_fill():
                for _ in range(25):
                    time.sleep(2.0)
                    if session_key not in active_sessions or active_sessions[session_key].get("status") != "RUNNING":
                        break
                    try:
                        if not page.is_closed():
                            filler.fill_signup_form(account, password)
                        else:
                            break
                    except Exception:
                        break

            threading.Thread(target=watch_and_fill, daemon=True).start()
        except Exception as err:
            import traceback
            traceback.print_exc()
            err_msg = str(err).encode("ascii", errors="replace").decode("ascii")
            print(f"[BROWSER ERROR] {err_msg}")
            active_sessions[session_key]["status"] = "ERROR"
            active_sessions[session_key]["error"] = err_msg

    t = threading.Thread(target=run_browser, daemon=True)
    t.start()

    return jsonify({"success": True, "message": "Navegador abierto en tu pantalla", "account_id": account_id})

@app.route("/api/browser/save-session", methods=["POST"])
def api_save_session():
    payload = request.json or {}
    account_id = int(payload.get("account_id"))
    session_key = str(account_id)

    if session_key not in active_sessions:
        return jsonify({"success": False, "error": "No hay una sesión activa para esta cuenta"}), 400

    sess = active_sessions[session_key]
    ctx = sess.get("context")
    pw = sess.get("playwright")
    prof_dir = sess.get("profile_dir")

    try:
        if ctx and prof_dir:
            saver = SessionSaver()
            saver.save_session_state(ctx, prof_dir)
            summary = saver.get_state_summary(prof_dir)
            ctx.close()
        if pw:
            pw.stop()

        vault = get_vault()
        account = vault.get_account_by_id(account_id)
        vault.update_account_status(account_id, status="ACTIVE", profile_dir=str(prof_dir))
        target_url = sess.get("url", "")
        domain = urlparse(target_url).netloc or "web"
        platform_label = sess.get("platform_label") or domain

        current_meta = (account.metadata if account else {}) or {}
        registered_platforms = current_meta.get("registered_platforms", [])
        # Check if already present, otherwise add
        existing_idx = next((i for i, p in enumerate(registered_platforms) if p.get("domain") == domain or p.get("name") == platform_label), None)
        platform_entry = {
            "name": platform_label,
            "domain": domain,
            "url": target_url,
            "registered_at": str(current_meta.get("updated_at") or "")
        }
        if existing_idx is not None:
            registered_platforms[existing_idx] = platform_entry
        else:
            registered_platforms.append(platform_entry)

        vault.update_account_metadata(account_id, {
            "signup_url": target_url,
            "last_domain": domain,
            "registered_platforms": registered_platforms
        })

        sess["status"] = "SAVED"
        del active_sessions[session_key]

        return jsonify({
            "success": True,
            "message": "Sesión guardada con éxito. La cuenta ahora está ACTIVA.",
            "cookies_saved": summary.get("cookies", 0) if prof_dir else 0
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/browser/open-session", methods=["POST"])
def api_open_saved_session():
    payload = request.json or {}
    account_id = int(payload.get("account_id"))
    vault = get_vault()
    account = vault.get_account_by_id(account_id)
    if not account:
        return jsonify({"success": False, "error": "Cuenta no encontrada"}), 404

    manager = BrowserManager()
    target_url = payload.get("url") or account.metadata.get("signup_url") or "https://google.com"

    def run_session():
        pw, ctx = manager.launch_persistent_context(
            project_id=account.project_id,
            username=account.username,
            headless=False
        )
        page = ctx.new_page()
        page.goto(target_url)

    t = threading.Thread(target=run_session, daemon=True)
    t.start()

    return jsonify({"success": True, "message": f"Navegador abierto con cookies y perfil de {account.username}"})

@app.route("/api/browser/session-status/<account_id>", methods=["GET"])
def api_session_status(account_id):
    sess = active_sessions.get(str(account_id))
    if not sess:
        return jsonify({"active": False})
    return jsonify({
        "active": True,
        "status": sess.get("status"),
        "step": sess.get("step"),
        "fill_report": sess.get("fill_report"),
        "error": sess.get("error")
    })

@app.route("/api/export", methods=["GET"])
def api_export():
    project = request.args.get("project") or None
    fmt = (request.args.get("format") or "json").lower()
    vault = get_vault()
    accounts = vault.list_accounts(project_id=project)
    exporter = Exporter(vault)

    if fmt == "json":
        data = exporter.export_json(accounts)
        return jsonify(json.loads(data))
    elif fmt == "csv":
        data = exporter.export_csv(accounts)
        from flask import Response
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=userforge_accounts.csv"}
        )
    elif fmt == "bitwarden":
        data = exporter.export_bitwarden(accounts)
        from flask import Response
        return Response(
            data,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=userforge_bitwarden.csv"}
        )
    return jsonify({"error": "Formato no válido"}), 400

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
