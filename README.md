# Housecall Pro + Claude

**Ask questions about your jobs in plain English and get real answers from your
own Housecall Pro data.**

```
You:  How did last week's jobs compare to what we quoted?
You:  Show me next week's schedule and where we're overbooked.
You:  Full breakdown on job 4821 — did we make money?
```

Never heard of an MCP or an API, and not sure what you're looking at?
**→ Start with [START_HERE.md](START_HERE.md)** (3 minutes, plain English).

Wondering whether this is worth your time?
**→ Read [WHY_THIS_HELPS.md](WHY_THIS_HELPS.md) first** (5 minutes, no technical
background needed).

---

## What this actually is

Claude is an AI assistant — you type questions, it answers. On its own, Claude
can't see your Housecall Pro account.

This is the connector that lets it. You install it once on your own computer, and
from then on Claude can read your jobs, schedule, estimates, and invoices when you
ask about them.

Three things worth knowing up front:

- **It runs on your computer.** Your data goes to Claude and to Housecall Pro,
  and nowhere else. No middleman service.
- **Your crew changes nothing.** They keep using Housecall Pro exactly as today.
- **It can make changes, not just read.** Scheduling an appointment is half the
  value. Claude asks first — read those prompts.

You'll see the term **MCP** in a few places (it's in some filenames). It's just
the name of the standard Claude uses to connect to outside tools. You never need
to think about it again.

---

## Contents

- [Before you start](#before-you-start)
- [Setup](#setup) — 15 minutes, five steps
- [Did it work?](#did-it-work)
- [What to ask](#what-to-ask)
- [Reading the numbers](#reading-the-numbers) ← **the important section**
- [When something goes wrong](#when-something-goes-wrong)
- [Settings you should review](#settings-you-should-review)
- [Safety](#safety)
- [For the technically curious](#for-the-technically-curious)

**Other pages:** [START_HERE.md](START_HERE.md) (what this is, in plain English) ·
[WHY_THIS_HELPS.md](WHY_THIS_HELPS.md) (why bother) ·
[FIRST_WEEK.md](FIRST_WEEK.md) (what to ask once it's running) ·
[FAQ.md](FAQ.md) (questions people actually ask)

---

## Before you start

| You need | Notes |
|---|---|
| **Housecall Pro API access** | Comes with the MAX plan. Local Handyman owners are all on MAX, so there's nothing to check. Outside that network: look under Settings → Integrations → API, and if there's no API section you're on a lower plan and this won't work yet. |
| **Claude desktop app** | Free to download at [claude.ai/download](https://claude.ai/download). Sign in with your Claude account. |
| **About 15 minutes** | Mostly waiting on downloads. |

You do **not** need to know how to program. You'll copy and paste a few commands
into a black window. If that sounds intimidating, it's genuinely just copy, paste,
press Enter.

---

## Setup

### Step 1 — Get your Housecall Pro key

In Housecall Pro: **Settings → Integrations → API → create a key**, then copy it.

This key is how your computer proves it's allowed to read your account. **Treat it
like your password.** Don't email it or paste it into a group chat. Later steps
put it in a settings file on your own machine and nowhere else.

### Step 2 — Open the command window

This is a window where you type commands instead of clicking. Each system has its
own name for it:

- **Mac** — press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows** — press the `Windows` key, type `PowerShell`, press Enter.

A window with a blinking cursor opens. That's all it is.

> From here on this guide says **"Terminal"** to mean *Terminal on Mac,
> PowerShell on Windows*. Everything else is the same on both.

### Step 3 — Install the helper tool

This installs `uv`, which runs the connector and manages the technical pieces so
you don't have to. Copy this whole line, paste it into Terminal, press Enter:

**Mac**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Text will scroll by. When the cursor comes back, **close Terminal and open it
again** (this matters — it won't work otherwise). Then check it worked:

```bash
uv --version
```

If you see a version number, you're good. If you see "command not found," close
and reopen Terminal once more.

### Step 4 — Download and set up

Download this project: click the green **Code** button at the top of this page →
**Download ZIP**. Unzip it, and move the folder somewhere you'll find again — your
Documents folder is fine.

Now point Terminal at that folder. Type `cd ` — the letters c, d, then a space —
and then drag the folder itself into the Terminal window. That pastes its location
for you, so you never have to type it out. Press Enter.

- **Mac** — drag the folder from **Finder**
- **Windows** — drag the folder from **File Explorer**

If dragging doesn't paste anything, type `cd ` and then the full folder location by
hand (on Windows it starts with `C:\`).

Then run the setup:

```bash
uv run python setup_wizard.py
```

It will ask you a few questions:

- **Your API key** — paste the one from Step 1
- **Who your field techs are** — pick the numbers of the people who actually do
  the work. Leave out owners and office staff, or your capacity math will look
  better than reality.
- **Who's an apprentice** — they count as half a person for capacity, but can
  still be booked a full day
- **Your cost per tech-hour** — see [Settings](#settings-you-should-review) below;
  this one matters
- **Your normal workday** — how many productive hours, and how long a window you
  block on the calendar

When it finishes it prints a block of text starting with `{`. **Leave that window
open** — you need it next.

### Step 5 — Connect it to Claude

Open the Claude settings file:

- **Mac** — in Finder press `Cmd + Shift + G`, paste
  `~/Library/Application Support/Claude/`, press Enter. Open
  `claude_desktop_config.json` in TextEdit.
- **Windows** — press `Win + R`, type `%APPDATA%\Claude`, press Enter. Open
  `claude_desktop_config.json` in Notepad.

Paste in the block the setup wizard printed, and replace
`PASTE_YOUR_API_KEY_HERE` with your actual key. Save.

> If that file already has text in it, don't replace everything — you'd disconnect
> your other tools. Ask Claude for help merging it; paste both blocks and it'll
> show you the combined version.

Finally, **quit Claude completely and reopen it.** Closing the window is not
enough — Claude keeps running in the background, and it only picks up the new
settings on a full restart.

- **Mac** — press `Cmd + Q`, or Claude menu → Quit Claude
- **Windows** — find the Claude icon in the system tray (bottom-right, next to the
  clock; you may need to click the small `^` arrow to see hidden icons),
  right-click it, choose **Quit**

Then open Claude again.

---

## Did it work?

Ask Claude:

```
run hcp_check_setup
```

You should see:

```
╔══ SETUP CHECK ═══════════════════════════════════════════════
║  ✓ API key works — connected to: Your Company Name
║  ✓ Config found
║  ✓ Labor cost rate: $95.00/tech-hour
║  ✓ All 6 configured field-tech IDs exist in this account
║  ✓ 21 pipeline stages configured
╠══════════════════════════════════════════════════════════════
║  RESULT: ready to use ✓
```

If anything shows ✗, it tells you exactly what's wrong and what to do. Run it again
any time results look empty or wrong.

---

## What to ask

Talk to it normally — you don't need to memorize commands.

**Planning the week**
```
Show me next week's schedule with capacity by day.
What's in the backlog that should get scheduled first?
Where are we overbooked in the next four weeks?
```

**Reviewing the week**
```
Run a time variance for last week.
How did we do on quoted vs actual hours this month?
Which jobs ran furthest over quote this quarter?
Full analysis on job 4821.
```

**Finding data problems**
```
Which completed jobs have no usable actual time, and why?
Show me jobs where the appointments don't cover the quoted hours.
```

---

## Reading the numbers

**Please read this part.** It's the difference between using this well and drawing
a wrong conclusion confidently.

### Every number has a confidence grade

Housecall Pro records **one Start and one Finish per job** — not per tech, not per
visit, and it doesn't track lunch or breaks. Everything below follows from that.

| Grade | What it means | How much to trust it |
|---|---|---|
| **MEASURED** | One-day job. Start and finish both real. | Trust it. |
| **ESTIMATED** | Multi-day job. First and last day anchored to real timestamps, middle days filled in from your schedule. | Directional. Good for spotting problems, not for precision. |
| **SCHEDULED** | Timestamps unusable — tech closed out days later, or started the timer weeks early. "Actual" here is just your calendar. | No information. Ignore. |

Totals are reported separately so the good data never gets diluted by the weak
data.

### Two traps

**1. "Our quoting is accurate" usually means small jobs.**

MEASURED jobs are one-day jobs, and one-day jobs are small jobs. In one year of
real data, jobs quoted under 4 hours were 61 measured; jobs over 50 hours were
**zero** measured. So a clean result from the MEASURED block is a statement about
your small work. Your big jobs can only be estimated — read those as *crew time
committed*, not stopwatch time.

**2. For multi-day jobs, "actual" partly means "what you blocked."**

Middle days come from your calendar, so a combined total measures calendar
commitment as much as worked time. The tool prints this warning on screen. Judge
quote accuracy from the MEASURED-ONLY block.

### It tells you when your data is the problem

Jobs it can't measure get listed by name and reason:

- **closeout drift** — tech closed the job hours or days after leaving
- **stale start** — job started long before the appointment (often at the estimate)
- **late start** — started well after the scheduled time
- **appointments incomplete** — quoted hours far exceed the booked calendar time

That list is a coaching sheet. Fix the habits and those jobs become measurable next
quarter.

---

## When something goes wrong

**Claude doesn't seem to know about my jobs**
Quit Claude completely and reopen — `Cmd + Q` on Mac, or right-click the tray icon
→ Quit on Windows. Closing the window doesn't do it. If there's still nothing, the
settings file probably has a typo; one misplaced comma disables everything. Paste
the file to Claude and ask it to check.

**"HTTP 401" or "403"**
Your key is wrong, was deleted, or your plan doesn't include API access. Make a new one in
Settings → Integrations → API.

**"HTTP 429" or fewer jobs than expected**
Housecall Pro is limiting how fast we can ask. It retries automatically, and if it
still can't get a job it **names** the ones it skipped — it never silently reports
zero. Wait a minute and ask again.

**Capacity or schedule tools come back empty**
Almost always the setup. Run `hcp_check_setup`.

**One job's numbers look wrong**
Ask for a full analysis on it and read the **Confidence** line. `SCHEDULED` means
the timestamps weren't usable and you're looking at your calendar, not real work.

**"uv: command not found"** (Mac) or **"uv is not recognized..."** (Windows)
Close and reopen Terminal, then try again. The install only takes effect in a
window opened *afterwards*. If it still isn't found on Windows, restart the
computer once — that reliably fixes it.

---

## Settings you should review

The setup wizard fills these in, but two are worth a second look. They're in
`config.json` in the project folder, or just ask Claude to explain them.

**Your cost per tech-hour** — the single most important number here. It should be
your *fully loaded* cost: wages, payroll taxes, vehicle, insurance, overhead — not
just the hourly wage. Every profit and margin figure depends on it. The default of
$95 is a placeholder from another company.

**Your workday** — two numbers: productive hours (say 8.0) and the window you
block on the calendar (say 8.5). The difference between them is the unpaid break,
and it gets subtracted from full days automatically. Set both to match how you
actually book.

Added or lost a tech? Re-run the setup wizard, then `hcp_check_setup`.

---

## Safety

- Your Housecall Pro key lives in the Claude settings file on your computer. It is
  never uploaded here.
- Your data goes to Claude and to Housecall Pro. There is no other server involved.
- **This is not read-only.** It can create and change customers, estimates, jobs,
  appointments, tags, notes, and invoices. Claude asks before changes — actually
  read those prompts.
- There is deliberately no bulk-delete tool.
- If you share this project with someone, share the link — never your `config.json`
  or your API key. Their setup wizard builds their own.

---

## For the technically curious

Everything below is optional.

**Architecture.** `housecallpro_LHSTL.py` is the main server: 43 tools returning
formatted, readable output. The other 20 `housecallpro_<domain>.py` files are thin
wrappers returning raw JSON — register one in your Claude config only if you want
unformatted access to a specific area.

**How actual hours are computed.** Per day, not as one span:

```
day 1      real started_at   →  scheduled end
middle     scheduled window     (inference — no data exists)
last day   scheduled start   →  real completed_at
```

Each day is multiplied by the crew dispatched *that day*, less the break on days
of 6h or more. Measuring instead as one `started_at → completed_at` span is what
makes a two-week job read as 300 hours. Across 263 completed jobs, `started_at`
landed within 4h of the first appointment 90% of the time and `completed_at`
within tolerance 88% of the time — the anchors are sound, and the failures are
detected and named rather than averaged in.

**Config resolution.** `config.json` beside the server, then legacy names, then the
parent directory. `HCP_CONFIG_PATH` overrides everything. `config.example.json`
documents every key, including optional tuning (`anchor_tolerance_hours`,
`cluster_gap_days`).

**Rate limiting.** Bulk fan-out draws HTTP 429s. Requests are capped at 4
concurrent and retry behind a process-wide backoff gate; any job that still fails
is excluded *and named*. If you script against this API yourself, do the same —
treating a failed fetch as an empty payload silently turns into "0 quoted hours"
that looks like real data.

**Licence.** MIT — see [LICENSE](LICENSE). Not affiliated with Housecall Pro.
