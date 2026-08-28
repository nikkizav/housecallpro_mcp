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
- [The permission pop-ups](#the-permission-pop-ups) — Deny / Allow once / Allow for this task
- [Set up a Project](#set-up-a-project-so-you-dont-repeat-yourself)
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
| **Housecall Pro API access** | Comes with the MAX plan. Local Handyman owners are all on MAX, so there's nothing to check. Outside that network: open **My Apps → Go to App Store** and search for **API**. If there's no **API Key Management** tile, you're on a lower plan and this won't work yet. |
| **Claude desktop app** | Free to download at [claude.ai/download](https://claude.ai/download). **Install it and open it once before you start** — Claude creates the settings folder you'll need in Step 5 the first time it runs. Sign in with your Claude account. |
| **About 15 minutes** | Mostly waiting on downloads. |

You do **not** need to know how to program. You'll copy and paste a few commands
into a black window. If that sounds intimidating, it's genuinely just copy, paste,
press Enter.

---

## Setup

### Step 1 — Get your Housecall Pro key

In Housecall Pro:

1. On the top bar, click the **My Apps** tile — the icon made of nine small
   squares, sitting next to Settings
2. Click the **Go to App Store** button
3. Search for **API**
4. Open the **API Key Management** tile
5. Click the **Generate a new API key** tile, and name it something you'll
   recognise later — `Claude` works
6. Copy the key it gives you

This key is how your computer proves it's allowed to read your account. **Treat it
like your password.** Don't email it or paste it into a group chat. Later steps
put it in a settings file on your own machine and nowhere else.

> Copy the key now if it's shown to you. Most systems only display a new key once,
> and if you lose it you just generate another.

### Step 2 — Open the command window

This is a window where you type commands instead of clicking. Each system has its
own name for it:

- **Mac** — press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows** — press the `Windows` key, type `PowerShell`, press Enter.

**There will already be some text in the window. That's normal.** Windows shows a
couple of lines about Microsoft, and Mac may show when you last logged in. Below
it is a line ending in `>` (Windows) or `%` (Mac) — that's the prompt, and it's
where what you type appears. Windows looks roughly like this:

```
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

PS C:\Users\yourname>
```

Ignore the existing text. You just type after the prompt and press Enter.

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
**Download ZIP**. Unzip it, and move the resulting folder somewhere you'll find
again — your Documents folder is fine.

**Two things that trip people up here:**

The folder will be named something like `housecallpro_mcp-main`. Renaming it to
something short — `HCP_MCP` works well — makes the next command much easier to
type. Do that now if you like.

Unzipping often creates **a folder inside a folder**, both with the same name. You
need the *inner* one — the folder that directly contains `setup_wizard.py` and
`README.md`. Open it and look; if all you see is another folder with the same
name, go one level deeper.

Now point Terminal at that folder. Type `cd ` — the letters c, d, then a space —
then drag **that** folder (the one holding the files) into the Terminal window.
Dragging pastes its location for you, so you never type it out. Press Enter.

- **Mac** — drag the folder from **Finder**
- **Windows** — drag the folder from **File Explorer**

If dragging doesn't paste anything, type `cd ` and then the full folder location by
hand (on Windows it starts with `C:\`).

**Check you're in the right place** before going on. Type this and press Enter:

- **Mac** — `ls`
- **Windows** — `dir`

You should see `setup_wizard.py` and `README.md` in the list. If instead you see a
single folder name, you're one level too high — run `cd ` followed by that folder
name, and check again.

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

**First: install the Claude desktop app and open it at least once.** The settings
folder doesn't exist until Claude has run once and created it. Get it from
[claude.ai/download](https://claude.ai/download), open it, sign in.

### The easy way — let the wizard do it

At the end of Step 4 the wizard asks:

```
Found Claude Desktop's settings folder:
  /path/to/Claude
Write the connection into it for you? (Y/n)
```

**Say yes.** It finds the settings file wherever your version of Claude keeps it,
backs up what's there, adds the connection with your API key already filled in,
and leaves any other tools you've connected untouched.

If it says *"Setup complete"*, you're done here — skip to
[Did it work?](#did-it-work) and restart Claude.

If it couldn't find Claude Desktop, it says so and lists where it looked. Install
Claude, open it once, then re-run `uv run python setup_wizard.py` — it'll finish
the job.

### The manual way

Only needed if you declined above, or the wizard couldn't write the file.

Open `claude_desktop_config.json` in this folder:

- **Mac** — in Finder press `Cmd + Shift + G`, paste
  `~/Library/Application Support/Claude/`, press Enter. Edit in TextEdit.
- **Windows** — there are **two possible locations**, depending on how Claude was
  installed. Press `Win + R` and try each:
  - `%APPDATA%\Claude` — if you installed the `.exe` from the website
  - `%LOCALAPPDATA%\Packages` — if you installed from the **Microsoft Store**.
    Inside, open the folder starting `Claude_…`, then
    `LocalCache\Roaming\Claude`. The full path looks like
    `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude`,
    where those random-looking letters differ on every machine.

  If `%APPDATA%\Claude` gives you *"Windows cannot find…"*, you have the Store
  version — use the second path. Edit in Notepad.

The block the wizard printed **already has your API key in it** — there's nothing
to find and replace. Copy the whole thing.

**If the file is empty or missing,** paste the block in as-is and save.

**If the file already has content,** don't replace it — you'd disconnect your other
tools. You're adding the `"housecallpro"` entry *inside* the existing
`"mcpServers"` object. Like this:

```json
{
  "mcpServers": {
    "some-other-tool": { "command": "..." },

    "housecallpro": {
      "command": "uv",
      "args": ["run", "--project", "/your/path", "python", "/your/path/housecallpro_LHSTL.py"],
      "env": { "HOUSECALL_PRO_API_KEY": "your-key-is-already-here" }
    }
  }
}
```

Note the comma after the previous entry's `}`, and that there's only ever **one**
`"mcpServers"`. If you're unsure, paste the whole file to Claude and ask it to
merge the block in for you — it'll hand back the corrected file.

> **Windows: saving the file.** In Notepad use **File → Save As**, set *Save as
> type* to **All Files**, and name it exactly `claude_desktop_config.json`. Left as
> *Text Documents*, Notepad silently saves `claude_desktop_config.json.txt` and
> Claude will never read it. On Mac, choose **Format → Make Plain Text** first.

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

## The permission pop-ups

The first time Claude uses this connector it stops and asks, with three choices —
usually **Deny**, **Allow once**, and **Allow for this task**. This is Claude
checking with you before touching your business data. Here's how to think about it.

| Choice | What happens | When to pick it |
|---|---|---|
| **Allow for this task** | Stops asking for the rest of this piece of work | Almost always. This is the normal answer. |
| **Allow once** | Runs this one call, then asks again | You want to see each step, or you're not sure yet |
| **Deny** | Blocks it. Claude tells you what it couldn't do | Something looks wrong, or you didn't expect it |

**Why "Allow for this task" matters practically:** the analysis tools make a lot of
calls. A time variance over a month pulls details for every job in it — that can be
two hundred separate lookups. On **Allow once** you'll be clicking approve until
you give up. Pick **Allow for this task** and it runs.

### Reading the prompt

The pop-up names the tool it wants to run, and the name tells you what it does:

- **`hcp_list_…`, `hcp_get_…`, `hcp_time_variance`, `hcp_post_job_analysis`** —
  these only look things up. 28 of the 45 tools are read-only. Nothing you approve
  here can change anything.
- **`hcp_create_…`, `hcp_update_…`, `hcp_delete_…`, `hcp_add_…`, `hcp_remove_…`,
  `hcp_set_…`, `hcp_write_estimate`, `hcp_finalize_estimate`,
  `hcp_approve_estimate_option`** — these **change your Housecall Pro data**. There
  are 17 of them. Read what it says before allowing.

If you asked a question and it wants to *change* something, that's worth a second
look — say Deny and ask what it's trying to do.

Denying never breaks anything. It just stops that one action.

---

## Set up a Project so you don't repeat yourself

**First, a clarification:** `hcp_check_setup` is a **one-time check**. You run it
once after installing to confirm everything's wired up. You do *not* run it at the
start of every conversation. Only come back to it if results look empty or wrong.

The connection itself is set up once, at the app level. It's available in every
chat from then on — nothing to reconnect.

What *doesn't* carry between chats is **context about your business** — your team,
how you quote, what you care about. A **Project** fixes that.

### Creating one

In Claude, go to **Projects → New project** (in Cowork, the Projects section in the
left sidebar). Name it something like *Housecall Pro*.

Then add **project instructions** — this is the part that saves you time. Something
like:

```
I run [your company], a home services business in [your city].
We have [N] field techs and [N] apprentice(s).
Our fully loaded cost is $[X] per tech-hour.
We book [8.5]-hour days on the calendar.

You have a connection to our Housecall Pro account. Use it to answer
questions about our jobs, schedule, estimates and invoices.

When you report hours, always tell me the confidence grade and judge
quote accuracy from the MEASURED jobs only.

Check numbers before presenting them. Tell me when you're not sure.
```

Now every chat in that Project starts knowing who you are. You ask "how did last
week go?" instead of re-explaining your company first.

You can also drop the `WHY_THIS_HELPS.md` and `README.md` files into the Project so
Claude knows how the tool works and what its limits are.

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

**"Windows cannot find 'C:\Users\...\AppData\Roaming\Claude'"**
Two possible causes, and the first is more likely:

1. **You installed Claude from the Microsoft Store.** Store apps are sandboxed, so
   that path is redirected. Go to `%LOCALAPPDATA%\Packages`, open the folder
   starting `Claude_…`, then `LocalCache\Roaming\Claude`.
2. **Claude has never been opened.** The folder is created on first run. Install
   it, open it, sign in.

Easiest fix either way: re-run `uv run python setup_wizard.py` and let it write the
file — it checks both locations for you.

**I saved the settings file but Claude still doesn't see the tools (Windows)**
Check the filename. In File Explorer turn on **View → File name extensions**. If
it reads `claude_desktop_config.json.txt`, Notepad added the `.txt` — rename it to
remove that, then fully quit and reopen Claude.

**`cd` says "cannot find the path" or the setup script isn't found**
You're probably one folder too high. Unzipping usually makes a folder inside a
folder. Run `dir` (Windows) or `ls` (Mac): you should see `setup_wizard.py`. If you
only see another folder name, `cd` into it and try again.

**Claude doesn't seem to know about my jobs**
Quit Claude completely and reopen — `Cmd + Q` on Mac, or right-click the tray icon
→ Quit on Windows. Closing the window doesn't do it. If there's still nothing, the
settings file probably has a typo; one misplaced comma disables everything. Paste
the file to Claude and ask it to check.

**"HTTP 401" or "403"**
Your key is wrong, was deleted, or your plan doesn't include API access. Generate a
fresh one: **My Apps → Go to App Store → search "API" → API Key Management →
Generate a new API key**, then update it in the Claude settings file from Step 5.

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

**Architecture.** `housecallpro_LHSTL.py` is the main server: 45 tools returning
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
