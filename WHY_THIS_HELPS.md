# Why this is worth your time

*A short read for owners and managers. No technical background needed.*

---

## The problem

You quote a job at 6 hours. Your tech goes out. The job gets invoiced. Money
comes in.

Now answer this: **did it actually take 6 hours?**

You probably have a feeling. You might remember the bad ones. But across forty
jobs last month, you almost certainly can't say — and neither can Housecall Pro,
because it has no report that puts *quoted*, *scheduled*, and *actually worked*
side by side.

The information exists. Every job in your account already stores what you quoted
(the hours on your labor line items), what you booked (the appointment windows and
who was dispatched), and when your tech hit Start and Finish. It's just scattered
across three places and never added up.

That gap costs real money, quietly:

- If you're **underquoting**, every job burns margin and you find out at year end.
- If you're **overquoting**, you're losing bids you should win.
- If you're **blocking more calendar than the work needs**, you feel "fully
  booked" while techs have slack — so you turn away work you had room for.

Those three problems look identical from the outside. They feel like "we're busy
but margins are thin." They need opposite fixes.

---

## What this does

It connects Claude — the AI assistant — to your Housecall Pro account so you can
just ask.

```
You:  How did last week's jobs compare to what we quoted?

      MEASURED (21 jobs)
        Quoted 91.8 hrs  →  Actual 92.5 hrs      (101%)
        Scheduled was 129.2 hrs
        → 36.8 tech-hours blocked but not worked
```

No spreadsheets, no exports, no new software for your crew to learn. You type a
question the way you'd ask an office manager, and it reads your live data.

It also does the ordinary daily things: show next week's schedule and where you're
over capacity, pull up the backlog in priority order, give you a full profitability
breakdown on any single job, and flag which jobs need attention.

---

## What you might learn

Real example from the franchise that built this — **your numbers will differ,
and that's the point**:

| What we assumed | What the data showed |
|---|---|
| We're probably underquoting | Quoted 370 hrs vs actual 372 hrs across 67 jobs — **quoting was accurate** |
| We're at capacity | **79 tech-hours of calendar blocked but never worked** in one quarter |
| Big jobs are fine, small ones are noise | Sub-4-hour jobs ran **35% over** quote consistently |

That third one was the surprise. Small jobs have fixed overhead — drive time,
setup, cleanup, closeout — that doesn't shrink with the job. It's a pricing-floor
question, not an estimating one, and nobody was looking at it.

The second one was the most valuable. "We're slammed" turned out to mean "the
calendar is full," not "the crew is full." Those are different problems with
different fixes.

**You will not find the same things we did.** You might find you genuinely are
underquoting. The value isn't in our answers — it's in getting your own, from your
own jobs, in a few minutes instead of a quarter.

---

## It's not just one report

Quoted-vs-actual is the headline because it's the thing nothing else can tell you.
But most of the day-to-day value is more ordinary than that. Some things people
actually say, and what you'd get back:

**"I can't see where my week is actually going."**
Next week laid out with capacity per day, who's on what, and where you're over or
under. Then the same view four weeks out, so you spot the crunch while you can
still do something about it.

**"What should we schedule next?"**
Your backlog in priority order — urgent first, then jobs waiting on materials,
then the flexible ones. Plus a board of every active job by stage, so nothing sits
forgotten in "waiting on parts" for three weeks.

**"Did we actually make money on that job?"**
One job, end to end: hours by day, what you charged, what the labor and materials
cost you, gross margin, whether add-ons were billed, and how many days they took
to pay.

**"Where are our estimates stuck?"**
Everything in the pipeline by stage, with a full brief on any single estimate —
customer history, property notes, prior visits, and existing line items — pulled
together before you walk in the door.

**"Who owes us money?"**
Invoices with what's still outstanding, filtered by due date so you can pull just
what's overdue.

**"Where are our good leads coming from?"**
Lead sources across customers and jobs, so you can see which referral streams turn
into real work instead of just calls.

**"Can you just book it?"**
Yes — it can create and move appointments, add notes and tags, build and send
estimates, and update job stages. It asks before changing anything.

You don't memorize any of that. You ask in your own words and it works out what to
pull.

---

## Being straight with you about the limits

This is worth knowing before you decide, because it shapes what you can trust.

**Housecall Pro records one Start and one Finish per job** — not per tech, not per
visit, and it doesn't track breaks. That's a limit of the software, not of this
tool, and nothing can work around it.

What that means in practice:

- **Single-day jobs are genuinely measured.** Start and finish both land on the
  same day, so the math is real.
- **Multi-day jobs are estimated.** The tool anchors the first day's start and the
  last day's finish to real timestamps, then fills the middle days from your
  schedule. It's a good estimate, not a stopwatch.

So every number comes with a **confidence grade** — measured, estimated, or "no
usable signal" — and totals are reported separately for each. It will tell you
when it doesn't know something rather than quietly averaging a guess into your
results.

One consequence worth understanding: because measured jobs are single-day jobs,
and single-day jobs are small jobs, a clean "our quoting is accurate" result is a
statement about your *small* jobs. Big multi-day jobs can only be estimated. The
tool says so on screen rather than letting you over-read it.

**It also depends on your crew's habits.** If techs close jobs out days later, or
start the timer at the estimate visit, those jobs can't be measured. The tool
lists them by name and reason, so that list doubles as a coaching sheet.

---

## What it costs and what it needs

| | |
|---|---|
| **This software** | Free and open source. Runs on your own computer. |
| **Housecall Pro** | Must be on the **MAX plan** — API access is MAX-only. This is the real gate. |
| **Claude** | The desktop app, signed in to a Claude account. |
| **Setup time** | About 15 minutes, once. A setup script does the hard part. |
| **Your crew** | Changes nothing. They keep using Housecall Pro exactly as they do now. |

---

## Is it safe?

Fair question, and the honest answer has a caveat in it.

**Where your data goes:** nowhere new. This runs on your computer and talks
directly to Housecall Pro. There's no middleman service, no vendor collecting your
numbers, nobody else's cloud. Your Housecall Pro key stays in a settings file on
your own machine.

**What it can see:** your customers, jobs, estimates, invoices, and schedule —
the same things you see when you log in.

**The caveat:** it is **not read-only**. It can create and change customers,
estimates, jobs, appointments, tags, and invoices, because being able to actually
schedule something is half the value. Claude asks before making any change — but
read those prompts rather than clicking through them, the same way you'd review
anything before signing it.

There is deliberately no bulk-delete tool. Some things shouldn't be one sentence
away.

---

## Where to start

Set it up, then ask for a time variance on a month you remember well.

Look at the MEASURED block first and check it against your gut. If it matches what
you remember, you can trust the rest. If it doesn't, the jobs listed under "no
usable signal" will usually explain why — and fixing those is a conversation with
your crew about closing jobs out on time, not a software problem.

The first useful question is rarely "are we underquoting." It's usually **"how
much calendar are we blocking that we don't actually need?"**

---

*Setup instructions are in [README.md](README.md). If you get stuck, ask Claude to
"run hcp_check_setup" — it checks your setup and tells you in plain language what's
wrong and how to fix it.*
