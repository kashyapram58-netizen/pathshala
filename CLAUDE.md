# Pathshala

Frappe v15 app for **Pathshala – Library and Self Study Centre**. The business rents **study seats** to students (by shift, full day or hour) and **paid lockers** for keeping books. It is a self-study space, *not* a book-lending library. Site: `pathshala.com` (ERPNext is installed alongside but not used).

## Dev environment

- Bench runs inside Docker container **`rapl_devcontainer-frappe-1`**. `bench` is not on the host PATH.
  - Host path `/Users/ram/Desktop/dev/rapl/development/frappe-bench` = container path `/workspace/development/frappe-bench`
  - Run commands with: `docker exec -u frappe -w /workspace/development/frappe-bench rapl_devcontainer-frappe-1 bash -lc '<cmd>'`
  - To pipe a script via stdin, use `docker exec -i ...` (without `-i`, stdin is silently empty).
- **`pathshala.com` is NOT the default site** (the default is `emergency.localhost`). Always pass `--site pathshala.com`. A server started without it serves the wrong site.
- `developer_mode` is on for `pathshala.com`, so DocType edits in the UI are written to JSON files in the app.
- After changing DocType JSON: `bench --site pathshala.com migrate`. After changing hooks, www pages or Python: `bench --site pathshala.com clear-cache` (restart the server if running).
- Ad-hoc scripts: from `sites/`, run `../env/bin/python script.py` with `frappe.init(site="pathshala.com", sites_path="."); frappe.connect()`. Wrap test data in `try/finally: frappe.db.rollback()`, **but don't trust the rollback**: one seed run (with print/PDF rendering) was committed anyway. Use clearly fake names and check table counts afterwards; clean up by `creation` time window.
- PDF rendering from a script needs `frappe.local.conf.host_name` pointed at a running server. Otherwise wkhtmltopdf fails with `HostNotFoundError`, because `pathshala.com` is a real public domain.
- Headless screenshots: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --user-data-dir=<tmp> --screenshot=...`. Its minimum layout width is about 500px, so to test phone widths, put the page in a 390px `<iframe>`. The host shell is zsh, so don't rely on `set -- $var` word-splitting.
- No committed test suite yet; behaviour was verified with rollback scripts. Ruff isn't installed in the container.

## Layout

```
pathshala/
  hooks.py          scheduler, after_migrate, jinja, app_include_css, branding (app_logo_url, favicon, apps screen)
  setup.py          after_migrate: roles, syncs Custom HTML Blocks from workspace_blocks/, sets
                    System Settings.default_app = pathshala (only if empty) so login lands on /app/pathshala
  bulk.py           create_seats / create_lockers (prefix + start + count, skips existing, max 500) + next_*_number
  public/js/pathshala.js   desk helpers (app_include_js): pathshala.bulk_seats() / pathshala.bulk_lockers() dialogs,
                    used by the Study Zone and Pathshala Branch forms and the Seat and Locker list views
  id_card.py        get_id_card_data() for the "Pathshala ID Card" print format (embeds logo/photo/QR as data URIs)
  workspace_blocks/ source of the "Pathshala Overview" Custom HTML Block (html/css/js, shadow DOM, `root_element`)
  utils.py          shared helpers: mobile normalising, time maths, fee status,
                    set_payment_totals, new_fee_payment, validate_gender_policy
  attendance.py     punch() check-in/out rules, auto_check_out (hourly)
  api.py            whitelisted kiosk_punch / kiosk_status / staff_punch, PIN lockout
  www/kiosk.*       full-screen tablet check-in page (keypad + optional QR via html5-qrcode)
  www/login.*       glass re-skin of Frappe login (extends frappe/www/login.html)
  public/css/login.css   login styles;  public/css/desk.css   glass styles scoped to body[data-route="Workspaces/Pathshala"]
  public/images/pathshala-*.png   brand assets
  pathshala/doctype/…   all DocTypes (module "Pathshala")
  pathshala/page/seat_map/   "Seat & Locker Map" desk page (/app/seat-map)
  pathshala/print_format/pathshala_id_card/   CR80 front/back student card (Student default print format)
  pathshala/workspace/pathshala/   desk workspace (overview block + shortcuts + link cards)
```

## DocTypes

| DocType | Notes |
|---|---|
| Pathshala Branch | opening/closing time. Named "Pathshala Branch" because ERPNext already has "Branch" |
| Study Zone | `gender_policy`: Co-ed / **Girls Only**. Name = `"{zone_name} - {branch}"` |
| Seat | name = `"{branch}-{SEAT_NO}"` (upper-cased in `autoname`, which runs *before* validate) |
| Study Shift | `shift_type` **Daily Hours** (`hours_per_day`, e.g. the 4/8/12 hr plans; no times) or **Time Slot** (start/end, same day only). Frappe fills an empty Time field with *now* on insert, so validation checks end > start rather than "missing" |
| Seat Plan | booking_type Shift / Full Day / Hourly. `rate` = total for the duration, or per hour for Hourly. `shift_type`/`hours_per_day` copied from the shift. `fixed_seat` (Daily Hours only) = premium reserved seat; `extra_hour_rate` overrides the settings overstay rate |
| Student | 10-digit unique `mobile`. `kiosk_pin` is a Password field (auto-generated 4 digits, shown once). `qr_token` → QR payload `PSL:<token>` |
| Seat Booking (submittable) | dates/times/amount calculated from the plan. status Draft/Active/Expired/Cancelled. `seat_mode` **Flexi** (Daily Hours plan without fixed seat: no zone/seat, window = branch hours) or Fixed. `extra_charges` = sum of overstay on its Attendance Logs |
| Locker | status maintained by `refresh_locker_status()`: Available/Occupied/Overdue/Maintenance |
| Locker Plan | rent + refundable security deposit |
| Locker Allocation (submittable) | status Active/Overdue/Renewed/Released/Cancelled. Release via `release_locker()` |
| Fee Payment (submittable) | **generic**: `reference_doctype` (Seat Booking / Locker Allocation) + `reference_name` Dynamic Link |
| Attendance Log | one row per visit. source Staff/Kiosk. `auto_checked_out`. `seat_assignment` Booking/Auto/Student/Staff. Daily Hours: `allowance_minutes`, `used_before_minutes`, `extra_minutes`, `extra_amount` |
| Kiosk Device | maps a tablet login user to a branch |
| Pathshala Settings (single) | kiosk rules: block if fee due, enforce shift timing, early-entry minutes, expiry warning days, repeat-scan seconds. Daily Hours: `extra_hour_rate`, `overstay_grace_minutes` |

## Business rules (keep these intact)

- **Girls Only:** non-female students can never be given a seat or locker in a Girls Only zone (`utils.validate_gender_policy`, enforced on the server). A student's gender can't be changed away from Female while they hold an active Girls Only booking.
- **Seat conflict:** a clash needs *both* overlapping dates *and* overlapping times on the same seat (submitted, Active bookings). Morning and evening students can share a seat, and an hourly booking can fill a gap. A student can't hold two overlapping bookings.
- Bookings must fall within branch hours. Monthly plans run `to_date = from_date + N months − 1 day`. Hourly bookings are a single day.
- **Fees:** `net = amount − discount + extra_charges` (lockers: `rent + deposit − discount`). Paid/outstanding/fee_status are recalculated from submitted Fee Payments (`set_payment_totals`). Overpayment is blocked, and non-cash payments need a Transaction Ref No.
- **Lockers:** the deposit is charged once; renewals set `security_deposit = 0` and mark the source "Renewed". An **Overdue** allocation blocks the locker for any date until it is renewed or released. Release requires zero outstanding, and the refund is capped at the deposit held across the renewal chain (`get_deposit_held`).
- **Kiosk punch** (`attendance.punch`): an open log means check-out (a repeat scan within `duplicate_punch_seconds` is ignored); otherwise check-in. Check-in needs an Active booking at this branch for today whose time window (minus early-entry grace) covers now. Fee due blocks entry. Plan ending soon or an overdue locker gives a warning. Results are `{status: success|warning|error|info, action: IN|OUT, message, student_name, photo, seat, zone}`.
- **Flexi (Daily Hours) seating:** at check-in `attendance.free_seats()` picks a seat: not occupied by an open log, and not reserved by a fixed booking overlapping [now, now + max(hours left today, 60 min)]. Allowed zones: Female → Girls Only + Co-ed, others → Co-ed (and the plan's gender policy/seat type). Order: last seat used, booking zone, **Girls Only zones before Co-ed** (keeps Co-ed free for boys), zone name, natural seat no. No free seat → error. The kiosk gets a `seat_token` (cache, 180 s) for `kiosk_free_seats`/`kiosk_change_seat`; staff use `attendance.change_seat`.
- **Daily hours & overstay:** visits on one day add up per booking. Billable = `max(0, used − allowance − grace)`; each log is charged the increase it causes, at the plan rate or the settings rate. `update_extra_charges()` rolls it into the booking's net/outstanding, so the normal fee-due block applies to overstay too.
- **Kiosk security:** `get_kiosk_branch()` ties a kiosk user to its Kiosk Device branch, while staff can pass `?branch=`. 5 wrong PINs locks that student out for 10 min. Read expiring cache keys with `frappe.cache.get_value(key, expires=True)`, otherwise the per-request local cache returns a stale value. Errors are deliberately generic ("Invalid mobile number or PIN").
- **Schedulers:** daily `expire_bookings`, daily `mark_overdue` (lockers), hourly `auto_check_out` (closes open logs at branch closing time).

## Frontend conventions

- **Workspace overview** (`workspace_blocks/pathshala_overview.*`): edit those files, then migrate. Don't edit the Custom HTML Block in the UI, because migrate overwrites it. Data comes from `pathshala.api.dashboard_stats`.
- **Seat map** states at the chosen date and time: free / partial (booked other hours, so sell hourly) / occupied / maintenance, with flags for checked-in, expiring soon and fee due. Seats and lockers sort naturally (C2 before C10).
- **ID card** is laid out with tables, because wkhtmltopdf is old WebKit. Keep that, and include `-webkit-` gradient fallbacks.
- Brand colours: blue `#3C6DF5`, deep blue `#1E3CF4`, teal `#6CCAB7`, lime `#ADFC54`. Font Poppins. The look is "glass": `backdrop-filter: blur()` over blurred colour shapes.
- `www/login.html` **extends** `frappe/www/login.html` and only overrides `navbar`, `footer`, `head_include` and `content` (calling `self.page_content()`). Don't copy Frappe's form markup, because `login.js` depends on its IDs. All CSS is scoped under `body.psl-login`.
- Files under `/assets` are browser-cached for 12h, so cache-bust with `?v=<mtime>` (see `www/login.py`).
- `www/kiosk.html` extends `templates/base.html` with navbar/footer blanked. Its JS is in the colocated `kiosk.js` and uses `frappe.call`, which handles CSRF.

## Code style

Tabs, 110-char lines (ruff config in `pyproject.toml`). Controllers use `frappe.throw(_(...))` with translatable strings. Whitelisted methods check `doc.check_permission(...)`. Mapped-doc helpers (`make_renewal`, `make_payment`) return unsaved docs for `frappe.model.open_mapped_doc`.

## Ideas not yet built

UPI QR on the "fee due" kiosk screen, WhatsApp alerts (the `frappe_whatsapp` app is in the bench but not installed on this site), reports (occupancy, dues, attendance).
