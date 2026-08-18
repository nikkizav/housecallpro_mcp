# Questions people actually ask

*Grouped by what's really behind the question. Skip to yours.*

---

## "I'm not technical enough for this"

**Do I need to know how to code?**

No. You will not write a single line of code. Setup is: copy a line, paste it into
a window, press Enter. Four times. A script asks you a few questions about your
business and does the rest.

**What's the black window?**

It's called Terminal on a Mac and PowerShell on Windows. It's a place where you
type commands instead of clicking buttons. It looks intimidating and it is
genuinely just a text box. Nothing you paste from the instructions can hurt your
computer.

**What if I get stuck?**

Ask Claude. Paste the error message straight into the chat and say "I'm following
this setup guide and got this." It's surprisingly good at this, because it can see
what you're doing.

If that fails, the setup has a self-check. Type `run hcp_check_setup` and it will
tell you in plain language what's wrong and what to fix.

**What's the most common thing that goes wrong?**

Not restarting Claude properly. Closing the window isn't enough, Claude keeps
running in the background. You have to fully quit it: `Cmd + Q` on Mac, or
right-click the icon near your clock and choose Quit on Windows. Then reopen.

Second most common: running the `uv` install and then not closing and reopening
Terminal. The install only takes effect in a window you open afterward.

---

## "Isn't AI just making things up?"

**Will it invent numbers?**

The concern is fair and the answer is that this works differently than a chatbot
answering from memory. When you ask about job 4821, it goes and reads job 4821 out
of your account. The numbers come from your records.

**What about when the data is bad?**

This is the part worth understanding, and it's the reason to trust the rest.

Housecall Pro records **one Start and one Finish per job**. Not per tech, not per
visit, and it doesn't track breaks. That's a limit of Housecall Pro, not of this
tool, and nothing can work around it.

So every time figure comes back graded:

- **MEASURED** means a single-day job where start and finish are both real. Trust
  it.
- **ESTIMATED** means a multi-day job. First and last day are anchored to real
  timestamps, the middle days are filled in from your schedule. Directional, good
  for spotting problems, not a stopwatch.
- **SCHEDULED** means the timestamps were unusable, usually because a tech closed
  the job out days later. The "actual" there is just your calendar. Ignore it.

Totals are reported separately so the weak data never dilutes the good data.

**Does it ever just tell me it doesn't know?**

Yes, by design. Jobs it can't measure get listed by name with the reason: closeout
drift, stale start, late start, appointments incomplete. That list is a coaching
sheet for your crew, not a bug.

**What's the honest catch?**

Measured jobs are single-day jobs, and single-day jobs are small jobs. So a clean
"our quoting is accurate" result is really a statement about your small work. Big
multi-day jobs can only be estimated. The tool says so on screen instead of letting
you over-read it.

---

## "Is my data safe?"

**Where does my information go?**

Nowhere new. This runs on your computer and talks directly to Housecall Pro. There
is no middleman service, no vendor collecting your numbers, no shared server.

**Who can see it?**

You, Claude, and Housecall Pro. Nobody who shared this with you can see anything.

**Where does my API key live?**

In a settings file on your own machine. It's never uploaded anywhere.

If you share this tool with someone else, share the **link**, never your
`config.json` or your key. Their setup script builds their own.

**Can it delete my data?**

It can create and change customers, estimates, jobs, appointments, tags, notes,
and invoices. That's deliberate, because being able to actually schedule the thing
is half the value.

Claude asks before every change. Read those prompts rather than clicking through
them, the same way you'd read something before signing it.

There is deliberately no bulk-delete tool. Some things shouldn't be one sentence
away.

**Should I let my office manager use it?**

That's your call, and it's the same call as giving someone Housecall Pro admin
access. It can see and change what they'd be able to see and change anyway.

---

## "Will this disrupt my business?"

**Do my techs have to learn anything?**

No. Nothing changes in the field. They keep using Housecall Pro exactly as they do
today. This is a tool for whoever runs the office.

**Do I have to change how we enter data?**

No, but you'll want to. Once you see which jobs come back as "no usable signal,"
you'll notice they're almost all the same problem: techs closing out jobs hours or
days after they leave, or starting the timer at the estimate visit. Fixing that
habit makes more of your jobs measurable next quarter. That's a conversation with
your crew, not a software change.

**Does this replace my Housecall Pro reports?**

No. Those still do what they do. This answers the questions those reports were
never built for.

**What if I stop using it?**

Nothing happens. Delete the folder. Your Housecall Pro account is untouched.

---

## "What does it cost and what do I need?"

**What's the price?**

The tool is free and open source under the MIT license. Nothing to buy, no
subscription, no upsell.

**So what am I actually paying for?**

Only a Claude account. The desktop app is free to download and there's a free
tier. Heavy daily use is more comfortable on a paid plan.

**Do I need to upgrade my Housecall Pro plan?**

No. It runs on Housecall Pro's API, which comes with MAX, and every Local Handyman
owner is on MAX already. Nothing to buy and nothing to change.

*If you're outside the Local Handyman network:* confirm you have API access first,
under **Settings → Integrations → API**. No API section means you're on a plan
below MAX and this won't work yet.

**How long does setup take?**

About 15 minutes, mostly waiting on downloads.

**Do I need to keep it updated?**

Not really. Re-run the setup wizard if you add or lose a tech, or if your labor
cost changes. Then `run hcp_check_setup` to confirm.

---

## "What should I set carefully?"

Two settings matter more than the rest, and the setup wizard's defaults are
placeholders from somebody else's company.

**Your cost per tech-hour.** This is the single most important number. It should be
your *fully loaded* cost: wages, payroll taxes, vehicle, insurance, overhead. Not
the hourly wage. Every profit and margin figure depends on it. The default of $95
is not your number.

**Who counts as a field tech.** Pick only the people who actually do the work.
Leave out owners and office staff, or your capacity math will look better than
reality. Apprentices count as half a person for capacity but can still be booked a
full day.

---

## For franchise HQ

**Can we endorse or standardize this?**

It's MIT licensed and open source, so there's nothing to negotiate and nothing to
license. Anyone can use it, fork it, or change it.

**Can every owner actually run it?**

Yes. It needs Housecall Pro API access, which comes with MAX, and the whole network
is on MAX. Every owner can run it on day one with nothing to buy and no plan
change. That's unusual for a tool worth standardizing on.

**What's the real barrier to system-wide rollout, then?**

Not the software. It's support and setup. Fifteen minutes of copy-and-paste is
fifteen minutes for someone comfortable with a Terminal window and a support
ticket for someone who isn't.

The sensible sequence is a pilot group of five or six owners for a month, spanning
a range of comfort with technology, specifically to find where people get stuck so
the instructions can be fixed before it goes out to everybody. Then decide who
answers questions at scale.

**Is Housecall Pro involved?**

No. This is not affiliated with or endorsed by Housecall Pro. It uses their
public, documented API, the same one any integration partner uses.

**Who supports it if something breaks?**

Nobody, formally. It's a tool one franchisee built and shared. That's worth being
honest about. It has a built-in self-check that diagnoses most problems, and the
documentation is written for non-technical owners, but there's no support desk
behind it.

**Does it create liability around customer data?**

It doesn't move customer data anywhere new. It runs on the owner's machine and
talks to Housecall Pro directly, so the data path is the same one that exists when
they log into Housecall Pro in a browser. Worth having whoever handles your data
policy read the Safety section of the README, but there's no third-party processor
being introduced.

---

## Still stuck?

Two things, in order:

1. In Claude, type `run hcp_check_setup`. It checks everything and tells you
   what's wrong in plain language.
2. Paste your error into Claude and say what you were doing. It can usually work it
   out from there.
