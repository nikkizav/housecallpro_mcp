# Housecall Pro + Claude — MCP Server

Connects Claude to your Housecall Pro account so you can review the schedule,
plan capacity, and measure **quoted vs. scheduled vs. actually-worked hours** by
talking to it in plain language.

Built by and for a home-services franchise. Runs entirely on your own machine
against your own API key — no third-party servers involved.

```
You:    How did last week's jobs stack up against what we quoted?
Claude: [runs hcp_time_variance]
        MEASURED (21 jobs, fully timestamp-anchored)
          Quoted 91.8 → Actual 92.5 tech-hrs   (101% — quoting is accurate)
          Scheduled was 129.2 → 36.8 tech-hrs of calendar blocked but not worked
```

---

## Contents

- [What you need](#what-you-need)
- [Install](#install) — five steps, about 15 minutes
- [Verify it worked](#verify-it-worked)
- [The time model](#the-time-model-read-this-before-trusting-the-numbers) ← **read this**
- [What to ask Claude](#what-to-ask-claude)
- [Tool reference](#tool-reference)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [For franchise partners](#for-franchise-partners)

---

## What you need

| | |
|---|---|
| **Housecall Pro MAX plan** | API access is MAX-only. Without it, nothing here works. |
| **Claude Desktop** | [claude.ai/download](https://claude.ai/download). Also works with Claude Code and Cowork. |
| **A terminal** | Terminal on macOS, PowerShell on Windows. You'll paste a few commands. |
| **~15 minutes** | Mostly waiting on downloads. |

You do **not** need to know Python.

---

## Install

### 1. Get your API key

Housecall Pro → **Settings** → **Integrations** → **API** → create a key and copy it.

Treat it like a password: it can read customer data and create and modify jobs,
estimates, and invoices.

### 2. Install `uv`

`uv` runs the server and manages Python for you. The system Python on most Macs
is too old (3.9); `uv` handles that.

**macOS**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen your terminal, then confirm:
```bash
uv --version
```

### 3. Download this repo

```bash
git clone <REPO_URL> housecallpro_mcp
cd housecallpro_mcp
```

No git? Use GitHub's **Code → Download ZIP**, unzip it, and `cd` into the folder.

### 4. Run the setup wizard

```bash
uv run python setup_wizard.py
```

This is the step that makes the tool yours. It will:

- verify your API key against Housecall Pro
- pull **your** employees, pipeline stages, and price-book labor rates
- ask which people are field techs (so owners and office staff don't inflate capacity)
- ask for your fully-loaded cost per tech-hour
- write `config.json`
- print the exact Claude Desktop block to paste, with correct paths for your machine

> **Why a wizard instead of a config file to copy?** Employee IDs (`pro_…`) and
> pipeline-stage IDs (`kcs_…`) are unique per Housecall Pro account. A config
> copied from another franchise looks perfectly valid but matches nothing in your
> account — capacity and pipeline tools then return empty results without any
> error. The wizard builds the config from your own account so that can't happen.

### 5. Add to Claude Desktop and restart

Open your Claude Desktop config:

- **macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows** — `%APPDATA%\Claude\claude_desktop_config.json`

Paste the block the wizard printed, with your real API key. It looks like:

```json
{
  "mcpServers": {
    "housecallpro": {
      "command": "uv",
      "args": ["run", "--project", "/full/path/to/housecallpro_mcp",
               "python", "/full/path/to/housecallpro_mcp/housecallpro_LHSTL.py"],
      "env": { "HOUSECALL_PRO_API_KEY": "your_key_here" }
    }
  }
}
```

If the file already has `mcpServers`, add `"housecallpro"` alongside the existing
entries rather than replacing the block. Paths must be absolute.

Then **fully quit** Claude Desktop — Cmd+Q on macOS, not just closing the window —
and reopen it.

---

## Verify it worked

Ask Claude:

```
run hcp_check_setup
```

You should see something like:

```
╔══ SETUP CHECK ═══════════════════════════════════════════════
║  ✓ API key works — connected to: Your Company Name
║  ✓ Config found — /path/to/housecallpro_mcp/config.json
║  ✓ Labor cost rate: $95.00/tech-hour
║  ✓ All 6 configured field-tech IDs exist in this account
║  ✓ 21 pipeline stages configured
╠══════════════════════════════════════════════════════════════
║  RESULT: ready to use ✓
```

`hcp_check_setup` cross-checks your config against the live account, so it catches
the failure that is otherwise invisible: IDs that belong to a different company.
Run it again any time a tool returns empty or implausible numbers.

---

## The time model (read this before trusting the numbers)

Housecall Pro's public API exposes **one** `started_at` and **one** `completed_at`
per job — never per appointment or per tech. There is no per-tech time tracking
and no pause data. Everything below follows from that limit.

**Actual hours are built per day, not as one span.** For each appointment day:

```
day 1      real started_at   →  scheduled end
middle     scheduled window     (inference — no data exists for these)
last day   scheduled start   →  real completed_at
```

Each day is multiplied by the crew dispatched *that day*, minus the unpaid break
on any day of 6h or more. Measuring instead as one `started_at → completed_at`
span is what makes a two-week job read as 300 hours.

**Every job carries a confidence grade.** Nothing is silently averaged in:

| Grade | Meaning | Trust |
|---|---|---|
| `MEASURED` | Single day, both edges backed by real timestamps | High — use these |
| `ESTIMATED` | Multi-day; outer edges anchored, middle days from the schedule | Directional; check `Cov%` |
| `SCHEDULED` | Timestamps unusable (stale start, late closeout). "Actual" is just the schedule | No information |
| `UNMEASURABLE` | No per-day record at all | None |

`Cov%` is the share of day boundaries backed by a real timestamp. A single-day job
is 100%; a ten-day job can only ever reach 10%, so low coverage on a long job is
structural, not a data problem.

### Two traps worth knowing

**1. `MEASURED` skews small.** Single-day jobs are small jobs. In one year of
data, jobs quoted under 4h were 61 measured / 9 estimated, while jobs over 50h
were **0 measured / 9 estimated**. A clean "quoting is accurate" result from the
MEASURED block is a statement about *short* jobs. Large jobs can only be
estimated — so judge them from `ESTIMATED` and read it as crew-time committed,
not stopwatch time.

**2. For `ESTIMATED` jobs, actual ≈ scheduled by construction.** Middle days come
from the calendar, so a combined MEASURED+ESTIMATED overrun figure partly measures
calendar blocking rather than worked time. The tool prints this caveat inline.
Judge quote accuracy from the MEASURED-ONLY block.

### What good data looks like

The model leans on your techs' start/complete timestamps. Where they're reliable,
you get real measurement. The failure modes it detects and names:

- **closeout drift** — job closed hours or days after leaving site
- **stale start** — job started long before the appointment
- **late start** — started well after the scheduled time
- **appointments incomplete** — quoted hours exceed booked calendar time by >2x

`hcp_time_variance` lists these by reason as a work list. Fix the timestamps and
those jobs become measurable.

---

## What to ask Claude

Plain language works — you don't need tool names.

**Before the week**
```
Show me next week's schedule with capacity by day.
What's in the backlog that should be scheduled first?
Show me the pipeline board.
Give me a four-week view — where are we overbooked?
```

**After the week**
```
Run a time variance for last week.
How did we do on quoted vs actual hours this month?
Full analysis on job 4821.
Which jobs ran furthest over quote this quarter?
```

**Data quality**
```
Which completed jobs have no usable actual time, and why?
Show me jobs where the appointments don't cover the quoted hours.
```

**Estimating**
```
Pull up the estimating brief for estimate 1116.
What labor rates and standard hours are in my price book?
```

---

## Tool reference

**43 tools** on the main server (`housecallpro_LHSTL.py`), formatted for reading.

### Analysis
| Tool | Purpose |
|---|---|
| `hcp_time_variance` | Quoted vs scheduled vs actual across a date range, graded, with split-project rollup and a data-quality work list |
| `hcp_post_job_analysis` | One job end to end: hours by day, revenue, labor and material cost, margin, payment speed |
| `hcp_check_setup` | Validate key, config, and whether configured IDs exist in this account |

### Scheduling and capacity
`hcp_get_week_schedule` · `hcp_multi_week_view` · `hcp_job_backlog` ·
`hcp_get_routes` · `hcp_list_events` · `hcp_create_appointment` ·
`hcp_update_appointment` · `hcp_delete_appointment`

### Jobs
`hcp_list_jobs` · `hcp_get_job` · `hcp_get_job_line_items` ·
`hcp_get_job_appointments` · `hcp_get_job_invoice` ·
`hcp_get_job_input_materials` · `hcp_add_job_note` · `hcp_add_job_tag` ·
`hcp_remove_job_tag`

### Estimates
`hcp_list_estimates` · `hcp_get_estimate` · `hcp_get_estimate_brief` ·
`hcp_write_estimate` · `hcp_get_estimate_line_items` ·
`hcp_update_estimate_line_items` · `hcp_add_estimate_note` ·
`hcp_finalize_estimate` · `hcp_approve_estimate_option` ·
`hcp_upload_estimate_pdf`

### Pipeline
`hcp_pipeline_board` · `hcp_get_pipeline_statuses` · `hcp_set_pipeline_status`

### Customers, invoices, reference
`hcp_list_customers` · `hcp_get_customer` · `hcp_create_customer` ·
`hcp_list_invoices` · `hcp_get_invoice` · `hcp_list_employees` ·
`hcp_list_tags` · `hcp_create_tag` · `hcp_update_tag` · `hcp_list_lead_sources`

### Optional: raw passthrough servers

The 20 `housecallpro_<domain>.py` files are thin wrappers returning raw JSON
(`housecallpro_jobs.py`, `_estimates.py`, `_leads.py`, `_webhooks.py`, …). Most
people never need them — the main server covers normal use with readable output.
Register one only when you want unformatted API access to a specific area, by
adding another `mcpServers` entry pointing at that file.

---

## Configuration

`config.json` is generated by the wizard and gitignored. `config.example.json` is
the annotated template.

Settings worth revisiting:

| Key | Why it matters |
|---|---|
| `scheduling.blended_cost_per_tech_hour` | Drives every margin number. Use your fully-loaded cost — wages, burden, vehicle, insurance, overhead. |
| `scheduling.productive_hours_per_day` | Real working capacity per tech (e.g. 8.0). |
| `scheduling.appointment_window_hours` | The window you block on the calendar (e.g. 8.5). |
| `team[].field_tech` | Only field techs count toward capacity. Exclude owners and office staff. |
| `team[].capacity_multiplier` | `0.5` for apprentices — still bookable a full day, but counted half. |

The gap between `appointment_window_hours` and `productive_hours_per_day` **is**
the unpaid break the model deducts from full days. Set both to match how you
actually book.

Optional tuning keys (`anchor_tolerance_hours`, `cluster_gap_days`, …) are
documented inline in `config.example.json`. Defaults are sensible.

**After you add or remove a tech**, re-run the wizard or edit `team` by hand, then
run `hcp_check_setup`.

You can point at a config elsewhere with the `HCP_CONFIG_PATH` environment
variable.

---

## Troubleshooting

**Tools don't appear in Claude**
Quit Claude Desktop completely (Cmd+Q) and reopen. Then check the config file is
valid JSON — a stray comma silently disables every server. Paths must be absolute.

**"HTTP 401" or "403"**
Key is wrong, revoked, or the account isn't on MAX. Recopy from Settings →
Integrations → API.

**"HTTP 429" / a run reports fewer jobs than expected**
Rate limiting. The tools retry behind a shared backoff and then **name** any job
they had to exclude — they never quietly report zero. Wait a minute and re-run.
If you script against this API yourself, do the same: treating a failed fetch as
an empty payload turns into "0 quoted hours" that looks like real data.

**Capacity or pipeline tools return nothing**
Almost always config. Run `hcp_check_setup` — it will tell you whether the config
is missing, has no field techs, or holds IDs from another account.

**Numbers look wrong on a specific job**
Run `hcp_post_job_analysis` on it and read the `Confidence` line and the day
breakdown. `SCHEDULED` grade means the timestamps weren't usable and you're
looking at the calendar, not measured work.

**`uv: command not found`**
Reopen your terminal after installing `uv`, or use the full path
(`~/.local/bin/uv`).

---

## Security

- Your API key lives in the Claude Desktop config, which is gitignored here.
- `config.json` holds no secrets, but it does hold employee names and your
  account's IDs — it's gitignored, and it should not be shared between accounts.
- Nothing leaves your machine except calls to `api.housecallpro.com`.
- **This is not read-only.** The server can create and modify customers,
  estimates, jobs, appointments, tags, notes, and invoices. Claude asks before
  write actions, but review those prompts rather than approving reflexively.
- No bulk-delete or bulk-lock tool is included, deliberately: those are hard to
  undo through a chat interface.

---

## For franchise partners

Everything account-specific is discovered by the wizard, so the normal path is:
clone, run the wizard, paste the config block, restart, run `hcp_check_setup`.

Three things are genuinely yours to decide:

1. **Your cost per tech-hour.** The default is a placeholder. Margin math is
   only as good as this number.
2. **Your day model.** `productive_hours_per_day` and `appointment_window_hours`
   should match how you actually book.
3. **Your tag convention** (optional). `config.example.json` ships one
   franchise's `CREW-` / `SCH-` / `JOB-` / `MAT-` / `TOOL-` system. Adopt it,
   change it, or delete the `tags` block — the tools degrade gracefully and just
   flag jobs as untagged.

The filenames still say `LHSTL` (`housecallpro_LHSTL.py`) for continuity with
existing installs. Renaming works if you also update the path in your Claude
Desktop config.

**A note on interpreting results.** The most useful early finding in one
franchise's data was not underquoting — quoted and actual hours matched to within
1% on measured jobs. It was that **40% more calendar time was blocked than the
work needed**, and separately that sub-4-hour jobs consistently ran ~35% over
quote while mid-size jobs were quoted well. Your numbers will differ. Start with
`hcp_time_variance` over a month you remember well, and check the MEASURED block
against your own sense of what happened before trusting the wider totals.
