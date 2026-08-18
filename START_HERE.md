# Start here

*If you've never heard of an MCP or an API, this page is for you. Three minutes.
Nothing to install yet.*

---

## The short version

Housecall Pro holds everything about your business. Every job, every estimate,
every invoice, every appointment.

It just doesn't answer questions.

You can pull a report, export a CSV, and build a spreadsheet. But you can't ask
it "did we make money on the Henderson job?" or "where am I overbooked in
three weeks?" and get an answer.

This lets you ask.

```
You:  Show me next week's schedule and where we're overbooked.
You:  How did last week's jobs compare to what we quoted?
You:  Full breakdown on job 4821. Did we make money?
```

Real answers, from your own account, in seconds.

---

## What the pieces are

There are three, and you only really need to understand the first two.

**Claude** is an AI assistant. It's an app you download and type into, like a
chat window. Free to start. If you've used ChatGPT, same idea.

**Housecall Pro** you already know.

**This connector** is the bridge between them. Claude on its own cannot see your
Housecall Pro account, any more than your accountant can see your bank balance
without you giving them access. You install this once on your own computer, and
from then on Claude can look things up when you ask.

That's it. That's the whole architecture.

---

## About that word, MCP

You will see "MCP" in some of the filenames and in the setup steps. It stands for
Model Context Protocol.

Here's all it means: it's the plug shape.

A USB port doesn't do anything interesting on its own. It's just an agreed-on
shape so that any device can plug into any computer. MCP is that, for AI
assistants and software. Someone builds a connector once, in the agreed-on shape,
and it works.

You will never need to think about this word again. If someone uses it at you,
they mean "connector."

---

## What you can actually do with it

Three buckets.

**See your week clearly.** Next week's schedule with capacity per day, who's on
what, where you're over and where you have room. Then the same view four weeks
out, so you catch the crunch while you can still move something.

**Find out where the money goes.** What you quoted versus what the job actually
took, across a month or a quarter. Full profitability on any single job: hours by
day, what you charged, what labor and materials cost, gross margin, days to pay.
Who still owes you money. Which lead sources turn into real work.

**Get things done.** It can create and move appointments, add notes and tags,
build estimates, and update job stages. It asks before it changes anything.

You do not memorize commands. You type the question the way you'd say it out loud
to your office manager.

---

## What it is not

Worth being clear, because people assume in both directions.

**It is not a new system for your crew.** They keep using Housecall Pro exactly as
they do today. Nothing changes in the field. This is a tool for whoever runs the
office.

**It is not guessing.** Claude is reading your actual records, not making up
plausible numbers. And where your data genuinely can't support an answer, it says
so instead of averaging in a guess. Every time figure comes back marked
**measured**, **estimated**, or **no usable signal**, so you know what you're
looking at.

**It is not read-only.** It can change things in your account, because being able
to actually book the appointment is half the value. It asks first. Read those
prompts rather than clicking through them.

**It is not a reporting replacement.** Housecall Pro's reports still do what they
do. This answers the questions those reports were never built for.

---

## What it takes

| | |
|---|---|
| **Cost of this software** | Free. Open source. Runs on your own computer. |
| **Housecall Pro plan** | Needs API access, which comes with **MAX**. Local Handyman owners are all on MAX already, so nothing to do here. |
| **Claude** | The desktop app, signed in. |
| **Setup** | About 15 minutes, once. A setup script does the hard part. |
| **Technical skill** | None. You'll paste a few lines into a black window. That's the hardest part and it is genuinely copy, paste, Enter. |
| **Your crew** | Nothing changes for them. |

*Not with Local Handyman? Confirm you have API access before you start: in
Housecall Pro go to **Settings → Integrations → API**. No API section means
you're on a plan below MAX and this won't work yet.*

---

## Where your data goes

Nowhere new.

This runs on your computer and talks directly to Housecall Pro. There is no
middleman company, no vendor collecting your numbers, nobody else's server. Your
Housecall Pro key stays in a settings file on your own machine.

What it can see is what you see when you log in: your customers, jobs, estimates,
invoices, and schedule.

---

## Next steps, in order

1. **Read [WHY_THIS_HELPS.md](WHY_THIS_HELPS.md).** Five minutes on what you'd
   actually learn and what the honest limits are. Worth it before you install
   anything.
2. **Follow [README.md](README.md).** Fifteen minutes of setup, five steps.
3. **Read [FIRST_WEEK.md](FIRST_WEEK.md).** The five questions to ask first and
   what each one tells you.

Questions or worries before you start, [FAQ.md](FAQ.md) probably covers it.
