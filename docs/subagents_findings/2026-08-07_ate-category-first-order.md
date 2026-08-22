---
keywords: runner, category-first, channel, DUT, test_tag, ORT, Settling, GBW, popup
main_idea: Run order is board/category → channel → all DUTs → tests; Continue popup/dock shows short test tags (ORT/Settling/GBW). B-only selection starts on CHB.
---

# Category-first run order + short popup tags

## Order
1. Same fixture category (BUFFER / G11 / G_NEG100)
2. Channel (CHA then CHB, or B-only if only B selected)
3. DUTs 1..N on that channel
4. Next channel, then next category

## UI
Gate dock + modal kind show `test_tag` short form.
