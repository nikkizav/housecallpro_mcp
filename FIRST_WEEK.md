# Your first week

*Setup is done and it works. Now what? Five questions, in this order. About 30
minutes total, spread over a week.*

The point of this order is that each question builds trust in the next one. Don't
skip to number five.

---

## Day 1: Prove it's reading your real data

Ask:

```
Full analysis on job [pick a job you remember well].
```

Pick a job you have opinions about. One that went badly is ideal.

**What you'll get:** hours by day, what you charged, what labor and materials cost
you, gross margin, whether add-ons got billed, and how long they took to pay.

**What you're checking:** does this match what you remember? Look at the
**Confidence** line. If it says `MEASURED`, the times are real. If it says
`SCHEDULED`, the timestamps weren't usable and you're looking at your calendar,
not worked hours.

**Why this first:** you can't evaluate a report on 60 jobs if you don't trust it on
one. Verify it against your own memory before you trust it at scale.

---

## Day 2: Find out how much calendar you're wasting

Ask:

```
Run a time variance for last quarter.
```

**What you'll get:** three blocks, one per confidence grade. Look at the
**MEASURED** block first.

**What you're looking for:** the gap between **scheduled** hours and **actual**
hours. Not the gap between quoted and actual. The scheduled one.

That number is calendar you blocked and didn't use. It's the difference between
"we're full" and "the calendar is full," and most shops have never seen it. It's
usually the single most valuable number in the whole tool.

**What to do with it:** if the gap is large, you have room you didn't know you had.
That's either more jobs, tighter arrival windows, or both.

---

## Day 3: Check your estimating, carefully

Same report, different column. Ask:

```
How did we do on quoted vs actual hours last quarter?
Break it out by job size.
```

**What you're looking for:** whether you're over or under, and where.

**Read this before you conclude anything:** MEASURED jobs are single-day jobs, and
single-day jobs are small jobs. So a clean result in the MEASURED block is a
statement about your *small* work. Your big jobs can only be ESTIMATED, and for
those "actual" partly means "what you blocked."

Judge your estimating from the MEASURED block. Read the ESTIMATED block as crew
time committed, not stopwatch time.

**The thing to watch for:** small jobs running consistently over. Drive time,
setup, cleanup, and closeout don't shrink with the job. If your sub-4-hour work is
running 30%+ over, that's a pricing floor question, not an estimating one. Very
different fix.

---

## Day 4: Get your coaching list

Ask:

```
Which completed jobs have no usable actual time, and why?
```

**What you'll get:** jobs listed by name with a reason:

- **closeout drift**: the tech closed the job hours or days after leaving
- **stale start**: the job was started long before the appointment, often at the
  estimate
- **late start**: started well after the scheduled time
- **appointments incomplete**: quoted hours far exceed the booked calendar time

**What to do with it:** this is a crew conversation, not a software problem. Every
job on this list is one you paid for and can't learn anything from. Fix the habits
and those jobs become measurable next quarter, which makes every report above
better.

Start with closeout drift. It's usually the biggest bucket and the easiest fix.

---

## Day 5: Make it part of running the week

This is the one that turns a good report into a habit. Ask:

```
Show me next week's schedule with capacity by day.
What's in the backlog that should get scheduled first?
Where are we overbooked in the next four weeks?
```

**What you'll get:** the week laid out with who's on what and where you're over or
under, then the backlog in priority order (urgent, then waiting on materials, then
flexible), then the four-week view.

**Why this is the one that sticks:** the analysis questions are things you'll run
monthly or quarterly. This one you'll run every Friday. It's the reason to keep the
tool open.

---

## After the first week

A reasonable rhythm:

| When | What |
|---|---|
| **Every Friday** | Next week's schedule and capacity. Backlog priority. |
| **Monthly** | Time variance for the month. Check the no-usable-signal list. |
| **Quarterly** | Quoted versus actual by job size. Revisit your pricing floor. |
| **As needed** | Full analysis on any job that felt wrong. Who owes you money. Where estimates are stuck. |

---

## Two things to fix before you trust the money numbers

If you rushed the setup wizard, go back and check these. They're in `config.json`
or you can just ask Claude to explain them.

**Your cost per tech-hour.** Every margin and profit figure depends on this. It
should be your fully loaded cost: wages, payroll taxes, vehicle, insurance,
overhead. The default of $95 is a placeholder from another company. If it's wrong,
every profitability number you've read this week is wrong.

**Who's a field tech.** Only people who actually do the work. Owners and office
staff in that list will make your capacity look better than it is.

Changed either one? Re-run the setup wizard, then `run hcp_check_setup`.

---

## If a number looks wrong

Ask for the full analysis on that specific job and read the **Confidence** line
first. Nine times out of ten, `SCHEDULED` explains it: the timestamps weren't
usable, so you're looking at your calendar rather than real work.

If results come back empty, run `hcp_check_setup`. It's almost always a config
problem, and it will tell you which one.
