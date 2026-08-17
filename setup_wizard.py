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
import sys
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
                print("    The key was rejected. Copy it again from Housecall Pro >")
                print("    Settings > Integrations > API. API access needs the MAX plan.")
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


def desktop_block(api_key_placeholder: str) -> str:
    main = (HERE / "housecallpro_LHSTL.py").resolve()
    return json.dumps({
        "mcpServers": {
            "housecallpro": {
                "command": "uv",
                "args": ["run", "--project", str(HERE.resolve()),
                         "python", str(main)],
                "env": {"HOUSECALL_PRO_API_KEY": api_key_placeholder},
            }
        }
    }, indent=2)


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
        print("\nFind your key: Housecall Pro > Settings > Integrations > API")
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
    sched = {
        "productive_hours_per_day": ask_float(
            "Productive hours per tech per day", DEFAULTS["productive_hours_per_day"]),
        "appointment_window_hours": ask_float(
            "Booked appointment window per day (incl. break)",
            DEFAULTS["appointment_window_hours"]),
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

    print("\n" + "─" * 66)
    print("Add this to your Claude Desktop config, inside \"mcpServers\":")
    print("  macOS   ~/Library/Application Support/Claude/claude_desktop_config.json")
    print("  Windows %APPDATA%\\Claude\\claude_desktop_config.json")
    print("─" * 66)
    print(desktop_block("PASTE_YOUR_API_KEY_HERE"))
    print("─" * 66)
    print("Then restart Claude Desktop completely (quit, not just close the")
    print("window) and ask Claude:  run hcp_check_setup")
    print("\nconfig.json holds no secrets and is gitignored by default; your API")
    print("key lives only in the Claude Desktop config.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
