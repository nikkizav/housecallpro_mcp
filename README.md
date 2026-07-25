# Housecall Pro + Claude Desktop — MCP Server

Connect Claude Desktop to your Housecall Pro account so you can ask questions, analyze your schedule, track finances, and manage jobs in plain English — no spreadsheet exports, no digging through menus.

This server was built for handyman and home services companies running on Housecall Pro. Each franchise owner installs it on their own machine with their own API key — you each connect to your own HCP account independently.

---

## What can it do?

**Ask Claude things like:**
> *"Show me the full schedule for next week with projected hours per tech"*
> *"Which jobs are outstanding and haven't been invoiced yet?"*
> *"Show me all jobs that came in from Google Ads this year"*
> *"Add the SCH-FOLLOWUP tag to Job #274"*
> *"Which jobs are missing crew tags?"*
> *"What's our total revenue for April vs March?"*

Claude understands natural language — no special commands required.

---

## Before you start — what you need

1. **Claude Desktop** (the app, not the website) — download free at [claude.ai/download](https://claude.ai/download)
2. **A Housecall Pro account on the MAX plan** — the API is only available on MAX
3. **Your computer** — Mac or Windows, instructions below cover both

---

## Part 1 — Get your Housecall Pro API key

Every franchise owner does this step with **their own HCP login**. Your API key connects Claude to *your* account only.

1. Log in to Housecall Pro at [app.housecallpro.com](https://app.housecallpro.com)
2. Click your name/avatar → **Settings** → **Integrations** → **API**
3. Copy your API key and save it temporarily (Notepad/TextEdit)

> If you don't see the API option, your account may not be on MAX plan. Contact Housecall Pro support to confirm.

---

## Part 2 — Download the server files

Download the `housecallpro_mcp` folder from wherever it was shared with you.

Place it somewhere **permanent** — don't move it after setup:
- **Mac:** `/Users/YOUR_NAME/Documents/housecallpro_mcp`
- **Windows:** `C:\Users\YOUR_NAME\Documents\housecallpro_mcp`

---

## Part 3 — Install uv

`uv` is a free tool that runs the Python server. Install it once and it handles everything else automatically.

**Mac:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Close and reopen Terminal, then verify: `~/.local/bin/uv --version`

**Windows** (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
Close and reopen PowerShell, then verify: `uv --version`

---

## Part 4 — Configure Claude Desktop

Find the config file:
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
  *(Finder → Cmd+Shift+G → paste that path)*
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
  *(Windows+R → paste that path)*

Replace the contents with the appropriate block below, substituting **YOUR_NAME** and your API key:

**Mac:**
```json
{
  "mcpServers": {
    "housecallpro": {
      "command": "/Users/YOUR_NAME/.local/bin/uv",
      "args": [
        "run",
        "--project",
        "/Users/YOUR_NAME/Documents/housecallpro_mcp",
        "python",
        "/Users/YOUR_NAME/Documents/housecallpro_mcp/server.py"
      ],
      "env": {
        "HCP_API_KEY": "PASTE_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "housecallpro": {
      "command": "C:\\Users\\YOUR_NAME\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--project",
        "C:\\Users\\YOUR_NAME\\Documents\\housecallpro_mcp",
        "python",
        "C:\\Users\\YOUR_NAME\\Documents\\housecallpro_mcp\\server.py"
      ],
      "env": {
        "HCP_API_KEY": "PASTE_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

> **Don't know your username?** Run `whoami` in Terminal (Mac) or PowerShell (Windows).

> **Config file already has content?** Add only the `"mcpServers"` block inside the existing `{}` — don't replace the whole file. Paste your config into [jsonlint.com](https://jsonlint.com) to catch formatting errors.

---

## Part 5 — Restart Claude Desktop

Fully quit Claude (Cmd+Q on Mac, or right-click tray icon → Quit on Windows) and relaunch.

> Simply closing the window is **not enough** — you must fully quit and relaunch.

**First launch takes 20–40 seconds** while it downloads Python and installs packages. After that it starts instantly.

---

## Part 6 — Verify it's working

1. Open a new chat in Claude Desktop
2. Look for a **tools icon** (hammer) in the chat input area — click it and you should see the `hcp_*` tools listed
3. Type: **"List my Housecall Pro employees"**

You should see your real team returned from your HCP account.

---

## Part 7 — First time setup: Tell Claude about your business

When you start your first session, paste this to give Claude context about your operation:

```
I run a handyman / home services company on Housecall Pro. Here's what you should know:

Team: [list your techs and any notes — e.g. who is lead vs apprentice]
Work week: [e.g. Monday–Friday, typical start time]
Job volume: [e.g. roughly X jobs per week]
Average job size: [e.g. $500–$5,000, multi-day projects common]

Tag system we use:
- CREW-* = crew size/composition (CREW-1L, CREW-2L1A, CREW-TBD, etc.)
- SCH-* = scheduling urgency (SCH-URGENT, SCH-1W through SCH-4W, SCH-FLEX, SCH-MAT, SCH-FOLLOWUP)
- JOB-* = location type (JOB-IN, JOB-OUT, JOB-INOUT)
- MAT-* = material sourcing (MAT-HD, MAT-LO, MAT-SO, etc.)
- TOOL-* = special tool needs (TOOL-SCAFF, TOOL-LIFT, TOOL-BRAKE, etc.)
- SCH-FOLLOWUP = job needs a return call before scheduling

My two main weekly workflows are:
1. Pre-week planning (Sunday/Monday morning): Who's working what, projected hours, gaps
2. Post-week financial review (Friday afternoon): Revenue collected, outstanding invoices, actual vs projected hours

What would you like to tackle first?
```

Claude will ask clarifying questions and help you get started right away.

---

## Suggested first prompts by workflow

### 📅 Pre-week scheduling

```
Show me the full schedule for the week of [date]. Include:
- Who is dispatched to each job each day
- Projected hours per job
- Whether each job is on track to finish this week
- Any gaps or unassigned time
```

```
List all jobs with status 'scheduled' or 'in progress'. 
For each one show projected hours remaining and who's assigned.
```

```
Which jobs have the SCH-FOLLOWUP tag? I need to call those customers.
```

```
Are there any jobs this week that are missing crew tags or scheduling tags?
```

### 💰 Post-week financial review

```
Show all invoices from this week. What's the total billed, total collected, 
and what's still outstanding?
```

```
Which completed jobs from this week still have outstanding balances?
List the customer, job number, amount due, and job value.
```

```
Compare projected hours to actual elapsed time for jobs completed this week.
Flag anything where actual was significantly more than projected.
```

```
What were our top 5 jobs by revenue this month?
```

### 🔍 Customer & lead source analysis

```
Show me all customers who came from [lead source name].
How many jobs did they generate and what's the total revenue?
```

```
Search for customer [name or phone number].
Show their full job history and any outstanding balances.
```

```
Which jobs this year are missing a lead source? 
I need to reconcile those for our marketing analysis.
```

### 📆 Scheduling (read & write)

```
Show me the full schedule for Monday April 28th.
```

```
Add a new appointment to Job #[number] for Wednesday May 6th, 
7:30 AM to 4:00 PM, dispatched to [tech name].
```

```
Move Job #[number]'s Thursday appointment to Friday — same time, same crew.
```

```
Job #[number] wrapped up early. Delete the remaining appointment for Friday.
```

### 🏷️ Tag management

```
Pull my full tag list and show me all jobs that are tagged SCH-FOLLOWUP.
```

```
Add the SCH-FOLLOWUP tag to Job #[number].
```

```
Show me all scheduled jobs that are missing a CREW tag.
```

```
Create a new tag called SCH-FOLLOWUP.
```
*(Do this step when you first set up — see the tag checklist below)*

### 🧾 Estimates & pipeline

```
Show me all open estimates from the last 30 days. 
Which ones haven't been converted to jobs yet?
```

```
Pull the estimate for [customer name] and summarize the scope and pricing.
```

---

## Available tools

### Customers
| Tool | What it does |
|------|-------------|
| `hcp_list_customers` | Search/list customers |
| `hcp_get_customer` | Full customer detail |
| `hcp_create_customer` | Create a new customer |

### Jobs
| Tool | What it does |
|------|-------------|
| `hcp_list_jobs` | List jobs with filters (status, date, employee) |
| `hcp_get_job` | Full job detail |
| `hcp_get_job_line_items` | Services & materials, projected hours |
| `hcp_get_job_invoice` | Invoice with line items and payment status |
| `hcp_get_job_input_materials` | Materials logged on a job |
| `hcp_add_job_note` | Add a note to a job |

### Scheduling
| Tool | What it does |
|------|-------------|
| `hcp_get_routes` | **Every tech's full day** — all appointments, events, estimates by employee for a given date. Fastest schedule view. |
| `hcp_get_job_appointments` | All appointment windows for a job, with dispatched techs per appointment |
| `hcp_create_appointment` | Add a new appointment day to a job, assign techs |
| `hcp_update_appointment` | Change date, time, or crew on an existing appointment |
| `hcp_delete_appointment` | Remove an appointment from a job |
| `hcp_list_events` | Non-job calendar events (time off, meetings, etc.) |

### Invoices & Estimates
| Tool | What it does |
|------|-------------|
| `hcp_list_invoices` | List invoices with rich filters |
| `hcp_get_invoice` | Full invoice detail by UUID |
| `hcp_list_estimates` | List estimates |
| `hcp_get_estimate` | Single estimate detail |

### Team & Configuration
| Tool | What it does |
|------|-------------|
| `hcp_list_employees` | List all active employees with IDs |
| `hcp_list_lead_sources` | All configured lead sources |
| `hcp_list_tags` | All tags, grouped by prefix |
| `hcp_create_tag` | Create a new tag |
| `hcp_update_tag` | Rename an existing tag |
| `hcp_add_job_tag` | Add a tag to a job |
| `hcp_remove_job_tag` | Remove a tag from a job |

---

## Tag system setup checklist

When you first set up this integration, run through this checklist to make sure your tags are ready:

```
Pull my full tag list and tell me which of these standard tags are missing:

CREW: CREW-TBD, CREW-1L, CREW-2L, CREW-3L, CREW-4L, 
      CREW-1L1A, CREW-2L1A, CREW-3L1A, CREW-1L2A, CREW-2L2A

SCH: SCH-URGENT, SCH-FLEX, SCH-1W, SCH-2W, SCH-3W, SCH-4W, 
     SCH-TBD, SCH-MAT, SCH-FOLLOWUP

JOB: JOB-IN, JOB-OUT, JOB-INOUT

MAT: MAT-SO, MAT-HD, MAT-LO, MAT-ME, MAT-SW, MAT-LLT

TOOL: TOOL-BRAKE, TOOL-SCAFF, TOOL-CMIX, TOOL-LIFT, TOOL-EXL, TOOL-OTHER

Create any that are missing.
```

> **Note for franchise owners:** Your tag values may differ from the list above. Update the checklist to match your own naming conventions before running it.

---

## Tag dictionary (Local Handyman standard)

Customize this section for your franchise's tag conventions.

### CREW-* — Staffing
| Tag | Meaning |
|-----|---------|
| CREW-1L | 1 lead tech |
| CREW-2L | 2 lead techs |
| CREW-1L1A | 1 lead + 1 apprentice |
| CREW-2L1A | 2 leads + 1 apprentice |
| CREW-TBD | Crew not yet determined |
| CREW-[Name] | Specific tech assigned |

### SCH-* — Scheduling urgency
| Tag | Meaning |
|-----|---------|
| SCH-URGENT | Schedule ASAP |
| SCH-FLEX | Flexible timing |
| SCH-1W through SCH-4W | Schedule within 1–4 weeks |
| SCH-TBD | Scheduling pending decision |
| SCH-MAT | Waiting on materials before scheduling |
| SCH-FOLLOWUP | Needs a return call from office before scheduling |

### JOB-* — Work location
| Tag | Meaning |
|-----|---------|
| JOB-IN | Interior work only |
| JOB-OUT | Exterior work only |
| JOB-INOUT | Both interior and exterior |
| JOB-RT-FEE | Return trip fee applies |

### MAT-* — Material sourcing
| Tag | Meaning |
|-----|---------|
| MAT-SO | Special order required |
| MAT-HD | Home Depot |
| MAT-LO | Lowes |
| MAT-ME | Menards |
| MAT-SW | Sherwin Williams |
| MAT-LLT | Long lead time |

### TOOL-* — Special equipment needed
| Tag | Meaning |
|-----|---------|
| TOOL-BRAKE | Sheet metal brake |
| TOOL-SCAFF | Scaffolding |
| TOOL-CMIX | Concrete mixer |
| TOOL-LIFT | Boom/scissor lift |
| TOOL-EXL | Extension ladder (tall) |
| TOOL-OTHER | Other specialty tool |

---

## Using this with Cowork

Everything this server can do in Claude Desktop works identically in **Cowork** — the same 26 tools, the same live HCP data.

Where Cowork becomes more powerful is when you combine live HCP data with data from your other platforms. In a Cowork session you can:

- Ask questions that pull live data from HCP via these tools
- Upload reports or exports from Google Ads, QuickBooks, or any other platform
- Have Claude analyze everything together in a single conversation

**Example workflow — full business review:**
1. Open a Cowork session
2. Say: *"Pull all completed jobs from last week with revenue and lead source"* — Claude pulls live from HCP
3. Drag in your Google Ads CSV export for the same week
4. Drag in a QuickBooks P&L or expense report
5. Ask: *"Calculate our customer acquisition cost by lead source, net margin per job, and compare actual labor cost to what we projected"*

Claude holds all of it in context simultaneously and reasons across all the data sources.

### What to pull from each platform

| Platform | What to export | What it enables |
|----------|---------------|-----------------|
| **Housecall Pro** | Live via MCP — no export needed | Jobs, revenue, hours, customers, schedule |
| **Google Ads** | Campaign performance report (CSV) | Spend by campaign, clicks, conversions |
| **Google Local Services** | Leads report | Cost per lead, lead volume by week |
| **QuickBooks** | P&L report, payroll summary, expenses by vendor | Labor cost, materials cost, overhead, true margins |
| **Angi / Yelp / Thumbtack** | Leads or spend report | CAC by platform |
| **Any other platform** | CSV or Excel export | Claude can read any tabular format |

### Key analyses you can run

**Customer Acquisition Cost (CAC) by lead source:**
```
Here's my Google Ads spend for April [attach CSV] and my Google Local Services report [attach].
Pull all April jobs from HCP with their lead sources.
Calculate CAC per lead source: total ad spend ÷ number of new customers acquired per channel.
```

**True job margin:**
```
Here's my QuickBooks payroll summary for the week [attach].
Pull all completed jobs from this week with projected hours and revenue.
Calculate: revenue − materials cost − labor cost (hours × burdened rate) = gross margin per job.
Flag any job where margin is under 40%.
```

**Tech productivity:**
```
Pull all completed jobs this month. For each tech, show:
- Total hours dispatched
- Total revenue on jobs they worked
- Revenue per hour
- Jobs completed
```

**Weekly P&L in 5 minutes:**
```
Pull this week's completed jobs, invoices sent, and collections.
Here's this week's QuickBooks expense summary [attach].
Give me: revenue collected, revenue invoiced, outstanding AR, estimated gross margin.
```

---

**Projected hours** — The `quantity` field on labor line items is the projected hours for that scope. Use this for scheduling and estimating how long jobs will take.

**Appointment-level scheduling** — `hcp_get_job_appointments` shows who is *dispatched* to each specific appointment, not just who is assigned to the job overall. Use this for accurate weekly schedule analysis.

**Dollar amounts** — All amounts are displayed in dollars. The API stores them in cents internally, but the server converts them automatically.

**Job date filters** — The `scheduled_start_min/max` filters on `hcp_list_jobs` match the job's *primary* start date. For ongoing multi-week jobs, use a wide date range and then pull appointments to see which ones have work this specific week.

**Work status values** — `unscheduled`, `scheduled`, `in_progress`, `completed`, `canceled`, `user_canceled`, `pro_canceled`

---

## Troubleshooting

**Tools icon not showing in Claude Desktop**
- Fully quit and relaunch Claude (Cmd+Q on Mac, tray icon → Quit on Windows)
- Check your config file for JSON errors at [jsonlint.com](https://jsonlint.com)
- Verify your username is correct in all path locations
- Mac: run `~/.local/bin/uv --version` in Terminal to confirm uv is installed

**Getting API errors**
- Confirm your API key is correct — re-copy it from HCP Settings → Integrations → API
- Confirm your HCP account is on the MAX plan

**Windows path issues**
- Run `(Get-Command uv).Source` in PowerShell to get the exact path to uv

---

## Security reminders

- Your API key gives access to your Housecall Pro account — treat it like a password
- **Do not share your `claude_desktop_config.json`** — it contains your API key
- Each franchise owner uses **their own API key** — never share keys across accounts
- If your key is exposed, regenerate it from HCP Settings → Integrations → API
