## Change summary

Describe what changed and why.

## Navigation checkpoint

- [ ] Linked the **existing** issue/PR or justified a new one; named the blocker this change removes
- [ ] Chose the smallest available tool: deterministic code / Codex / specialist agent / manual review; listed which **actually ran**
- [ ] Reported actual test/CI and independent critic evidence (or explicitly **not yet reviewed**)
- [ ] Checked data vintage, missing/late forecast slots, elapsed lead and locked-OOS restrictions where relevant
- [ ] Disclosed API/token/cost, automation, permissions and data-access impact; no unapproved spending or dispatch
- [ ] Preserved Stage-6 **NO-GO / NO_RUN / NO_FREEZE** unless A1–A6 and independent scientific approval are documented

**Next blocking gate / owner:** 

## Impact

- [ ] No Stable Core contract break
- [ ] No new security permission
- [ ] No capital/execution authority change
- [ ] Data/schema impact reviewed

## Validation

- [ ] `python scripts/quality_gate.py` passes
- [ ] Relevant regression tests added/updated
- [ ] Rollback is understood

## Risk class

- [ ] LOW
- [ ] MODERATE
- [ ] HIGH
- [ ] CRITICAL
