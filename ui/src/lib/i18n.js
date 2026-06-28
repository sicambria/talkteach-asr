// Minimal i18n scaffold for the TalkTeach UI (roadmap #36).
//
// The UI's plain-language strings are English-only today. This gives them keys
// and a tiny lookup so a non-English-speaking child can use the app once
// catalogs are added. Kept dependency-free and simple; it pairs with the future
// Svelte 5 / TypeScript migration (DECISIONS.md D-011). Wire `t()` into screens
// incrementally — each hard-coded string becomes `t('key')`.
import { writable, derived } from 'svelte/store';

// String catalogs by language code. Add a language by adding its map. Missing
// keys fall back to English, so a partial translation never blanks the UI.
const CATALOGS = {
  en: {
    'record.title': "Let's record!",
    'record.read_prompt': 'Read this out loud, then press the big button.',
    'record.press_to_talk': 'Press to talk',
    'record.listening': 'Listening… press to stop',
    'check.title': 'Check the words',
    'teach.title': 'Teach it!',
    'try.title': 'Try it!',
    'common.back': '◀ Back',
    'common.saved': 'Saved ✓',
  },
};

export const locale = writable('en');

/** Reactive translator: `$t('record.title')`. Falls back to English, then the key. */
export const t = derived(locale, ($locale) => (key) => {
  const lang = CATALOGS[$locale] || CATALOGS.en;
  return lang[key] ?? CATALOGS.en[key] ?? key;
});

export function availableLocales() {
  return Object.keys(CATALOGS);
}
