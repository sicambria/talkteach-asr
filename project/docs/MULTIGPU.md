# Optional multi-GPU / distributed training (#56)

TalkTeach targets a family laptop, so single-device training is the default and the
only path the product UI exposes. Multi-GPU is a **documented escape hatch** for
power users with a workstation or a rented multi-GPU box — not a feature the child's
flow needs.

## Why there is no in-app "use N GPUs" toggle

Hugging Face multi-GPU is driven by the **launcher**, not by a
`Seq2SeqTrainingArguments` flag. `Trainer`/`Seq2SeqTrainer` already detect and use
all visible GPUs (DataParallel) or every rank a distributed launcher spawns (DDP) —
the parallelism comes from *how you start the process*, not from a knob we could set
in the `TrainingPlan`. Inventing a `plan.multi_gpu = True` flag would be a fake knob
that maps to nothing, so we deliberately don't ship one (this is the honest tier for
#56).

## The escape hatch

The real training entry point is the headless CLI (#54). Launch it under a
distributed launcher:

```bash
# One node, 2 GPUs, DistributedDataParallel:
torchrun --nproc_per_node=2 -m talkteach.cli train \
    --manifest data/manifest.json --workdir runs/multi

# Or via 🤗 Accelerate (after `accelerate config`):
accelerate launch -m talkteach.cli train \
    --manifest data/manifest.json --workdir runs/multi
```

`Seq2SeqTrainer` picks up the ranks the launcher provides; the effective batch size
scales with the number of processes. Everything else — the LoRA config, the safety
rails (#3), checkpoint/resume (#17) — is unchanged.

### Controlling which GPUs

```bash
CUDA_VISIBLE_DEVICES=0,1 torchrun --nproc_per_node=2 -m talkteach.cli train ...
```

## Tier / verification

Doc-only in this sandbox: verifying real multi-GPU training needs multiple GPUs,
which aren't available here. The code path (single-process `Trainer.train`) is the
same one the launcher fans out, so no product code changes are required to use the
hatch — only the launch command. This is tracked as #56 in `ROADMAP.md`.
