frappe.ready(() => {
	const root = document.querySelector(".kiosk");
	const branch = root.dataset.branch;
	const resetSeconds = parseInt(root.dataset.reset, 10) || 4;
	const $ = (id) => document.getElementById(id);

	let step = "mobile"; // mobile | pin
	let mobile = "";
	let pin = "";
	let busy = false;
	let resetTimer = null;
	let idleTimer = null;
	let scanner = null;

	// ------------------------------------------------------------ keypad
	function render() {
		const display = $("k-display");
		const value = step === "mobile" ? mobile : "●".repeat(pin.length);
		display.textContent = value || (step === "mobile" ? "Mobile number" : "4-digit PIN");
		display.classList.toggle("placeholder", !value);
		$("k-sub").textContent =
			step === "mobile" ? "Enter your registered mobile number" : `Enter PIN for ${mask(mobile)}`;
		$("k-go").textContent = step === "mobile" ? "Next" : "Go";
		$("k-go").disabled = step === "mobile" ? mobile.length !== 10 : pin.length !== 4;
		$("k-cancel").classList.toggle("k-hidden", !mobile);
	}

	function mask(m) {
		return m.slice(0, 2) + "••••" + m.slice(-4);
	}

	function press(k) {
		if (busy) return;
		bumpIdle();
		if (k === "back") {
			if (step === "pin" && !pin) step = "mobile";
			else if (step === "pin") pin = pin.slice(0, -1);
			else mobile = mobile.slice(0, -1);
		} else if (k === "go") {
			if (step === "mobile" && mobile.length === 10) step = "pin";
			else if (step === "pin" && pin.length === 4) return submit({ mobile, pin });
		} else if (step === "mobile" && mobile.length < 10) {
			mobile += k;
		} else if (step === "pin" && pin.length < 4) {
			pin += k;
			if (pin.length === 4) {
				render();
				return submit({ mobile, pin });
			}
		}
		render();
	}

	function resetPad() {
		step = "mobile";
		mobile = "";
		pin = "";
		render();
	}

	// Clear half-typed input if the student walks away.
	function bumpIdle() {
		clearTimeout(idleTimer);
		idleTimer = setTimeout(resetPad, 30000);
	}

	$("k-pad").addEventListener("click", (e) => {
		const key = e.target.closest("[data-k]");
		if (key) press(key.dataset.k);
	});
	$("k-cancel").addEventListener("click", resetPad);
	document.addEventListener("keydown", (e) => {
		if (/^[0-9]$/.test(e.key)) press(e.key);
		else if (e.key === "Backspace") press("back");
		else if (e.key === "Enter") press("go");
	});

	// ------------------------------------------------------------ QR scanning
	$("k-scan-btn").addEventListener("click", startScan);
	$("k-scan-cancel").addEventListener("click", stopScan);

	function startScan() {
		if (typeof Html5Qrcode === "undefined") {
			return showResult({ status: "error", message: "QR scanner could not load. Please use mobile & PIN." });
		}
		$("k-step-pad").classList.add("k-hidden");
		$("k-step-scan").classList.remove("k-hidden");
		scanner = scanner || new Html5Qrcode("k-reader");
		scanner
			.start({ facingMode: "user" }, { fps: 10, qrbox: 240 }, (text) => {
				if (busy) return;
				stopScan();
				submit({ qr: text });
			})
			.catch(() => {
				stopScan();
				showResult({ status: "error", message: "Camera not available. Please use mobile & PIN." });
			});
	}

	function stopScan() {
		if (scanner && scanner.isScanning) scanner.stop().catch(() => {});
		$("k-step-scan").classList.add("k-hidden");
		$("k-step-pad").classList.remove("k-hidden");
	}

	// ------------------------------------------------------------ server
	function submit(args) {
		busy = true;
		frappe
			.call({
				method: "pathshala.api.kiosk_punch",
				type: "POST",
				args: Object.assign({ branch }, args),
				freeze: false,
			})
			.then((r) => showResult(r.message || { status: "error", message: "Something went wrong." }))
			.catch(() => showResult({ status: "error", message: "Network error. Please try again." }))
			.finally(() => {
				busy = false;
				resetPad();
			});
	}

	function showResult(res) {
		clearTimeout(resetTimer);
		const name = res.student_name || "";
		const avatar = $("k-avatar");
		avatar.innerHTML = "";
		if (res.photo) {
			const img = document.createElement("img");
			img.src = res.photo;
			img.style.cssText = "width:100%;height:100%;border-radius:50%;object-fit:cover";
			img.onerror = () => (avatar.textContent = initials(name));
			avatar.appendChild(img);
		} else {
			avatar.textContent = name ? initials(name) : res.status === "error" ? "!" : "✓";
		}

		const badges = { IN: "✔ CHECKED IN", OUT: "➜ CHECKED OUT" };
		$("k-badge").textContent = res.status === "error" ? "✖ NOT ALLOWED" : badges[res.action] || "";
		$("k-badge").classList.toggle("k-hidden", !$("k-badge").textContent);
		$("k-name").textContent = name;
		$("k-seat").textContent = [res.seat && `Seat ${res.seat}`, res.zone].filter(Boolean).join(" · ");
		$("k-msg").textContent = res.message || "";
		$("k-time").textContent = res.time || "";

		const box = $("k-result");
		box.className = `k-result ${res.status || "error"}`;
		const seconds = res.status === "error" ? resetSeconds + 3 : resetSeconds;
		animateBar(seconds);
		resetTimer = setTimeout(hideResult, seconds * 1000);
		if (res.status !== "error") loadStatus();
	}

	function hideResult() {
		$("k-result").classList.add("k-hidden");
	}
	$("k-result").addEventListener("click", hideResult);

	function animateBar(seconds) {
		const bar = $("k-bar");
		bar.style.transition = "none";
		bar.style.width = "100%";
		requestAnimationFrame(() =>
			requestAnimationFrame(() => {
				bar.style.transition = `width ${seconds}s linear`;
				bar.style.width = "0%";
			})
		);
	}

	function initials(name) {
		return name
			.split(" ")
			.filter(Boolean)
			.slice(0, 2)
			.map((w) => w[0].toUpperCase())
			.join("");
	}

	// ------------------------------------------------------------ header
	function tick() {
		$("k-clock").textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
	}

	function loadStatus() {
		frappe.call({ method: "pathshala.api.kiosk_status", args: { branch } }).then((r) => {
			const zones = (r.message && r.message.zones) || [];
			$("k-zones").innerHTML = zones
				.map(
					(z) =>
						`<span class="k-zone">${frappe.utils.escape_html(z.zone_name)}: <b>${z.present}</b> / ${z.seats}</span>`
				)
				.join("");
		});
	}

	tick();
	setInterval(tick, 10000);
	loadStatus();
	setInterval(loadStatus, 60000);
	render();
});
