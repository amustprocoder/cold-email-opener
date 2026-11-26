# Website → 3-line cold-email opener

Give it a company's website. It reads the site, drafts the first three lines of a cold email to the founder,
and shows the exact quote from the site behind each line, so you can check it before you send.

```
python opener.py https://plausible.io
```

```
Plausible  (https://plausible.io/)
Founder named on site: Uku and Marko

OPENER
  You built Plausible as a simple and privacy-friendly alternative to Google Analytics.
  Your platform already serves over 22,000 paying customers and stores 332 billion events.   [UNVERIFIED: not found on the page, check before sending]
  I help small software companies see the numbers that run the business.

EVIDENCE (quotes from the site)
  1. Plausible Analytics | Simple, privacy-friendly Google Analytics alternative
  2. 22k
  3. (bridge line about us, no site fact)

Grounded: 1/2 fact lines verified against the page text

gemini-3.5-flash-lite | 1719 in + 131 out tokens | $0.00084 | 9.5 s | text from homepage (6000 chars)
```

That UNVERIFIED flag is the point of the tool: the site says "22k", the model wrote "22,000 ... 332 billion",
and the code could not find those numbers on the page, so it tells you not to send that line as is. (This was
the first run; the second run on the same site wrote "22k" and passed 2/2. The model is not deterministic, the
check is.)

## Run it

1. Python 3.11+. `pip install -r requirements.txt`
2. A free Gemini key from https://aistudio.google.com. Set it: `setx GEMINI_API_KEY your_key` (Windows) or
   `export GEMINI_API_KEY=your_key` (Mac/Linux). Open a new terminal.
3. `python opener.py <website>`  or, for a browser view, `streamlit run app.py`

Every run appends one line to `runs.csv`: time, url, model, tokens in, tokens out, cost, seconds, where the
text came from, how many fact lines were verified. `samples/` holds three full JSON outputs.

## What runs in code, what runs in the model

| Step | Where | Why |
|---|---|---|
| Fetch the homepage, strip scripts/nav/footer, keep title + meta description + body, trim to 6,000 chars | code (`src/fetch.py`) | deterministic, free, fast; the model never sees raw HTML |
| If the page is thin (JavaScript-only), try `/about`, then a public page-to-text proxy | code | most failures are fetch failures, not model failures |
| Write 3 lines + the quote that backs each + founder name if the site names one | model (`src/draft.py`, Gemini 3.5 Flash-Lite, falls back to 3.8 Flash) | the only step that needs language |
| Check every quote and every number in lines 1-2 against the page text; flag misses | code | the model's one job is to be specific, and specific is where it invents |
| Count tokens from the API's `usageMetadata`, price them, log the run | code (`src/cost.py`) | cost is measured, not estimated |

Line 3 is a fixed bridge about us, so it is not checked against the site.

## Cost and what breaks at 1,000 runs a day

Measured on 8 runs across 5 real sites during testing (`runs.csv` keeps the last 6): about 1,600-2,100 input
tokens and 120-150 output tokens per run,
**$0.0008-0.0009 per run** on Gemini 3.5 Flash-Lite at the paid price ($0.30 in / $2.50 out per 1M tokens,
https://aistudio.google.com/docs/pricing, read 26 Nov 2026). 1,000 runs a day is about **$0.90 a day, $27 a
month**. Latency 2-10 s, almost all of it the model call.

What breaks first, in order:

1. **The free tier.** It is per-project, per-day, and Google no longer publishes a fixed table; 1,000 runs a day
   needs a billed key. Cost is the $27/month above, so money is not the problem.
2. **Fetching, not the model.** Sites that block bots, need JavaScript, or sit behind Cloudflare return nothing or
   a cookie wall. At 1,000 a day expect a few percent of these; the fix is a headless browser or a paid scraping
   API for the misses only, which roughly doubles cost per failed site but not per run.
3. **Rate limits and busy models.** Requests per minute on the model, and polite spacing on the target sites.
   Fix: a queue with 2-4 workers and retry-with-backoff, which is already how the model fallback works here.
4. **Quality drift.** Nothing stops the model from writing a true but useless line. The grounding check catches
   invented facts, not boring ones. At scale you would sample 20 outputs a day and keep a small test set of sites
   with known-good openers.

## What I left out, and why

- No email sending or contact lookup: the task was the opener, and the rules said not to contact anyone.
- No crawl beyond the homepage and `/about`: more pages means more tokens and more noise for a 3-line output.
- No caching of fetched pages: at 1,000 runs a day on different sites a cache saves little; at repeat sites it
  would be the first thing to add.
- No fine-tuned prompt per industry: one prompt, one test set first.

Built by Om Rana with Claude Code as pair programmer. Gemini for the model call because it has a free tier.
