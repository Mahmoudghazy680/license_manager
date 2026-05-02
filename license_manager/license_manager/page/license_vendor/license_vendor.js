const LV_METHOD = (m) =>
	`license_manager.license_manager.page.license_vendor.license_vendor.${m}`;

frappe.pages["license-vendor"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("License Vendor Control"),
		single_column: true,
	});

	const $body = $(page.main);

	// Auto-generate a license ID: LIC-YYYY-XXXXXX
	const now = new Date();
	const auto_lic_id = `LIC-${now.getFullYear()}-${String(now.getTime()).slice(-6)}`;

	$body.html(`
		<div style="max-width:900px;margin:0 auto;padding:var(--padding-lg)">

			<!-- ── Status ──────────────────────────────────────────────── -->
			<div class="frappe-card" style="margin-bottom:var(--margin-lg);padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-md)">
					<span class="frappe-card-title">${__("Current License Status")}</span>
					<button class="btn btn-xs btn-default" id="lv-refresh-btn" style="float:right">
						${__("Refresh")}
					</button>
				</div>
				<div id="lv-status-section"><span class="text-muted">${__("Loading…")}</span></div>
			</div>

			<!-- ── Machine Node ID ─────────────────────────────────────── -->
			<div class="frappe-card" style="margin-bottom:var(--margin-lg);padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-sm)">
					<span class="frappe-card-title">${__("This Machine's Node ID")}</span>
				</div>
				<p class="text-muted small" style="margin-bottom:var(--margin-sm)">
					${__("Use this as the Target Node ID when generating a license for this machine.")}
				</p>
				<div class="input-group">
					<input id="lv-machine-node-field" type="text" class="form-control"
						readonly style="font-family:monospace" placeholder="${__("Loading…")}" />
					<div class="input-group-append">
						<button class="btn btn-default" id="lv-copy-machine-node-btn" type="button">
							${__("Copy")}
						</button>
					</div>
				</div>
			</div>

			<!-- ── Generate & Sign ─────────────────────────────────────── -->
			<div class="frappe-card" style="margin-bottom:var(--margin-lg);padding:var(--padding-lg)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-md)">
					<span class="frappe-card-title">${__("Generate & Sign License")}</span>
				</div>

				<div class="row">
					<div class="col-sm-6">
						<div class="form-group">
							<label class="control-label">${__("Customer Name")} <span class="text-danger">*</span></label>
							<input id="lv-customer" type="text" class="form-control"
								placeholder="Acme Corp" />
						</div>
					</div>
					<div class="col-sm-6">
						<div class="form-group">
							<label class="control-label">${__("License ID")} <span class="text-danger">*</span></label>
							<input id="lv-license-id" type="text" class="form-control"
								value="${frappe.utils.escape_html(auto_lic_id)}"
								placeholder="LIC-2026-000001" />
						</div>
					</div>
				</div>

				<div class="row">
					<div class="col-sm-6">
						<div class="form-group">
							<label class="control-label">${__("Target Node ID")} <span class="text-danger">*</span></label>
							<div class="input-group">
								<input id="lv-node-id" type="text" class="form-control"
									style="font-family:monospace"
									placeholder="SITE-XXXXXXXXXXXXXXXXXXXXXXXX" />
								<div class="input-group-append">
									<button class="btn btn-default" id="lv-fill-machine-node-btn" type="button"
										title="${__("Fill with this machine\'s Node ID")}">
										${__("Use This Machine")}
									</button>
								</div>
							</div>
						</div>
					</div>
					<div class="col-sm-6">
						<div class="form-group">
							<label class="control-label">${__("Expiry Date")} <span class="text-danger">*</span></label>
							<input id="lv-expiry" type="date" class="form-control" />
						</div>
					</div>
				</div>

				<div class="form-group">
					<label class="control-label">
						${__("Private Key (Ed25519 PEM)")} <span class="text-danger">*</span>
						<span class="text-muted small"> — ${__("never stored, only used for this request")}</span>
					</label>
					<textarea id="lv-private-key" class="form-control" rows="6"
						placeholder="-----BEGIN PRIVATE KEY-----&#10;…&#10;-----END PRIVATE KEY-----"
						style="font-family:monospace;font-size:0.82em;resize:vertical;
						       background:#fff9f9;border-color:#f5a0a0"></textarea>
				</div>

				<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
					<button class="btn btn-primary" id="lv-sign-activate-btn" type="button">
						${__("Sign & Activate on This Site")}
					</button>
					<button class="btn btn-default" id="lv-sign-only-btn" type="button">
						${__("Sign & Get JSON (for another machine)")}
					</button>
				</div>

				<div id="lv-sign-result" style="margin-top:var(--margin-md)"></div>

				<!-- Output JSON for delivery -->
				<div id="lv-output-section" style="display:none;margin-top:var(--margin-md)">
					<label class="control-label">${__("Signed License JSON — copy and deliver to client")}</label>
					<div class="input-group">
						<textarea id="lv-output-json" class="form-control" rows="12"
							readonly style="font-family:monospace;font-size:0.82em"></textarea>
					</div>
					<button class="btn btn-xs btn-default" id="lv-copy-json-btn"
						style="margin-top:6px">
						${__("Copy JSON")}
					</button>
				</div>
			</div>

			<!-- ── Danger Zone ─────────────────────────────────────────── -->
			<div class="frappe-card"
				style="padding:var(--padding-lg);border:1px solid var(--red-300)">
				<div class="frappe-card-head" style="margin-bottom:var(--margin-sm)">
					<span class="frappe-card-title" style="color:var(--red-600)">
						${__("Danger Zone")}
					</span>
				</div>
				<p class="text-muted small">${__("Deactivating the license will immediately block all non-Administrator users.")}</p>
				<button class="btn btn-danger" id="lv-deactivate-btn" type="button">
					${__("Deactivate Current License")}
				</button>
			</div>

		</div>
	`);

	// ── Load status on mount ────────────────────────────────────────────────
	frappe.pages["license-vendor"].load_status(wrapper);

	// ── Refresh button ──────────────────────────────────────────────────────
	$body.on("click", "#lv-refresh-btn", () => frappe.pages["license-vendor"].load_status(wrapper));

	// ── Copy machine node ID ────────────────────────────────────────────────
	$body.on("click", "#lv-copy-machine-node-btn", function () {
		const val = $body.find("#lv-machine-node-field").val();
		if (val && val !== __("Loading…")) {
			navigator.clipboard.writeText(val).then(() =>
				frappe.show_alert({ message: __("Node ID copied."), indicator: "green" })
			);
		}
	});

	// ── Fill node ID field with this machine's ID ───────────────────────────
	$body.on("click", "#lv-fill-machine-node-btn", function () {
		const val = $body.find("#lv-machine-node-field").val();
		if (val && val !== __("Loading…")) {
			$body.find("#lv-node-id").val(val);
		}
	});

	// ── Sign & Activate ─────────────────────────────────────────────────────
	$body.on("click", "#lv-sign-activate-btn", function () {
		const args = _collect_form($body);
		if (!args) return;
		const $btn = $(this).prop("disabled", true).text(__("Signing & Activating…"));
		frappe.call({
			method: LV_METHOD("generate_and_activate"),
			args,
			callback(r) {
				$btn.prop("disabled", false).text(__("Sign & Activate on This Site"));
				const res = r.message || {};
				_show_result($body, res.success, res.message);
				if (res.success) {
					frappe.pages["license-vendor"].load_status(wrapper);
					$body.find("#lv-output-section").hide();
				}
			},
			error() { $btn.prop("disabled", false).text(__("Sign & Activate on This Site")); },
		});
	});

	// ── Sign Only ───────────────────────────────────────────────────────────
	$body.on("click", "#lv-sign-only-btn", function () {
		const args = _collect_form($body);
		if (!args) return;
		const $btn = $(this).prop("disabled", true).text(__("Signing…"));
		frappe.call({
			method: LV_METHOD("generate_license_json"),
			args,
			callback(r) {
				$btn.prop("disabled", false).text(__("Sign & Get JSON (for another machine)"));
				const res = r.message || {};
				_show_result($body, res.success, res.message);
				if (res.success && res.license_json) {
					$body.find("#lv-output-json").val(res.license_json);
					$body.find("#lv-output-section").show();
				}
			},
			error() { $btn.prop("disabled", false).text(__("Sign & Get JSON (for another machine)")); },
		});
	});

	// ── Copy JSON ───────────────────────────────────────────────────────────
	$body.on("click", "#lv-copy-json-btn", function () {
		const val = $body.find("#lv-output-json").val();
		if (val) {
			navigator.clipboard.writeText(val).then(() =>
				frappe.show_alert({ message: __("License JSON copied."), indicator: "green" })
			);
		}
	});

	// ── Deactivate ──────────────────────────────────────────────────────────
	$body.on("click", "#lv-deactivate-btn", function () {
		frappe.confirm(
			__("Are you sure? This will immediately lock out all non-Administrator users."),
			function () {
				frappe.call({
					method: LV_METHOD("deactivate_license"),
					callback(r) {
						const res = r.message || {};
						_show_result($body, res.success, res.message);
						if (res.success) frappe.pages["license-vendor"].load_status(wrapper);
					},
				});
			}
		);
	});
};

frappe.pages["license-vendor"].refresh = function (wrapper) {
	frappe.pages["license-vendor"].load_status(wrapper);
};

frappe.pages["license-vendor"].load_status = function (wrapper) {
	const $body = $(wrapper).find(".layout-main-section");
	frappe.call({
		method: LV_METHOD("get_vendor_status"),
		callback(r) {
			const d = r.message || {};

			// Machine node ID field
			$body.find("#lv-machine-node-field").val(d.machine_node_id || __("UNAVAILABLE"));

			// Pre-fill node ID in form if empty
			if (!$body.find("#lv-node-id").val() && d.machine_node_id) {
				$body.find("#lv-node-id").val(d.machine_node_id);
			}

			// Status section
			const status = d.status || "Not Activated";
			const color_map = { Valid: "green", Expired: "red", Invalid: "red", "Not Activated": "orange" };
			const color = color_map[status] || "grey";

			let html = `<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
				<span class="indicator-pill ${color}" style="font-size:1em;padding:4px 14px">
					${frappe.utils.escape_html(status)}
				</span>
			</div>`;

			if (d.license_id) {
				const rows = [
					[__("License ID"), d.license_id, true],
					[__("Customer"),   d.customer,   false],
					[__("Expiry"),     d.expiry,     false],
					[__("Node ID"),    d.node_id,    true],
				];
				html += `<table class="table table-bordered table-sm" style="margin:0">`;
				rows.forEach(([label, value, mono]) => {
					if (value) {
						html += `<tr>
							<th class="text-muted" style="width:140px;font-weight:500">${frappe.utils.escape_html(label)}</th>
							<td style="font-family:${mono ? "monospace" : "inherit"}">${frappe.utils.escape_html(String(value))}</td>
						</tr>`;
					}
				});
				html += `</table>`;
			}

			$body.find("#lv-status-section").html(html);
		},
	});
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function _collect_form($body) {
	const customer       = $body.find("#lv-customer").val().trim();
	const license_id     = $body.find("#lv-license-id").val().trim();
	const node_id        = $body.find("#lv-node-id").val().trim();
	const expiry         = $body.find("#lv-expiry").val().trim();
	const private_key_pem = $body.find("#lv-private-key").val().trim();

	const missing = [];
	if (!customer)       missing.push(__("Customer Name"));
	if (!license_id)     missing.push(__("License ID"));
	if (!node_id)        missing.push(__("Target Node ID"));
	if (!expiry)         missing.push(__("Expiry Date"));
	if (!private_key_pem) missing.push(__("Private Key"));

	if (missing.length) {
		frappe.msgprint(__("Please fill in: ") + missing.join(", "));
		return null;
	}

	return { customer, license_id, node_id, expiry, private_key_pem };
}

function _show_result($body, success, message) {
	const cls  = success ? "alert-success" : "alert-danger";
	const icon = success ? "✓" : "✗";
	$body.find("#lv-sign-result").html(
		`<div class="alert ${cls}" style="margin-bottom:0">
			<strong>${icon}</strong> ${frappe.utils.escape_html(message || "")}
		</div>`
	);
}
