# Stage 6 bounded scientific review (not Codex)

Three real OpenAI API reviewers (STATS-02, AUDIT-02, FEATURE-02), one call each.
Only the pinned development brief may cross the provider boundary. No locked
outcomes, production, passwords, or trading permissions are exposed.

Trigger is intentionally restricted to a new commit of RUN_ONCE_V1. No scheduled
runs or paid retries. GPT-5.6 Sol pricing used for the software budget:
$4/M input + $20/M output. Under 12,000 bytes prompt and <=2,400 output tokens
the upper model-token estimate is $0.096/reviewer or $0.288 for three. Check
OpenAI billing for the actual amount. CI/preflight does not incur API costs.

Output is a critique/proposal, NOT validation of investment returns or
a Freeze qualification. No results may modify the existing 24 hypotheses.
Codex engineering handoff is GitHub issue #72, separate from this workflow.
