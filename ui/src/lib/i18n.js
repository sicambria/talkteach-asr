// i18n for the TalkTeach UI (roadmap #36).
//
// The UI's plain-language strings live here as keyed catalogs so a non-English
// anyone can use the app once real translations are added. Kept dependency-free
// and simple; it pairs with the future Svelte 5 / TypeScript migration
// (project/docs/DECISIONS.md D-011). Each hard-coded screen string is `$t('key')`.
import { writable, derived } from 'svelte/store';

// The English base catalog. Add a language by adding another map — missing keys
// fall back to English, so a partial translation never blanks the UI.
const EN = {
  // App chrome
  'app.arena': '🏆 Arena',
  'app.wizard': 'Wizard',
  'app.advanced': 'Advanced',
  'app.advanced_details': 'Advanced details',
  'app.language': 'Language',

  // Screen 0 — New project
  'newproject.title': 'What should we teach?',
  'newproject.subtitle': 'Give your project a fun name. You can change it later.',
  'newproject.name_placeholder': 'Like: My Robot Friend',
  'newproject.name_label': 'Project name',
  'newproject.figure_out': 'Let it figure out the language by itself',
  'newproject.pick_language': 'Pick a language',
  'newproject.search_more': '…or search every language',
  'newproject.search_placeholder': 'Type a language, like “Polish” or “Japanese”…',
  'newproject.search_label': 'Search all supported languages',
  'newproject.teaching_in': 'Teaching in:',
  'newproject.error': "Something went wrong. Let's try again.",
  'newproject.starting': 'Starting…',
  'newproject.go': "Let's go! ▶",
  'newproject.import': '📁 Import a folder of recordings instead',
  'newproject.importing': 'Importing…',

  // Pre-flight screen (#18)
  'preflight.title': 'Is everything ready?',
  'preflight.subtitle': "Let's make sure your computer is set up before we record.",
  'preflight.checking': 'Checking your computer…',
  'preflight.error': "I couldn't check if everything is ready.",
  'preflight.error_hint': 'Is the helper program turned on? You can still carry on.',
  'preflight.ready': "You're ready!",
  'preflight.fix': "Let's fix this first",
  'preflight.recheck': '🔄 Check again',
  'preflight.go': "Let's record! ▶",
  'preflight.continue': 'Continue anyway ▶',

  // Screen 1 — Record
  'record.title': "Let's record!",
  'record.read_prompt': 'Read this out loud, then press the big button.',
  'record.press_to_talk': 'Press to talk',
  'record.listening': 'Listening… press to stop',
  'record.hearing': 'We can hear you! Press to stop',
  'record.another': '🔀 Another sentence',
  'record.start_recording': 'Start recording',
  'record.stop_recording': 'Stop recording',
  'record.checking': 'Checking your recording…',
  'record.great': 'Great recording!',
  'record.try_again': "Let's try that one again.",
  'record.drop': '📁 Drag sound files here too',
  'record.drop_label': 'Add sound files you already have',
  'record.how_much': 'How much have we recorded?',
  'record.start_hint': 'Press the mic to start filling this up!',
  'record.no_mic': 'No microphone? Try a ready-made set instead.',
  'record.practice': '🎁 Try a practice set',
  'record.ready_next': 'Next: Check the words ▶',
  'record.not_ready': 'Record a bit more first…',

  // Screen 2 — Check
  'check.title': 'Check the words',
  'check.subtitle': 'Did the computer hear you right? Tap a box to fix any words.',
  'check.finding': 'Finding your recordings…',
  'check.none': 'No recordings yet — go back and record some!',
  'check.back_record': '◀ Back to recording',
  'check.writing': 'Listening and writing it down…',
  'check.recording': 'Recording', // shown as "Recording 1", "Recording 2", …
  'check.words_for': 'Words for', // aria: "Words for Recording 1"
  'check.no_words': '(no words yet)',
  'check.saving': 'Saving…',
  'check.save_fix': 'Save fix',
  'check.try_again': 'Try again',
  'check.next': 'Next: Teach it! ▶',

  // Screen 3 — Teach
  'teach.title': 'Teach it!',
  'teach.intro': 'When you press the button, the computer will learn from your recordings.',
  'teach.teach_btn': 'Teach it! ✨',
  'teach.record_more': 'Record more first…',
  'teach.keep_watching': 'Keep watching ▶',
  'teach.how_far': 'How far along?',
  'teach.how_smart': 'How smart is it?',
  'teach.smart_suffix': '% smart',
  'teach.pause': '⏸ Pause',
  'teach.close_later': 'Close and continue later',
  'teach.try_again': 'Try again',
  'teach.next': 'Next: Try it! ▶',
  'teach.done': "All done! It's ready to try.",
  'teach.failed': "Oops, that didn't work.",
  'teach.almost': 'Almost there…',
  'teach.getting_smarter': 'Getting smarter!',
  'teach.warming': 'Warming up the brain…',
  'teach.stopped_early': "Teaching stopped early. Let's try again.",

  // Screen 4 — Try
  'try.title': 'Try it!',
  'try.subtitle': 'Say something and see if the computer understands you now.',
  'try.thinking': 'Thinking…',
  'try.heard': 'It heard:',
  'try.save': '💾 Save',
  'try.use': '🖥 Use on my computer',
  'try.make_better': '🔁 Make it better',
  'try.teach_first': 'Teach the computer first, then you can use it here.',
  'try.save_captions': '💬 Save captions',
  'try.captions_saved': '💬 Captions saved',

  // Shared chrome
  'common.back': '◀ Back',
  'common.saved': 'Saved ✓',
};

// A synthetic QA "pseudo-locale" generated programmatically from English: every
// value is accented and bracketed (Hello → ⟦Ħéĺĺó⟧). It is NOT a shipped
// translation — it exists so testers (and the language-switcher success check)
// can see the whole UI swap through `t()` at once, and to catch un-keyed strings
// (anything that stays plain English hasn't been migrated). Zero-maintenance: it
// tracks `en` automatically. See project/docs/I18N.md.
const ACCENTS = { a: 'á', e: 'é', i: 'í', o: 'ó', u: 'ú', A: 'Á', E: 'É', H: 'Ħ' };
function pseudo(value) {
  const accented = value.replace(/[aeiouAEH]/g, (c) => ACCENTS[c] ?? c);
  return `⟦${accented}⟧`;
}
const QA = Object.fromEntries(Object.entries(EN).map(([k, v]) => [k, pseudo(v)]));

// String catalogs by language code. `en` is the only real, shippable catalog.
const CATALOGS = { en: EN, qa: QA };

// Human-facing names for the switcher; unknown codes fall back to the code.
const LOCALE_NAMES = { en: 'English', qa: 'Pseudo (QA)' };

export const locale = writable('en');

/** Reactive translator: `$t('record.title')`. Falls back to English, then the key. */
export const t = derived(locale, ($locale) => (key) => {
  const lang = CATALOGS[$locale] || CATALOGS.en;
  return lang[key] ?? CATALOGS.en[key] ?? key;
});

export function availableLocales() {
  return Object.keys(CATALOGS);
}

export function localeName(code) {
  return LOCALE_NAMES[code] || code;
}
