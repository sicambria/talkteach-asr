<script>
  // In-app third-party credits (roadmap #28). Data is generated from
  // docs/THIRD_PARTY.md by scripts/gen_credits.py into lib/credits.json, so the
  // attribution shown here can never drift from the documented licences.
  import credits from '../lib/credits.json';
</script>

<section class="credits">
  <h2>Thanks to</h2>
  <p class="note">{credits.note}</p>
  <ul>
    {#each credits.components as c (c.name)}
      <li>
        <strong>{c.name}</strong> — {c.role}
        <span class="license">{c.license}</span>
      </li>
    {/each}
  </ul>
</section>

<style>
  .credits {
    text-align: left;
    max-width: 640px;
    margin: 0 auto;
  }
  .note {
    color: var(--tt-ink-soft, #667);
  }
  .license {
    color: var(--tt-ink-soft, #667);
    font-size: 0.85rem;
  }
  li {
    margin-bottom: 6px;
  }
</style>
