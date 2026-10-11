import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from user_forge.config.settings import settings
from user_forge.core.vault import Vault
from user_forge.modules.personas.generator import PersonaGenerator
from user_forge.modules.seeders.sql_seeder import SQLSeeder
from user_forge.modules.seeders.supabase_seeder import SupabaseSeeder
from user_forge.modules.browser_bot.browser_manager import BrowserManager
from user_forge.modules.browser_bot.form_filler import FormFiller
from user_forge.modules.browser_bot.session_saver import SessionSaver
from user_forge.modules.export.exporter import Exporter

app = typer.Typer(
    name="UserForge",
    help="Modular Identity & Account Provisioning Engine",
    add_completion=False
)
console = Console()

@app.command("create-persona")
def create_persona(
    project: str = typer.Option(..., "--project", "-p", help="Target project identifier (e.g. salieris, brand1)"),
    count: int = typer.Option(1, "--count", "-c", help="Number of personas to generate"),
    role_hint: Optional[str] = typer.Option(None, "--role", "-r", help="Role or bio flavor hint (e.g. 'Tech Lead')"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Custom email domain"),
    strategy: Optional[str] = typer.Option(None, "--strategy", "-s", help="Email routing strategy: 'plus' or 'direct'")
):
    """
    Generate realistic user profiles with es_AR localization and save to Vault.
    """
    console.print(Panel(f"[bold cyan]UserForge Persona Generator[/bold cyan]\nProject: [green]{project}[/green] | Count: [yellow]{count}[/yellow]"))
    
    gen = PersonaGenerator()
    vault = Vault()
    personas = gen.generate_batch(
        count=count,
        project_id=project,
        role_hint=role_hint,
        email_domain=domain,
        email_strategy=strategy
    )

    table = Table(title=f"Created Personas for Project '{project}'", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Full Name", style="bold")
    table.add_column("Username", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("City", style="dim")

    for p in personas:
        acc = vault.save_persona_as_account(
            persona=p,
            project_id=project,
            platform_name="custom",
            status="PENDING"
        )
        table.add_row(str(acc.id), acc.full_name or "", acc.username, acc.email, p.city or "")

    console.print(table)
    console.print(f"[bold green][OK] Successfully stored {count} personas in local encrypted vault.[/bold green]")


@app.command("list-accounts")
def list_accounts(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project ID"),
    platform: Optional[str] = typer.Option(None, "--platform", help="Filter by platform"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status")
):
    """
    List accounts stored in the local encrypted vault.
    """
    vault = Vault()
    accounts = vault.list_accounts(project_id=project, platform_name=platform, status=status)

    if not accounts:
        console.print("[yellow]No accounts found matching criteria.[/yellow]")
        return

    table = Table(title="Vault Accounts", show_header=True, header_style="bold blue")
    table.add_column("ID", width=6)
    table.add_column("Project", style="magenta")
    table.add_column("Platform", style="cyan")
    table.add_column("Username", style="bold")
    table.add_column("Email", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Profile Dir", style="dim")

    for acc in accounts:
        prof_info = Path(acc.profile_dir).name if acc.profile_dir else "-"
        table.add_row(
            str(acc.id),
            acc.project_id,
            acc.platform_name,
            acc.username,
            acc.email,
            acc.status,
            prof_info
        )

    console.print(table)


@app.command("signup-assisted")
def signup_assisted(
    account_id: int = typer.Option(..., "--account-id", "-a", help="Account ID from vault to register"),
    url: str = typer.Option(..., "--url", "-u", help="Registration URL"),
    headless: bool = typer.Option(False, "--headless", help="Run browser headlessly (not recommended for assisted mode)")
):
    """
    Launch isolated browser profile, auto-fill registration fields, and pause for CAPTCHA/SMS verification.
    """
    vault = Vault()
    account = vault.get_account_by_id(account_id)
    if not account:
        console.print(f"[bold red]Account with ID {account_id} not found in vault![/bold red]")
        raise typer.Exit(1)

    password = vault.get_decrypted_password(account)
    manager = BrowserManager()
    profile_dir = manager.get_profile_path(account.project_id, account.username)

    console.print(Panel(
        f"[bold cyan]Launching Assisted Registration[/bold cyan]\n"
        f"Project: [magenta]{account.project_id}[/magenta]\n"
        f"Target URL: [blue]{url}[/blue]\n"
        f"Username: [green]{account.username}[/green]\n"
        f"Email: [yellow]{account.email}[/yellow]\n"
        f"Profile: [dim]{profile_dir}[/dim]"
    ))

    playwright, context = manager.launch_persistent_context(
        project_id=account.project_id,
        username=account.username,
        headless=headless
    )

    try:
        page = context.new_page()
        console.print(f"[bold green]Navigating to {url}...[/bold green]")
        page.goto(url, wait_until="domcontentloaded", timeout=settings.BROWSER_TIMEOUT_MS)

        filler = FormFiller(page)
        fill_report = filler.fill_signup_form(account, password)
        console.print(f"[bold cyan]Auto-fill Report:[/bold cyan] {fill_report}")

        console.print("\n[bold yellow]════════════════════════════════════════════════════════════════[/bold yellow]")
        console.print("[bold red blink] [ACTION NEEDED] [/bold red blink] [bold white]Interact with the browser window:[/bold white]")
        console.print(" 1. Review or complete any remaining fields.")
        console.print(" 2. Solve any CAPTCHA, 2FA or SMS verification.")
        console.print(" 3. Submit the registration / Confirm login.")
        console.print("[bold yellow]════════════════════════════════════════════════════════════════[/bold yellow]\n")

        typer.prompt("Press ENTER when you have completed registration/login to capture session")

        # Save session cookies & state
        saver = SessionSaver()
        saver.save_session_state(context, profile_dir)
        summary = saver.get_state_summary(profile_dir)

        # Update Vault status
        vault.update_account_status(account_id, status="ACTIVE", profile_dir=str(profile_dir))
        # Update platform_name with domain of the URL
        from urllib.parse import urlparse
        domain = urlparse(url).netloc or "web"
        vault.update_account_metadata(account_id, {"signup_url": url, "last_domain": domain})

        console.print(f"[bold green][OK] Session state successfully captured! ({summary['cookies']} cookies saved).[/bold green]")
        console.print(f"[bold green][OK] Account #{account_id} marked as ACTIVE in Vault.[/bold green]")

    finally:
        context.close()
        playwright.stop()


@app.command("open-session")
def open_session(
    account_id: int = typer.Option(..., "--account-id", "-a", help="Account ID to launch session for"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to navigate to (optional)")
):
    """
    Re-opens an isolated browser with pre-loaded cookies and storage state.
    """
    vault = Vault()
    account = vault.get_account_by_id(account_id)
    if not account:
        console.print(f"[bold red]Account #{account_id} not found in vault![/bold red]")
        raise typer.Exit(1)

    manager = BrowserManager()
    profile_dir = Path(account.profile_dir) if account.profile_dir else manager.get_profile_path(account.project_id, account.username)

    console.print(Panel(
        f"[bold cyan]Re-opening Session Profile[/bold cyan]\n"
        f"Account: #{account.id} ({account.username})\n"
        f"Project: {account.project_id}\n"
        f"Profile: {profile_dir}"
    ))

    target_url = url or account.metadata.get("signup_url") or "https://google.com"

    playwright, context = manager.launch_persistent_context(
        project_id=account.project_id,
        username=account.username,
        headless=False
    )

    try:
        page = context.new_page()
        page.goto(target_url)
        console.print(f"[bold green]Session active on {target_url}. Browser window is open.[/bold green]")
        typer.prompt("Press ENTER when you want to finish and save updated session state")
        SessionSaver.save_session_state(context, profile_dir)
        console.print(f"[bold green][OK] Updated session saved.[/bold green]")
    finally:
        context.close()
        playwright.stop()


@app.command("seed-sql")
def seed_sql(
    project: str = typer.Option(..., "--project", "-p", help="Target project identifier"),
    db_url: str = typer.Option(..., "--db", "-d", help="SQLite database path or connection URL"),
    count: int = typer.Option(5, "--count", "-c", help="Number of users to seed"),
    table: str = typer.Option("users", "--table", "-t", help="Target table name")
):
    """
    Generate and seed test users directly into SQLite / SQL database with bcrypt hashes.
    """
    console.print(f"[bold cyan]Seeding {count} users into SQL table '{table}' for project '{project}'...[/bold cyan]")
    gen = PersonaGenerator()
    personas = gen.generate_batch(count=count, project_id=project)

    seeder = SQLSeeder(project_id=project, db_url=db_url, table_name=table)
    created = seeder.seed_personas(personas)

    successful = [a for a in created if a.status == "SEEDED"]
    console.print(f"[bold green][OK] Successfully seeded {len(successful)}/{count} users into {db_url}![/bold green]")


@app.command("seed-supabase")
def seed_supabase(
    project: str = typer.Option(..., "--project", "-p", help="Target project identifier"),
    url: str = typer.Option(..., "--url", help="Supabase project URL (e.g. https://xxx.supabase.co)"),
    service_key: str = typer.Option(..., "--key", "-k", help="Supabase service_role API key"),
    count: int = typer.Option(5, "--count", "-c", help="Number of users to seed")
):
    """
    Seed users directly into Supabase Auth via Admin API with auto-confirmed emails.
    """
    console.print(f"[bold cyan]Seeding {count} users into Supabase Auth for project '{project}'...[/bold cyan]")
    gen = PersonaGenerator()
    personas = gen.generate_batch(count=count, project_id=project)

    seeder = SupabaseSeeder(project_id=project, supabase_url=url, service_role_key=service_key)
    created = seeder.seed_personas(personas)

    successful = [a for a in created if a.status == "SEEDED"]
    console.print(f"[bold green][OK] Successfully seeded {len(successful)}/{count} users into Supabase![/bold green]")


@app.command("export")
def export_accounts(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID to export"),
    format: str = typer.Option("json", "--format", "-f", help="Format: 'json', 'csv', or 'bitwarden'"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Target output file path")
):
    """
    Export vault accounts to JSON, CSV or Bitwarden format.
    """
    vault = Vault()
    accounts = vault.list_accounts(project_id=project)

    if not accounts:
        console.print("[yellow]No accounts found to export.[/yellow]")
        return

    exporter = Exporter(vault)
    fmt = format.lower()
    
    if fmt == "json":
        res = exporter.export_json(accounts, output_path=output)
    elif fmt == "csv":
        res = exporter.export_csv(accounts, output_path=output)
    elif fmt == "bitwarden":
        res = exporter.export_bitwarden(accounts, output_path=output)
    else:
        console.print(f"[bold red]Unknown format: {format}. Choose json, csv or bitwarden.[/bold red]")
        raise typer.Exit(1)

    if output:
        console.print(f"[bold green][OK] Exported {len(accounts)} accounts to [white]{output}[/white][/bold green]")
    else:
        console.print(res)


@app.command("ui")
def start_web_ui(
    port: int = typer.Option(5000, "--port", "-p", help="Port to run the dashboard on")
):
    """
    Launch the interactive UserForge Web Dashboard.
    """
    from user_forge.web.server import app as web_app
    console.print(f"[bold cyan]Launching UserForge Web Dashboard at http://127.0.0.1:{port} ...[/bold cyan]")
    web_app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    app()
