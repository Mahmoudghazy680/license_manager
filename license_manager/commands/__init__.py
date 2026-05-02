import click

from frappe.commands import get_site, pass_context


@click.command("license-status")
@pass_context
def license_status(context):
    """Show the current license status for the active site."""
    import frappe

    site = get_site(context)
    frappe.init(site=site)
    frappe.connect()
    try:
        from license_manager.license_manager.page.license_manager.license_manager import get_license_status

        data = get_license_status()
        status = data.get("status", "Unknown")

        if status in ("Expired", "Invalid"):
            status_str = click.style(status, fg="red", bold=True)
        elif status == "Valid":
            status_str = click.style(status, fg="green", bold=True)
        else:
            status_str = click.style(status, fg="yellow", bold=True)

        click.echo(f"Status       : {status_str}")
        if data.get("license_id"):
            click.echo(f"License ID   : {data['license_id']}")
        if data.get("customer"):
            click.echo(f"Customer     : {data['customer']}")
        if data.get("expiry"):
            click.echo(f"Expiry       : {data['expiry']}")
        if data.get("features"):
            features_str = (
                ", ".join(data["features"]) if isinstance(data["features"], list) else data["features"]
            )
            click.echo(f"Features     : {features_str}")
        if data.get("node_id"):
            click.echo(f"License Node : {data['node_id']}")
        click.echo(f"Machine Node : {data.get('machine_node_id', 'UNAVAILABLE')}")
    finally:
        frappe.destroy()


@click.command("license-import")
@click.argument("path")
@pass_context
def license_import(context, path):
    """Import a license file at PATH into the active site."""
    import os

    import frappe

    site = get_site(context)

    if not os.path.exists(path):
        click.echo(f"ERROR: File not found: {path!r}", err=True)
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    frappe.init(site=site)
    frappe.connect()
    try:
        frappe.set_user("Administrator")
        from license_manager.license_manager.page.license_manager.license_manager import import_license

        result = import_license(content)
        if result.get("success"):
            click.echo(click.style(result.get("message", "License activated."), fg="green"))
        else:
            click.echo(click.style(result.get("message", "Failed."), fg="red"), err=True)
    finally:
        frappe.destroy()


@click.command("license-node-id")
@pass_context
def license_node_id(context):
    """Print the node ID for this machine. Share this with the vendor."""
    import frappe

    site = get_site(context)
    frappe.init(site=site)
    frappe.connect()
    try:
        from license_manager.utils.node_id import compute

        click.echo(compute())
    finally:
        frappe.destroy()


commands = [license_status, license_import, license_node_id]
