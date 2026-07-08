# First-run self-test (roadmap #22)

So a curious user can prove the whole **Record → Check → Teach → Try** loop in
~2 minutes without recording anything, TalkTeach can seed a tiny toy dataset.

- `backend/talkteach/selftest.py::make_toy_dataset` writes a handful of short,
  clean synthetic-tone WAVs paired with karaoke sentences as transcripts.
- `POST /api/selftest` seeds them into the project DB (marked good) so the
  sufficiency meter moves and "Teach!" becomes verifiable. The UI exposes this as
  a simple "try a practice set" button.
- `scripts/make_toy_dataset.py [dest] [--lang] [--clips]` writes the set to a
  folder for manual end-to-end checks.

The clips are synthetic tones — enough to exercise the pipeline + the training
**simulation** end-to-end with zero ML deps. A *real* fine-tune wants real speech
(see `tests/test_integration_train.py`, which synthesises its own tones only to
prove the loop runs).

```bash
python scripts/make_toy_dataset.py /tmp/toy --clips 8
cd backend && .venv/bin/python -m pytest tests/test_api.py -k selftest -q
```
</content>
