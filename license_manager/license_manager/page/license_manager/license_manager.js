frappe.pages["license-manager"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("License Manager"),
		single_column: true,
	});

	// ── Build page layout inline (no compiled template needed) ─────────
	const $body = $(page.main).addClass("license-manager-page");

	$body.html(`
		<div style="max-width:860px; margin:0 auto; padding:var(--padding-lg)">

			<!-- Status card -->
			<div class="frappe-card" style="margin-bottom:var(--margin-lg); padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-md)">
					<span class="frappe-card-title">${__("License Status")}</span>
				</div>
				<div id="lm-status-section">
					<span class="text-muted">${__("Loading…")}</span>
				</div>
			</div>

			<!-- Node ID card -->
			<div class="frappe-card" style="margin-bottom:var(--margin-lg); padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-sm)">
					<span class="frappe-card-title">${__("Machine Node ID")}</span>
				</div>
				<p class="text-muted small" style="margin-bottom:var(--margin-sm)">
					${__("Share this ID with your vendor to receive a license file.")}
				</p>
				<div class="input-group">
					<input id="lm-node-id-field" type="text" class="form-control"
						readonly placeholder="${__("Loading…")}" style="font-family:monospace" />
					<div class="input-group-append">
						<button class="btn btn-default" id="lm-copy-node-btn" type="button">
							<svg class="icon icon-sm" style="margin-right:4px"><use href="#icon-copy"></use></svg>
							${__("Copy")}
						</button>
					</div>
				</div>
			</div>

			<!-- Activate license card -->
			<div class="frappe-card" style="padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-sm)">
					<span class="frappe-card-title">${__("Activate License")}</span>
				</div>
				<p class="text-muted small" style="margin-bottom:var(--margin-sm)">
					${__("Paste the full contents of your .lic JSON file below, then click Activate.")}
				</p>
				<div class="form-group">
					<textarea id="lm-license-textarea" class="form-control" rows="10"
						placeholder='{ "license_id": "...", "signature": "..." }'
						style="font-family:monospace; font-size:0.85em; resize:vertical"></textarea>
				</div>
				<button class="btn btn-primary" id="lm-activate-btn" type="button">
					${__("Activate License")}
				</button>
				<div id="lm-import-result" style="margin-top:var(--margin-md)"></div>
			</div>

			<!-- ── Danger Zone ──────────────────────────────────────────── -->
			<div class="frappe-card"
				style="padding:var(--padding-lg);border:1px solid var(--red-300)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-sm)">
					<span class="frappe-card-title" style="color:var(--red-600)">
						${__("Danger Zone")}
					</span>
				</div>
				<p class="text-muted small">${__("Deactivating will immediately lock out all non-Administrator users.")}</p>
				<button class="btn btn-danger" id="lm-deactivate-btn" type="button">
					${__("Deactivate License")}
				</button>
			</div>

		</div>
	`);

	// ── Load status immediately ─────────────────────────────────────────
	frappe.pages["license-manager"].load_status(wrapper);

	// ── Copy node ID ────────────────────────────────────────────────────
	$body.find("#lm-copy-node-btn").on("click", function () {
		const val = $body.find("#lm-node-id-field").val();
		if (val && val !== __("Loading…") && val !== __("UNAVAILABLE")) {
			navigator.clipboard.writeText(val).then(() => {
				frappe.show_alert({ message: __("Copied to clipboard."), indicator: "green" });
			});
		}
	});

	// ── Activate license ────────────────────────────────────────────────
	$body.find("#lm-activate-btn").on("click", function () {
		const license_json = $body.find("#lm-license-textarea").val().trim();
		if (!license_json) {
			frappe.msgprint(__("Please paste the license file contents first."));
			return;
		}
		const $btn = $(this).prop("disabled", true).text(__("Activating…"));
		frappe.call({
			method: "license_manager.license_manager.page.license_manager.license_manager.import_license",
			args: { license_json },
			callback: function (r) {
				$btn.prop("disabled", false).text(__("Activate License"));
				const result = r.message || {};
				const $result = $body.find("#lm-import-result");
				if (result.success) {
					$result.html(
						`<div class="alert alert-success">
							<svg class="icon icon-sm" style="margin-right:6px"><use href="#icon-tick"></use></svg>
							${frappe.utils.escape_html(result.message)}
						</div>`
					);
					frappe.pages["license-manager"].load_status(wrapper);
				} else {
					$result.html(
						`<div class="alert alert-danger">
							<svg class="icon icon-sm" style="margin-right:6px"><use href="#icon-warning"></use></svg>
							${frappe.utils.escape_html(result.message)}
						</div>`
					);
				}
			},
			error: function () {
				$btn.prop("disabled", false).text(__("Activate License"));
			},
		});
	});

	// ── Deactivate license ──────────────────────────────────────────────
	$body.find("#lm-deactivate-btn").on("click", function () {
		frappe.confirm(
			__("Are you sure? This will immediately lock out all non-Administrator users."),
			function () {
				frappe.call({
					method: "license_manager.license_manager.page.license_manager.license_manager.deactivate_license",
					callback: function (r) {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: result.message, indicator: "green" });
							frappe.pages["license-manager"].load_status(wrapper);
						} else {
							frappe.msgprint(result.message);
						}
					},
				});
			}
		);
	});

frappe.pages["license-manager"].load_status = function (wrapper) {
	const $body = $(wrapper).find(".layout-main-section");
	frappe.call({
		method: "license_manager.license_manager.page.license_manager.license_manager.get_license_status",
		callback: function (r) {
			const d = r.message || {};

			// Node ID field
			$body.find("#lm-node-id-field").val(d.machine_node_id || __("UNAVAILABLE"));

			// Status badge
			const status = d.status || "Not Activated";
			const color_map = { Valid: "green", Expired: "red", Invalid: "red", "Not Activated": "orange" };
			const color = color_map[status] || "grey";

			let html = `<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px">
				<span class="indicator-pill ${color}" style="font-size:1em; padding:4px 12px">
					${frappe.utils.escape_html(status)}
				</span>
			</div>`;

			if (d.license_id) {
				const rows = [
					[__("License ID"),  d.license_id],
					[__("Customer"),    d.customer],
					[__("Expiry"),      d.expiry],
					[__("Features"),    Array.isArray(d.features) ? d.features.join(", ") : d.features],
					[__("Node ID"),     d.node_id],
				];
				html += `<table class="table table-bordered table-sm" style="margin:0">`;
				rows.forEach(([label, value]) => {
					if (value) {
						html += `<tr>
							<th class="text-muted" style="width:160px;font-weight:500">${frappe.utils.escape_html(label)}</th>
							<td style="font-family:${label === __("License ID") || label === __("Node ID") ? "monospace" : "inherit"}">${frappe.utils.escape_html(String(value))}</td>
						</tr>`;
					}
				});
				html += "</table>";
			}

			$body.find("#lm-status-section").html(html);
		},
	});
};
