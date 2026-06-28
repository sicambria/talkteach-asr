# Multi-project support in the app layer (#29)

A family might teach one model for a younger sibling's voice, another for a
grandparent who speaks a different language. The **data layer already supports
this**: `data/project.py` is one `ProjectDB` per SQLite file, and `config.py`
already separates `DATA_ROOT` (`~/.talkteach`) from `DEFAULT_PROJECT_DIR`
(`DATA_ROOT/default`). What's missing is the *app layer*: `app.py` is hard-wired
to the single `default` project for Phase 0.

## What already works

- `ProjectDB.open(db_path)` opens/creates any project DB idempotently (WAL,
  foreign keys, schema applied).
- One project = one directory: `db`, `clips/`, `runs/`, `exports/` all live under
  it. Nothing in the data layer assumes there is only one.

## What the app layer needs

1. **A project registry.** A small index under `DATA_ROOT` (a top-level
   `projects.json` or a tiny registry DB) listing `{id, name, dir, created_at,
   last_opened}`. Project dirs become `DATA_ROOT/<slug>/` instead of the fixed
   `default`.
2. **A "current project" notion.** Replace the module-level `_db()` /
   `DEFAULT_PROJECT_DIR` constants with a resolver that takes the active project
   id (from the registry's `last_opened`, or an explicit request param).
3. **Endpoints** (sketch):

   ```
   GET    /api/projects                 → [{id, name, language, last_opened}]
   POST   /api/projects   {name, lang}  → create dir + DB, return id
   POST   /api/projects/{id}/open       → set active, return summary
   DELETE /api/projects/{id}            → archive/remove (with confirm)
   ```

   The existing per-project endpoints (`/clips`, `/sufficiency`, `/train`, …)
   then resolve against the active project rather than the hard-coded default.
4. **A project picker screen** (UI): a "choose or start a project" screen before
   the wizard — big tiles, child-readable names, a "+ new" tile. Reuses Screen 0
   (new project) for creation.

## Migration

The existing `default` project becomes the first registry entry on first launch
(no data move needed — its dir already exists). Old single-project installs keep
working.

## Verify

```bash
curl -s localhost:8756/api/projects                          # list
curl -s -XPOST localhost:8756/api/projects -d '{"name":"Mia","language_code":null}'
curl -s -XPOST localhost:8756/api/projects/2/open            # switch
```

## Status

**Tier B** (#29). The data layer is real and tested for one-DB-per-project; the
registry, the active-project resolver, the endpoints above, and the picker screen
are the pending app-layer work. No new ML or storage design is required — it is
wiring `app.py` to what `data/project.py` already affords.
