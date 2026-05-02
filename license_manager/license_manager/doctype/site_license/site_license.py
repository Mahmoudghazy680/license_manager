import frappe
from frappe.model.document import Document


class SiteLicense(Document):
    def validate(self):
        """Validate and activate the pasted license on every save.

        Calls the full validation pipeline (parse → signature → expiry → node).
        On success, populates the read-only summary fields.
        On failure, frappe.ValidationError is raised and the save is aborted.
        """
        raw = (self.license_file_content or "").strip()
        if not raw:
            self.license_id = None
            self.customer = None
            self.issue_date = None
            self.expiry = None
            self.features = None
            self.node_id = None
            self.status = "Not Activated"
            self.computed_node_id = self.get_machine_node_id()
            return

        from license_manager.utils.crypto import activate_license

        license_data = activate_license(raw)

        self.license_id = license_data.get("license_id")
        self.customer = license_data.get("customer")
        self.issue_date = (license_data.get("issue_date") or "")[:10] or None
        self.expiry = (license_data.get("expiry") or "")[:10] or None
        self.features = ", ".join(license_data.get("features") or [])
        self.node_id = license_data.get("node_id")
        self.status = "Valid"
        self.computed_node_id = self.get_machine_node_id()

    def get_machine_node_id(self) -> str:
        """Compute and cache this machine's node ID into ``computed_node_id``.

        Returns:
            The computed node ID string.
        """
        from license_manager.utils.node_id import get_display_node_id

        node_id = get_display_node_id()
        self.computed_node_id = node_id
        return node_id
