const strengths = [
	"\u{2581}\u{2581}\u{2581}\u{2581}\u{2581}", // ▁▁▁▁▁
	"\u{2581}\u{2583}\u{2583}\u{2583}", // ▁▃▃▃
	"\u{2581}\u{2583}\u{2585}\u{2585}", // ▁▃▅▅
	"\u{2581}\u{2583}\u{2585}\u{2587}" // ▁▃▅▇
];
document.addEventListener('DOMContentLoaded', function () {
	const ssidSelect = document.getElementById('ssid-select');
	const hiddenSecurity = document.getElementById('hidden-security');
	const connectForm = document.getElementById('connect-form');
	const connectButton = document.getElementById('connect-button');

	function showHideFormFields() {
		const security = ssidSelect.options[ssidSelect.selectedIndex].getAttribute('data-security');
		connectForm.className = security;
		if (security === "HIDDEN") { connectForm.classList.add(hiddenSecurity.value); }
	}
	ssidSelect.addEventListener('change', showHideFormFields);
	hiddenSecurity.addEventListener('change', showHideFormFields);
	function addSsid(ssid, strength, security) {
		const lock = security === "OPEN" ? "\u{1F513}" : "\u{1F512}";
		const str = strengths[Math.min(Math.floor(strength*4), 3)];
		const name = security === "HIDDEN" ? ssid : `${lock} ${str} ${ssid}`;
		const opt = new Option(name, ssid);
		opt.setAttribute('data-security', security);
		ssidSelect.add(opt);
	}
	function refreshNetworks() {
		ssidSelect.disabled = connectButton.disabled = true;
		ssidSelect.options.length = 0;
		const opt = new Option("Loading networks... \xa0", "");
		ssidSelect.add(opt);
		opt.disabled = true;
		showHideFormFields();
		fetch("/networks").then((response) => response.json())
			.then((networks) => {
				ssidSelect.options.length = 0;
				for (const [ssid, strength, security] of networks) {
					addSsid(ssid, strength/100, security);
				}
			}).catch((error) => {
				console.error('Error:', error);
				ssidSelect.options.length = 0;
			}).finally(() => {
				addSsid("Other... \xa0", -1, "HIDDEN");
				showHideFormFields();
				ssidSelect.disabled = connectButton.disabled = false;
			});
	}
	document.getElementById('refresh-networks').addEventListener('click', refreshNetworks);
	connectForm.addEventListener('submit', function (ev) {
		ev.preventDefault();
		const selected = ssidSelect.options[ssidSelect.selectedIndex];
		let ssid = selected.value;
		let security = selected.getAttribute('data-security');
		if (ssid === "" || security === "") { return; }
		const data = {"ssid": ssid, "security": security}
		const hidden = security === "HIDDEN";
		if (hidden) {
			data["ssid"] = ssid = document.getElementById('hidden-ssid').value;
			if (ssid.length === 0) { return; }
			data["security"] = security = hiddenSecurity.value;
			data["hidden"] = true;
		}
		if (security !== "OPEN") {
			data["passphrase"] = document.getElementById('passphrase').value;
			if (data["passphrase"].length === 0) { return; }
		}
		if (security === "ENTERPRISE") {
			data["identity"] = document.getElementById('identity').value;
			if (data["identity"].length === 0) { return; }
		}
		document.getElementById("wifi-info").style.display = 'none';
		document.getElementById("submitted").style.display = 'block';
		fetch('/connect', {
			method: "POST",
			headers: {'Content-Type': 'application/json'},
			body: JSON.stringify(data),
		}).then((response) => response.json()).then((json) => {
			console.log(json);
		}).catch((error) => {
			console.error('Error:', error);
		});
	});

	refreshNetworks();

	function togglePassphraseVisibility() {
		const password = document.getElementById('passphrase');
		const type = password.getAttribute('type');
		password.setAttribute('type', type === 'password' ? 'text' : 'password');
	}
	document.getElementById('toggle-passphrase').
		addEventListener('click', togglePassphraseVisibility);
});
