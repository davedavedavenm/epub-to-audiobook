# GPU / Vast.ai Safety Rules — READ BEFORE ANY GPU ACTION

**The Vast.ai balance is real money and small (~$3–4). Treat cloud GPU as
OFF by default. These rules exist because an automated agent can drain the
balance in minutes by leaving an instance running.**

## The hard rules (for humans AND agents)

1. **Default is LOCAL.** Audiobook rendering runs on local CPU unless the
   user has *explicitly, in this session,* asked for cloud GPU. Never infer
   it. "Make it faster" is NOT permission to spend money — ask.
2. **The UI gate defaults OFF.** Settings → *Render Location* is
   `💻 Local (free)` by default. The backend setting `GPU_RENDER_ENABLED`
   defaults `0`. The `/api/gpu/scale-up` endpoint returns 403 unless it is
   explicitly turned on. Do not flip this setting on the user's behalf.
3. **Never spin up a Vast instance without an explicit user request for
   *this* task.** Not to "test", not to "benchmark", not to "save time".
4. **If you create an instance, you destroy it in the same session.**
   `python vast.py destroy instance <id>` — and verify
   `show instances` returns 0. Billing continues until destroyed, even when
   idle. A stopped instance still bills for storage.
5. **Respect the cost cap.** `AUTOSCALE_COST_CAP` (default $1.00). Never
   raise it without the user asking.
6. **Confirm the balance is intended to be spent.** If a GPU action would
   cost more than a few pence, or the balance is under $1, stop and ask.

## What "local" means here

- Chatterbox Turbo and Hume TADA both run on local CPU (see
  PLAN-ENGINE-UI.md). Slower (~14h and ~26h per book respectively), but the
  user has stated **time does not matter; quality and not wasting money
  do.** Overnight local batches are the expected default path.
- Cloud GPU is an opt-in accelerator for when the user *chooses* to trade a
  few pence for hours of wall-clock — never the automatic choice.

## Proven-safe Vast workflow (only when explicitly requested)

1. `python vast.py show user` — confirm balance and that spending is intended.
2. Search cheap reliable offers; create from a `pytorch/pytorch` image.
   Key format: the copied key is prefixed `arc_` — strip it to the 64-hex.
3. Do the work (see PLAN-ENGINE-UI.md Phase B for the TADA recipe).
4. **Download results, then immediately `destroy instance <id>` and verify 0
   instances remain.**
5. Report actual spend (`show user` before/after).

## For the implementing agent building GPU features

- Every code path that can bill money MUST call `gpu_render_enabled()`
  (app.py) and refuse when false. Add the same gate to any new auto-scale
  trigger. Belt and braces: gate at the endpoint AND before any
  `scale_up()` / instance-create call.
- Keep the default OFF in every layer: DB setting, env var, UI control.
- Never add an "auto-enable GPU when queue is long" path that is on by
  default.
