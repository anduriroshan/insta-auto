import click
import json
import os
import sys

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlmodel import Session, select
from config import settings
from core.database import engine, init_db
from core.models import AutomationRule, ActionLog, QueuedDM

@click.group()
def cli():
    """Instagram Creator Automation CLI — Official Meta Graph API"""
    init_db()

@cli.command()
def status():
    """Check current system status, credentials, and metrics."""
    click.secho("\n[+] Instagram Creator Automator - Status", fg="cyan", bold=True)
    click.echo("-" * 45)
    click.echo(f"Host/Port:        http://{settings.HOST}:{settings.PORT}")
    click.echo(f"Verify Token:     {settings.META_VERIFY_TOKEN}")
    click.echo(f"Webhook URL:      {settings.WEBHOOK_BASE_URL.rstrip('/')}/webhook" if settings.WEBHOOK_BASE_URL else "Not Configured (Run ngrok http 8000)")
    
    token_status = "Configured" if settings.PAGE_ACCESS_TOKEN else "MISSING (Set in .env)"
    click.secho(f"Access Token:     {token_status}", fg="green" if settings.PAGE_ACCESS_TOKEN else "yellow")
    
    with Session(engine) as session:
        active_rules = len(session.exec(select(AutomationRule).where(AutomationRule.is_active == True)).all())
        total_rules = len(session.exec(select(AutomationRule)).all())
        queued = len(session.exec(select(QueuedDM).where(QueuedDM.delivered == False)).all())
        logs_count = len(session.exec(select(ActionLog)).all())

        click.echo("-" * 45)
        click.echo(f"Active Rules:     {active_rules} / {total_rules}")
        click.echo(f"Queued (Follow):  {queued} pending")
        click.echo(f"Total Logs:       {logs_count}")
    click.echo("")

@cli.group()
def rules():
    """Manage keyword automation rules."""
    pass

@rules.command("list")
def list_rules():
    """List all configured automation rules."""
    with Session(engine) as session:
        items = session.exec(select(AutomationRule).order_by(AutomationRule.id.asc())).all()
        if not items:
            click.secho("No automation rules found. Add one with 'python cli.py rules add'", fg="yellow")
            return

        click.secho(f"\nFound {len(items)} Automation Rules:\n", fg="cyan", bold=True)
        for r in items:
            status_color = "green" if r.is_active else "red"
            status_text = "ACTIVE" if r.is_active else "DISABLED"
            click.secho(f"[{r.id}] {r.name}  [{status_text}]", fg=status_color, bold=True)
            click.echo(f"    Type:        {r.rule_type.upper()} ({r.match_type})")
            click.echo(f"    Keywords:    {', '.join(r.get_keywords_list())}")
            click.echo(f"    Response:    {r.response_text[:70]}...")
            click.echo(f"    Follow Gate: {'ENABLED' if r.follow_gate_enabled else 'Disabled'}")
            click.echo(f"    Cooldown:    {r.cooldown_minutes} min | Triggers: {r.trigger_count}")
            click.echo("")

@rules.command("add")
def add_rule():
    """Interactively create a new keyword automation rule."""
    click.secho("\n[*] Create New Automation Rule", fg="cyan", bold=True)
    name = click.prompt("Rule Name", default="Lead Magnet Delivery")
    keywords_raw = click.prompt("Keywords (comma separated)", default="guide, ebook, free")
    rule_type = click.prompt("Rule Type", type=click.Choice(["all", "dm", "comment", "story"]), default="all")
    match_type = click.prompt("Match Type", type=click.Choice(["contains", "exact", "regex"]), default="contains")
    response_text = click.prompt("Response Message Text")
    follow_gate = click.confirm("Enable Follow Gate? (Require user to follow your account first)", default=True)
    
    follow_gate_msg = None
    if follow_gate:
        follow_gate_msg = click.prompt(
            "Follow Gate Message",
            default="Hey! 👋 Please follow our page first, then reply with the keyword again to get your link! 🚀"
        )
    cooldown = click.prompt("Cooldown per user (minutes)", type=int, default=1440)

    keywords_list = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]

    rule = AutomationRule(
        name=name,
        match_type=match_type,
        rule_type=rule_type,
        response_text=response_text,
        follow_gate_enabled=follow_gate,
        follow_gate_message=follow_gate_msg or "",
        cooldown_minutes=cooldown,
        is_active=True
    )
    rule.set_keywords_list(keywords_list)

    with Session(engine) as session:
        session.add(rule)
        session.commit()
        session.refresh(rule)
        click.secho(f"\n[OK] Rule created successfully with ID: {rule.id}!\n", fg="green", bold=True)

@rules.command("delete")
@click.argument("rule_id", type=int)
def delete_rule(rule_id: int):
    """Delete a rule by ID."""
    with Session(engine) as session:
        rule = session.get(AutomationRule, rule_id)
        if not rule:
            click.secho(f"Rule ID {rule_id} not found.", fg="red")
            return
        session.delete(rule)
        session.commit()
        click.secho(f"Rule {rule_id} ('{rule.name}') deleted successfully.", fg="green")

@cli.command()
@click.option("--limit", default=15, help="Number of recent logs to show")
def logs(limit: int):
    """View recent activity logs."""
    with Session(engine) as session:
        recent = session.exec(select(ActionLog).order_by(ActionLog.id.desc()).limit(limit)).all()
        if not recent:
            click.secho("No activity logs recorded yet.", fg="yellow")
            return

        click.secho(f"\nRecent Activity Logs (Last {len(recent)}):\n", fg="cyan", bold=True)
        for l in recent:
            status_color = "green" if l.status == "success" else ("yellow" if l.status == "blocked" else "red")
            time_str = l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "N/A"
            user_str = f"@{l.sender_username}" if l.sender_username else l.sender_id
            click.echo(f"[{time_str}] [{l.event_type.upper()}] user={user_str} ", nl=False)
            click.secho(f"[{l.status.upper()}]", fg=status_color, bold=True)
            click.echo(f"   Details: {l.details}")
            click.echo("")

@cli.command()
def setup():
    """Interactive wizard to configure your .env file."""
    click.secho("\n[*] Instagram Automation — Setup Wizard", fg="cyan", bold=True)
    click.echo("This wizard will help you configure your credentials in .env\n")
    
    app_id = click.prompt("Meta App ID", default=settings.META_APP_ID)
    app_secret = click.prompt("Meta App Secret", default=settings.META_APP_SECRET)
    verify_token = click.prompt("Webhook Verify Token", default=settings.META_VERIFY_TOKEN)
    access_token = click.prompt("Page Access Token", default=settings.PAGE_ACCESS_TOKEN)
    ig_id = click.prompt("Instagram Business Account ID", default=settings.INSTAGRAM_ACCOUNT_ID)
    tunnel_url = click.prompt("Public Webhook Base URL (e.g., https://xyz.ngrok-free.app)", default=settings.WEBHOOK_BASE_URL)
    password = click.prompt("Dashboard Password", default=settings.DASHBOARD_PASSWORD)

    env_content = f"""# Meta App Configuration
META_APP_ID={app_id}
META_APP_SECRET={app_secret}
META_VERIFY_TOKEN={verify_token}
PAGE_ACCESS_TOKEN={access_token}
INSTAGRAM_ACCOUNT_ID={ig_id}

# Webhook Tunnel / Public URL
WEBHOOK_BASE_URL={tunnel_url}

# Dashboard Security
DASHBOARD_PASSWORD={password}
JWT_SECRET={settings.JWT_SECRET}

# Server Settings
HOST={settings.HOST}
PORT={settings.PORT}
DEBUG={str(settings.DEBUG).lower()}
"""
    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)

    click.secho("\n[OK] Settings saved to .env! You can now start the server with: python main.py\n", fg="green", bold=True)

if __name__ == "__main__":
    cli()
