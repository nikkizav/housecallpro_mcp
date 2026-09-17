#!/usr/bin/env python3
"""
export.py — Pull a date range of jobs out of Housecall Pro as JSON and CSV.

    uv run python export.py --start 2026-01-01 --end 2026-09-14 --out ytd

Writes <out>.json and <out>.csv. One row per job, with the money and the time
already worked out, so an analysis starts from figures rather than from raw API
payloads.

WHY THIS EXISTS RATHER THAN A HAND-ROLLED SCRIPT
------------------------------------------------
Housecall Pro rate-limits fan-out. Firing two requests per job across fifty jobs
reliably draws HTTP 429s, and the obvious way to write the loop —
asyncio.gather(..., return_exceptions=True) — turns each throttled response into
an empty payload. That does not look like an error. It looks like a job with no
appointments and no line items, which is to say it looks like data.

That exact bug once corrupted 139 of 295 jobs in an analysis here and produced
two confident, entirely false findings: "66 jobs have no appointment records"
and an "April 2026 cutover". The truth was 100% appointment coverage. Nothing
crashed and nothing warned.

So this reuses the server's hardened path — a process-wide rate gate, capped
concurrency, retry with backoff — and any job whose fetch still fails is
EXCLUDED and NAMED at the end rather than being handed back as zeroes. If the
run reports exclusions, the numbers are incomplete and the report says so.

Pagination is followed to the last page for the same reason: stopping early
looks identical to a quiet month.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import housecallpro_LHSTL as H   # noqa: E402  (path set above)


async def _all_jobs(client, start: str, end: str, quiet: bool) -> tuple[list, list]:
    """Every job scheduled in the window, following pagination to the end."""
    jobs, notes, page = [], [], 1
    while page <= 60:
        data, err = await H._get_json(client, "/jobs", params={
            "scheduled_start_min": f"{start}T00:00:00Z",
            "scheduled_start_max": f"{end}T23:59:59Z",
            "page": page, "page_size": 100})
        if err:
            notes.append(f"job list page {page} failed ({err}) — "
                         f"THIS EXPORT IS INCOMPLETE")
            break
        batch = data.get("jobs", [])
        jobs.extend(batch)
        total = data.get("total_pages") or 1
        if not quiet:
            print(f"  page {page}/{total} — {len(jobs)} jobs", file=sys.stderr)
        if page >= total:
            break
        page += 1
    return jobs, notes


def _row(job: dict, appts: list, items: list, invoices: list,
         materials: list, cfg: dict) -> dict:
    """One flat row: identity, money, and time, with the cents already divided."""
    num = str(job.get("invoice_number") or "")
    cust = job.get("customer") or {}
    addr = job.get("address") or {}
    start, end, _ = H._sched(job.get("schedule"))

    mat_billed = sum(int(i.get("amount") or 0) for i in items
                     if i.get("kind") == "materials") / 100
    labor_billed = sum(int(i.get("amount") or 0) for i in items
                       if i.get("kind") == "labor") / 100
    mat_cost = sum(float(m.get("unit_cost") or 0) / 100
                   * float(m.get("quantity") or 0) for m in materials)

    # _job_money returns CENTS throughout — the API's own unit. Dividing here,
    # once, is the whole point of exporting figures rather than payloads.
    money = H._job_money(job, invoices)
    C = lambda k: round((money.get(k) or 0) / 100, 2)

    est = H._estimate_job_time(job, appts, items, cfg)
    hours = est.get("actual") or 0.0
    rate = float(cfg.get("labor_cost_per_hour") or 0)
    labor_cost = hours * rate
    collected = C("collected")

    return {
        "job_number": num,
        "customer": f"{cust.get('first_name','')} {cust.get('last_name','')}".strip(),
        "city": addr.get("city", ""),
        "description": (job.get("description") or "")[:120],
        "work_status": H._norm_status(str(job.get("work_status") or "")),
        "scheduled_start": str(start or "")[:10],
        "scheduled_end": str(end or "")[:10],
        "days": est.get("ndays") or 0,
        "quoted_hours": round(est.get("quoted") or 0.0, 2),
        "scheduled_hours": round(est.get("scheduled") or 0.0, 2),
        "actual_hours": round(hours, 2),
        # measured = trust it; estimated = directional; scheduled = no signal.
        # Judge quote accuracy from measured rows ONLY — on estimated rows
        # actual is derived from the schedule, so comparing the two measures
        # calendar blocking rather than worked time.
        "time_grade": est.get("grade", ""),
        "anchor_coverage_pct": round((est.get("coverage") or 0.0) * 100, 0),
        "contract_value": C("contract"),
        "invoiced": C("invoiced"),
        "collected": collected,
        "outstanding": C("outstanding"),
        "unbilled": C("unbilled"),
        "discount": C("discount"),
        "labor_billed": round(labor_billed, 2),
        "materials_billed": round(mat_billed, 2),
        "labor_cost": round(labor_cost, 2),
        "materials_cost": round(mat_cost, 2),
        "gross_profit": round(collected - labor_cost - mat_cost, 2),
        "appointments": len(appts),
        "line_items": len(items),
        "posted_materials": len(materials),
    }


def _assemble(jobs: list, results: list, cfg: dict) -> tuple[list, list, list]:
    """Turn fetched payloads into rows. Returns (rows, excluded, quirks).

    The one tolerated failure is HTTP 400 on /appointments, which Housecall Pro
    returns for a CANCELED job. That is a real answer — the job has none — not a
    transport problem, and excluding every canceled job from every export would
    lose their money data permanently. It is still recorded per job so the
    tolerance is visible rather than assumed.

    Every other error excludes the job and is named. A throttled fetch must
    never reach a row as a zero.
    """
    rows, excluded, quirks = [], [], []
    for job, four in zip(jobs, results):
        num = str(job.get("invoice_number") or job.get("id"))
        (ap, ap_err), (li, li_err), (inv, inv_err), (mat, mat_err) = four
        canceled = H._norm_status(str(job.get("work_status") or "")).endswith("canceled")
        if ap_err == "HTTP 400" and canceled:
            quirks.append(f"#{num}: canceled job, appointments unavailable "
                          f"(API returns 400) — counted as none")
            ap, ap_err = {}, None
        errs = [e for e in (ap_err, li_err, inv_err, mat_err) if e]
        if errs:
            excluded.append((num, ", ".join(sorted(set(errs)))))
            continue
        rows.append(_row(
            job,
            (ap or {}).get("appointments") or [],
            li.get("data") or li.get("line_items") or [],
            inv.get("invoices") or inv.get("data") or [],
            mat.get("job_input_materials") or [],
            cfg))
    return rows, excluded, quirks


async def run(start: str, end: str, out: str, quiet: bool) -> int:
    raw = H._load_config()
    cfg = H._time_model(raw)
    # Fully loaded cost per tech-hour — wages, taxes, vehicle, insurance,
    # overhead — not the hourly wage. Every profit figure below rests on it.
    cfg["labor_cost_per_hour"] = float(
        (raw.get("scheduling") or {}).get("blended_cost_per_tech_hour", 95.0))
    async with H._hcp_client() as client:
        if not quiet:
            print(f"Fetching jobs {start} → {end}…", file=sys.stderr)
        jobs, notes = await _all_jobs(client, start, end, quiet)
        if not jobs:
            print("No jobs in that window." + ("\n" + "\n".join(notes) if notes else ""),
                  file=sys.stderr)
            return 1
        if not quiet:
            print(f"Fetching detail for {len(jobs)} jobs "
                  f"(capped at {H._HCP_FANOUT} concurrent)…", file=sys.stderr)
        results = await H._fanout_jobs(client, jobs, [
            "/appointments", "/line_items", "/invoices", "/job_input_materials"])

    rows, excluded, quirks = _assemble(jobs, results, cfg)

    # ── one retry pass, slower ───────────────────────────────────────────────
    # Four requests per job is twice the pressure of the analysis tools, so a
    # long window can exhaust the retry budget on a handful of jobs. Rather than
    # telling the user to run it again, run the stragglers again here at lower
    # concurrency — which is what fixes a 429 anyway.
    if excluded:
        retry_nums = {n for n, _ in excluded}
        retry_jobs = [j for j in jobs
                      if str(j.get("invoice_number") or j.get("id")) in retry_nums]
        if not quiet:
            print(f"Retrying {len(retry_jobs)} job(s) at lower concurrency…",
                  file=sys.stderr)
        await asyncio.sleep(5)
        async with H._hcp_client() as client:
            again = await H._fanout_jobs(client, retry_jobs, [
                "/appointments", "/line_items", "/invoices",
                "/job_input_materials"], limit=2)
        more, excluded, more_quirks = _assemble(retry_jobs, again, cfg)
        rows.extend(more)
        quirks.extend(more_quirks)

    rows.sort(key=lambda r: (r["scheduled_start"], r["job_number"]))
    stem = Path(out).expanduser()
    if stem.suffix in (".json", ".csv"):
        stem = stem.with_suffix("")
    stem.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": date.today().isoformat(),
        "window": {"start": start, "end": end},
        "job_count": len(rows),
        "excluded": [{"job": n, "error": e} for n, e in excluded],
        "complete": not excluded and not notes,
        "jobs": rows,
    }
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2))
    with open(stem.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} jobs → {stem.with_suffix('.json')} and "
          f"{stem.with_suffix('.csv')}")
    graded: dict = {}
    for r in rows:
        graded[r["time_grade"]] = graded.get(r["time_grade"], 0) + 1
    print("  time grades: " + ", ".join(f"{k or '—'}={v}" for k, v in
                                        sorted(graded.items())))
    print(f"  contract value: ${sum(r['contract_value'] for r in rows):,.2f}"
          f"   collected: ${sum(r['collected'] for r in rows):,.2f}")
    for n in notes:
        print(f"  ⚠ {n}")
    for q in quirks:
        print(f"  ℹ {q}")
    if excluded:
        print(f"  ⚠ {len(excluded)} job(s) EXCLUDED — their data could not be "
              f"read, so the totals above are short by that much:")
        for n, e in excluded[:12]:
            print(f"      #{n}: {e}")
        print("  Re-run to pick them up; these are usually transient.")
    else:
        print("  ✓ every job fetched cleanly — totals are complete")
    return 0


def main() -> int:
    today = date.today()
    p = argparse.ArgumentParser(
        description="Export Housecall Pro jobs with money and time worked out.")
    p.add_argument("--start", default=(today - timedelta(days=90)).isoformat(),
                   help="First scheduled day, YYYY-MM-DD (default: 90 days ago)")
    p.add_argument("--end", default=today.isoformat(),
                   help="Last scheduled day, YYYY-MM-DD (default: today)")
    p.add_argument("--out", default="hcp_export",
                   help="Output path without extension (default: hcp_export)")
    p.add_argument("--quiet", action="store_true", help="No progress output")
    a = p.parse_args()
    return asyncio.run(run(a.start, a.end, a.out, a.quiet))


if __name__ == "__main__":
    raise SystemExit(main())
