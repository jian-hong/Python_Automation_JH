# Dual-channel Continue (future 2Gxx)

OpAmp already pauses CHA then CHB (`TestSpec.dual_channel`, operator Continue `kind=channel_change`). Path B Logic registers `dual_channel=False` (1Gxx CHA-only).

Reuse that pattern as **DATA** on the product_model recipe. Do not hardcode OpAmp. Do not invent a 2G part YAML without a Datasheet card.

```yaml
recipe:
  dual_channel_continue: true
  channels: [CHA, CHB]
```

When `dual_channel_continue` is true, the runner ORs that flag onto Path B specs at run (registry stays `dual_channel=False`; do not wrap `TestSpec.run`). Operator Continue: Channel A, then Channel B. **Do not skip rewire prompt** (OpAmp-style switch). Recable Channel B after CHA Human Continue. `recipe.channels` is the channel list. Default CHA then CHB when the flag is on and channels are omitted.

1Gxx cards (RS1G97 / RS1G126 / RS1GT34 / overnight CONFIRMED / next-wave G00/G02/G04/G86) leave the flag unset/false. Dual-channel Continue is **2Gxx only**.

RS2G08 / RS2G32 are **CONFIRMED** (JH LAST-DAY UNLOCK 2026-09-21) for function/truth/isolation (`recipe.dual_channel_continue: true`, `channels: [CHA, CHB]`). Unsigned VOH/VOL/VIH and pin numbers HOLD. Do not invent OE/IOZ. Extra `rs2g*.yaml` without a Datasheet card stays forbidden.
