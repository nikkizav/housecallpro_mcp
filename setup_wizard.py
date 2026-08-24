#!/usr/bin/env python3
"""
setup_wizard.py — one-time setup for the Housecall Pro MCP server.

Run this once per machine, per Housecall Pro account:

    uv run python setup_wizard.py

It will:
  1. Ask for (or read) your Housecall Pro API key and verify it works
  2. Discover YOUR account's employees, pipeline stages and labor rates
  3. Write config.json with the real IDs from your account
  4. Print the exact Claude Desktop config block to paste, with correct paths

Why this exists: employee IDs (pro_...) and pipeline-stage IDs (kcs_...) are
unique to each Housecall Pro account.  Copying someone else's config.json
produces a setup that looks valid but matches nothing in your account — every
capacity and pipeline tool silently returns empty.  This script builds the
config from your own account so that cannot happen.

Nothing is sent anywhere except to api.housecallpro.com.  Your API key is
written to the Claude Desktop config, not to config.json.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx is missing. Run this with:  uv run python setup_wizard.py")

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "config.json"
BASE_URL = "https://api.housecallpro.com"

# 8.5h booked window less 8.0h productive = the 30-min unpaid break the
# time-variance model subtracts from any full day.
DEFAULTS = {
    "productive_hours_per_day": 8.0,
    "appointment_window_hours": 8.5,
    "blended_cost_per_tech_hour": 95.0,
    "capacity_target_hours_per_day": 44.0,
    "overtime_threshold_hours_per_day": 40,
}


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)
    return answer or (default or "")


def ask_float(prompt: str, default: float) -> float:
    while True:
        raw = ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number.")


def ask_yes(prompt: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    raw = ask(f"{prompt} ({d})").lower()
    if not raw:
        return default
    return raw.startswith("y")


async def get(client: httpx.AsyncClient, path: str, params: dict | None = None):
    """GET with a couple of retries; returns (payload, error_string)."""
    delay = 1.0
    for attempt in range(4):
        try:
            r = await client.get(path, params=params or {})
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == 3:
                    return None, f"HTTP {r.status_code}"
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if r.status_code >= 400:
                return None, f"HTTP {r.status_code}"
            return r.json(), None
        except Exception as e:  # transport hiccup
            if attempt == 3:
                return None, type(e).__name__
            await asyncio.sleep(delay)
            delay *= 2
    return None, "retries exhausted"


async def discover(api_key: str) -> dict | None:
    headers = {"Authorization": f"Token {api_key}",
               "Content-Type": "application/json",
               "Accept": "application/json"}
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers,
                                 timeout=30.0) as client:
        print("\nVerifying API key ...")
        company, err = await get(client, "/company")
        if err:
            print(f"  ✗ {err}")
            if "401" in err or "403" in err:
                print("    The key was rejected. Generate a fresh one in Housecall Pro:")
                print("      My Apps (nine-squares icon, top bar, next to Settings)")
                print("      > Go to App Store > search 'API' > API Key Management")
                print("      > Generate a new API key")
                print("    API access requires the MAX plan.")
            return None
        name = (company or {}).get("name") or (company or {}).get("company_name") or "?"
        print(f"  ✓ Connected to: {name}")

        print("Fetching employees ...")
        emp, err = await get(client, "/employees", {"page": 1, "page_size": 200})
        employees = (emp or {}).get("employees") or []
        print(f"  {'✓' if not err else '⚠'} {len(employees)} employee(s)"
              + (f" ({err})" if err else ""))

        print("Fetching pipeline stages ...")
        pipe, err = await get(client, "/pipeline/statuses",
                              {"resource_type": "job", "page": 1, "page_size": 50})
        stages = []
        if isinstance(pipe, dict):
            stages = pipe.get("statuses") or pipe.get("data") or []
        elif isinstance(pipe, list):
            stages = pipe
        print(f"  {'✓' if not err else '⚠'} {len(stages)} stage(s)"
              + (f" ({err})" if err else ""))

        print("Fetching labor rates from the price book ...")
        rates: list[dict] = []
        svc, err = await get(client, "/api/price_book/services",
                             {"page": 1, "page_size": 50,
                              "expand[]": ["service_labor_rates"]})
        seen = set()
        for s in ((svc or {}).get("data") or []):
            for slr in ((s.get("service_labor_rates") or {}).get("data") or []):
                lr = slr.get("labor_rate") or {}
                key = lr.get("uuid")
                if key and key not in seen:
                    seen.add(key)
                    rates.append({"name": lr.get("name"),
                                  "hourly_cost": lr.get("hourly_cost"),
                                  "hourly_price": lr.get("hourly_price"),
                                  "default": lr.get("default")})
        print(f"  {'✓' if not err else '⚠'} {len(rates)} distinct labor rate(s)")

        return {"company": company or {}, "company_name": name,
                "employees": employees, "stages": stages, "rates": rates}


def choose_field_techs(employees: list[dict]) -> list[dict]:
    """Interactively mark who actually turns wrenches."""
    print("\n" + "─" * 66)
    print("Which of these are FIELD TECHS?")
    print("Field techs count toward scheduling capacity. Owners, office staff and")
    print("estimators should be excluded so capacity math is not inflated.")
    print("─" * 66)
    for i, e in enumerate(employees, 1):
        role = e.get("role") or ""
        print(f"  {i:2d}. {e.get('first_name','')} {e.get('last_name','')}"
              f"{f'  ({role})' if role else ''}")
    print("\nEnter the numbers of the field techs, comma separated (e.g. 1,3,4).")
    print("Press Enter to accept all.")
    raw = ask("Field techs")
    if not raw:
        picked = list(range(1, len(employees) + 1))
    else:
        picked = []
        for part in raw.replace(" ", "").split(","):
            if part.isdigit() and 1 <= int(part) <= len(employees):
                picked.append(int(part))
        if not picked:
            print("  Nothing recognised — treating everyone as a field tech.")
            picked = list(range(1, len(employees) + 1))

    print("\nWhich of those are APPRENTICES / part-time?")
    print("They count 0.5x toward capacity but can still be booked a full day.")
    print("Use the same numbers from the list above. Press Enter for none.")
    appr_raw = ask("Apprentices")
    appr = {int(p) for p in appr_raw.replace(" ", "").split(",")
            if p.isdigit()} if appr_raw else set()

    team = []
    for idx in picked:
        e = employees[idx - 1]
        is_appr = idx in appr
        team.append({
            "name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
            "role": "apprentice" if is_appr else "lead_tech",
            "hcp_id": e.get("id"),
            "field_tech": True,
            "capacity_multiplier": 0.5 if is_appr else 1.0,
            "notes": "",
        })
    # keep non-field staff on record, but at zero capacity
    for i, e in enumerate(employees, 1):
        if i in picked:
            continue
        team.append({
            "name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
            "role": "office",
            "hcp_id": e.get("id"),
            "field_tech": False,
            "capacity_multiplier": 0,
            "notes": "Not a field tech — excluded from capacity math.",
        })
    return team


def build_config(found: dict, team: list[dict], sched: dict, tz: str) -> dict:
    stages = []
    for i, s in enumerate(found["stages"], 1):
        stages.append({
            "order": i,
            "name": s.get("name"),
            "id": s.get("id") or s.get("status_id"),
            "status_type": s.get("status_type"),
            "used_for": ["job"],
            "notes": "",
        })
    return {
        "_comment": ("Company configuration for the Housecall Pro MCP server. "
                     "Generated by setup_wizard.py from THIS account — employee and "
                     "pipeline IDs are account-specific, so do not copy this file "
                     "to another Housecall Pro account. Re-run the wizard instead."),
        "_generated_by": "setup_wizard.py",
        "company": {
            "name": found["company_name"],
            "short_name": (found["company_name"] or "")[:12],
            "timezone": tz,
        },
        "scheduling": {
            **sched,
            "workdays": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "notes": ("productive_hours_per_day is real capacity; "
                      "appointment_window_hours is the booked window including the "
                      "unpaid break. The difference is subtracted from any full day "
                      "in hcp_time_variance and hcp_post_job_analysis."),
            "blended_cost_note": ("Fully-loaded cost per tech-hour — labor, vehicle, "
                                  "insurance, overhead. Used for margin math."),
        },
        "team": team,
        "job_pipeline_stages": stages,
        "discovered_labor_rates": found["rates"],
        "api": {
            "base_url": BASE_URL,
            "auth_header": "Authorization: Token {API_KEY}",
        },
    }


def uv_command() -> str:
    """Absolute path to uv when we can find it, else the bare name.

    Claude Desktop launches servers without a login shell, so it often does not
    see PATH additions from .zshrc or the Windows user PATH. A bare "uv" then
    fails with ENOENT even though it works fine in a terminal.
    """
    found = shutil.which("uv")
    if found:
        return found
    for cand in (Path.home() / ".local" / "bin" / "uv",
                 Path.home() / ".cargo" / "bin" / "uv",
                 Path("/opt/homebrew/bin/uv"),
                 Path("/usr/local/bin/uv")):
        if cand.is_file():
            return str(cand)
    return "uv"


def server_entry(api_key: str) -> dict:
    """The one mcpServers entry this project needs."""
    main = (HERE / "housecallpro_LHSTL.py").resolve()
    return {
        "command": uv_command(),
        "args": ["run", "--project", str(HERE.resolve()), "python", str(main)],
        "env": {"HOUSECALL_PRO_API_KEY": api_key},
    }


def desktop_block(api_key: str) -> str:
    return json.dumps({"mcpServers": {"housecallpro": server_entry(api_key)}},
                      indent=2)


def claude_config_dirs() -> list[Path]:
    """Every location Claude Desktop is known to keep claude_desktop_config.json.

    Windows has two, and which one you get depends on how Claude was installed:
      - the .exe installer writes to %APPDATA%\\Claude
      - the Microsoft Store (MSIX) build is sandboxed, so the same path is
        redirected to
        %LOCALAPPDATA%\\Packages\\Claude_<id>\\LocalCache\\Roaming\\Claude
    The package id differs per machine, hence the glob.
    """
    home = Path.home()
    out: list[Path] = []
    if sys.platform == "darwin":
        out.append(home / "Library" / "Application Support" / "Claude")
    elif os.name == "nt":
        if appdata := os.environ.get("APPDATA"):
            out.append(Path(appdata) / "Claude")
        if local := os.environ.get("LOCALAPPDATA"):
            out.extend(sorted(
                (Path(local) / "Packages").glob("Claude_*/LocalCache/Roaming/Claude")
            ))
    else:
        out.append(home / ".config" / "Claude")
    return out


def choose_dir(cands: list[Path]) -> Path | None:
    """Prefer a folder that already holds the config, then any that exists."""
    for d in cands:
        if (d / "claude_desktop_config.json").is_file():
            return d
    for d in cands:
        if d.is_dir():
            return d
    return None


def pick_claude_dir() -> tuple[Path | None, list[Path]]:
    """(best directory to write into, every candidate we looked at)."""
    cands = claude_config_dirs()
    return choose_dir(cands), cands


def install_into_claude(cfg_dir: Path, api_key: str) -> tuple[bool, str]:
    """Merge our server into claude_desktop_config.json, backing up what's there.

    Merging matters: the file usually holds other MCP servers, and replacing it
    wholesale would disconnect them.
    """
    path = cfg_dir / "claude_desktop_config.json"
    existing: dict = {}
    note = ""
    if path.is_file():
        raw = path.read_text(encoding="utf-8-sig").strip()
        if raw:
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError as e:
                return False, (f"{path} exists but is not valid JSON ({e}). "
                               f"Fix or rename it, then re-run this wizard.")
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = path.parent / f"claude_desktop_config.backup-{stamp}.json"
            backup.write_text(raw, encoding="utf-8")
            note = f"  previous file backed up to: {backup.name}\n"
    if not isinstance(existing, dict):
        return False, f"{path} does not contain a JSON object."

    servers = existing.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    replaced = "housecallpro" in servers
    servers["housecallpro"] = server_entry(api_key)
    existing["mcpServers"] = servers

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    others = [k for k in servers if k != "housecallpro"]
    return True, (
        f"{note}  wrote: {path}\n"
        f"  {'updated' if replaced else 'added'} the 'housecallpro' entry"
        + (f", kept {len(others)} other server(s) untouched" if others else "")
    )


async def main() -> int:
    print("=" * 66)
    print("  Housecall Pro MCP server — setup")
    print("=" * 66)

    if CONFIG_PATH.exists():
        print(f"\n{CONFIG_PATH.name} already exists.")
        if not ask_yes("Overwrite it?", default=False):
            print("Left it alone. Nothing changed.")
            return 0

    key = os.environ.get("HOUSECALL_PRO_API_KEY", "")
    if key:
        print(f"\nUsing HOUSECALL_PRO_API_KEY from the environment "
              f"(ends ...{key[-4:]}).")
        if not ask_yes("Use this key?", default=True):
            key = ""
    if not key:
        print("\nFind your key in Housecall Pro:")
        print("  1. Top bar > My Apps tile (nine small squares, next to Settings)")
        print("  2. Go to App Store")
        print("  3. Search for 'API'")
        print("  4. API Key Management tile")
        print("  5. Generate a new API key - name it 'Claude'")
        print("(API access requires the MAX plan.)")
        key = ask("API key")
    if not key:
        print("No key given — cannot continue.")
        return 1

    found = await discover(key)
    if not found:
        return 1
    if not found["employees"]:
        print("\nNo employees came back, so capacity tools cannot be configured.")
        if not ask_yes("Continue anyway?", default=False):
            return 1

    team = choose_field_techs(found["employees"]) if found["employees"] else []

    print("\n" + "─" * 66)
    print("Scheduling and cost settings")
    print("─" * 66)
    default_cost = DEFAULTS["blended_cost_per_tech_hour"]
    if found["rates"]:
        costs = [r["hourly_cost"] / 100 for r in found["rates"]
                 if isinstance(r.get("hourly_cost"), int)]
        if costs:
            print(f"Labor rates in your price book: "
                  f"{', '.join(f'${c:,.0f}' for c in sorted(set(costs)))} /hr cost")
            print("Your blended cost should ALSO include vehicle, insurance and")
            print("overhead — it is usually higher than the price-book rate.")
    # These two numbers interact: the GAP between them is the unpaid break the
    # time model deducts from every full day. Asked separately, nobody notices —
    # one tester set 7.25 productive against an 8.5 window and silently got a
    # 75-minute deduction on every day. So show the result and let them confirm.
    print("\nThese next two work together. The difference between them is the")
    print("unpaid break subtracted from any day of 6 hours or more.")
    while True:
        productive = ask_float("Productive hours per tech per day",
                               DEFAULTS["productive_hours_per_day"])
        window = ask_float("Booked appointment window per day (incl. break)",
                           DEFAULTS["appointment_window_hours"])
        gap = window - productive
        print()
        if gap < 0:
            print(f"  ⚠ The window ({window}h) is SHORTER than productive hours "
                  f"({productive}h).")
            print("    That would add time rather than subtract it. Try again.")
            continue
        print(f"  → {window}h booked − {productive}h productive "
              f"= a {gap * 60:.0f}-minute break deducted from every full day.")
        if gap > 0.75:
            print(f"    That is a long break. If your crews take ~30 minutes, set")
            print(f"    productive to {window - 0.5:g} instead.")
        elif gap == 0:
            print("    No break deducted — full booked window counts as worked time.")
        if ask_yes("  Is that right?", default=True):
            break
        print()

    sched = {
        "productive_hours_per_day": productive,
        "appointment_window_hours": window,
        "blended_cost_per_tech_hour": ask_float(
            "Fully-loaded cost per tech-hour ($)", default_cost),
        "capacity_target_hours_per_day": ask_float(
            "Team capacity target, tech-hours per day",
            DEFAULTS["capacity_target_hours_per_day"]),
        "overtime_threshold_hours_per_day": ask_float(
            "Flag a day as overtime risk above (tech-hours)",
            DEFAULTS["overtime_threshold_hours_per_day"]),
    }
    tz = ask("Timezone", "America/Chicago")

    cfg = build_config(found, team, sched, tz)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    field = [m for m in team if m.get("field_tech")]
    print("\n" + "=" * 66)
    print(f"  Wrote {CONFIG_PATH}")
    print("=" * 66)
    print(f"  company        : {cfg['company']['name']}")
    print(f"  field techs    : {len(field)}")
    print(f"  pipeline stages: {len(cfg['job_pipeline_stages'])}")
    print(f"  cost per hour  : ${sched['blended_cost_per_tech_hour']:,.2f}")

    # ── connect it to Claude Desktop ─────────────────────────────────────────
    # Hand-editing this JSON is the single biggest failure point in setup, so
    # offer to do it. The key is already in hand, which also removes the "where
    # do I paste the API key" step entirely.
    print("\n" + "─" * 66)
    print("Connecting it to Claude Desktop")
    print("─" * 66)

    cfg_dir, candidates = pick_claude_dir()
    if cfg_dir:
        target = cfg_dir / "claude_desktop_config.json"
        print(f"Found Claude Desktop's settings folder:\n  {cfg_dir}")
        if target.is_file():
            print(f"  ({target.name} already exists — your other MCP servers, if any,")
            print("   will be kept, and the current file backed up first.)")
        if ask_yes("\nWrite the connection into it for you?", default=True):
            ok, msg = install_into_claude(cfg_dir, key)
            print()
            if ok:
                print(msg)
                print("\n" + "=" * 66)
                print("  Setup complete.")
                print("=" * 66)
                print("Now QUIT Claude Desktop completely and reopen it:")
                print("  Mac      Cmd+Q  (closing the window is not enough)")
                print("  Windows  right-click the Claude icon in the system tray")
                print("           (bottom-right, maybe behind the ^ arrow) > Quit")
                print("\nThen ask Claude:  run hcp_check_setup")
                return 0
            print(f"Couldn't write it automatically: {msg}")
            print("Falling back to the manual steps below.\n")
    else:
        print("Couldn't find Claude Desktop's settings folder. That usually means")
        print("Claude Desktop isn't installed yet, or has never been opened —")
        print("the folder is created the first time it runs.")
        print("Install it from https://claude.ai/download, open it once, then")
        print("re-run this wizard and it will finish the job.\n")
        print("Looked in:")
        for c in candidates:
            print(f"  {c}")

    # ── manual fallback ──────────────────────────────────────────────────────
    print("\n" + "─" * 66)
    print("To do it by hand, open claude_desktop_config.json in:")
    if sys.platform == "darwin":
        print("  ~/Library/Application Support/Claude/")
    elif os.name == "nt":
        print("  %APPDATA%\\Claude\\                        (.exe install)")
        print("  %LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Roaming\\Claude\\")
        print("                                            (Microsoft Store install)")
    else:
        print("  ~/.config/Claude/")
    print("\nand add the \"housecallpro\" block below INSIDE the existing")
    print("\"mcpServers\" object. Do not add a second \"mcpServers\" key.")
    print("The API key is already filled in for you.")
    print("─" * 66)
    print(desktop_block(key))
    print("─" * 66)
    print("Then quit Claude Desktop completely, reopen it, and ask Claude:")
    print("  run hcp_check_setup")
    print("\nconfig.json holds no secrets and is gitignored; your API key lives")
    print("only in the Claude Desktop config.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
