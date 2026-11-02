// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 jertech and contributors
// Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
// The Verdi status page: current status in the colours Verdi sends. verdi-settings.js is imported with this file's
// own query, because without the version in its URL it could stay cached after an update.

export function settingsUrl(page) {
  const url = new URL(page);
  url.pathname = url.pathname.replace(/verdi-panel\.js$/, "verdi-settings.js");
  return url.href;
}

const settings = await import(settingsUrl(import.meta.url));

export const FALLBACK_COLOR = "#D3D3D3";

const MENU_ICON = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";
const GEAR_ICON = "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z";
const VEHICLE_ICON = "mdi:fire-truck";

const LABELS = {
  en: {
    myStatus: "My status",
    vehicles: "Vehicles",
    personnel: "Personnel",
    until: "Until",
    total: "Total",
    noData: "No data",
    unknown: "Unknown",
    empty: "No Verdi data found.",
    incomplete: "List incomplete",
    menu: "Menu",
    changeStatus: "Change status",
    chooseStatus: "Choose a status",
    status: "Status",
    duration: "Duration",
    addException: "Add exception",
    returnToPlanning: "Return to planning",
    close: "Close",
    overruled: "Verdi accepted this, but a fixed planning overrules it. Your status stays as shown.",
    unchecked: "Sent to Verdi, but the result couldn't be checked. The status on this page shows what applies.",
    unclear: "No clear answer. Check in Verdi whether the change was made.",
    sending: "Sending...",
    readiness: "Readiness",
    statistics: "Statistics",
    since: "since",
    next: "Next",
    missing: "Missing",
    last: "last",
    now: "now",
    loading: "Loading...",
    open_history: "open history",
    history: "History",
    train_complete: "Complete",
    train_incomplete: "Incomplete",
    today: "Today",
    yesterday: "Yesterday",
    previous_day: "Previous day",
    next_day: "Next day",
    history_empty: "No history for this day.",
    history_failed: "History isn't available.",
    available: "Available",
    preAlert: "Pre-alert",
    garrison: "Garrison",
    problem_token: "Verdi login expired. Check the Verdi Token Relay.",
    problem_paused: "Verdi asked to slow down. It will retry by itself.",
    problem_verdi: "Verdi can't be reached. It will retry by itself.",
    problem_stale: "Some data may be out of date. It will retry by itself.",
  },
  nl: {
    myStatus: "Mijn status",
    vehicles: "Voertuigen",
    personnel: "Personen",
    until: "tot",
    total: "Totaal",
    noData: "Geen gegevens",
    unknown: "Onbekend",
    empty: "Geen Verdi-gegevens gevonden.",
    incomplete: "Lijst onvolledig",
    menu: "Menu",
    changeStatus: "Status wijzigen",
    chooseStatus: "Kies een status",
    status: "Status",
    duration: "Duur",
    addException: "Uitzondering toevoegen",
    returnToPlanning: "Terug naar planning",
    close: "Sluiten",
    overruled: "Verdi heeft dit aanvaard, maar een vaste planning gaat voor. Je status blijft zoals getoond.",
    unchecked: "Naar Verdi gestuurd, maar het resultaat kon niet gecontroleerd worden. De status op deze pagina toont wat geldt.",
    unclear: "Geen duidelijk antwoord. Kijk in Verdi of de wijziging gebeurd is.",
    sending: "Bezig met verzenden...",
    readiness: "Paraatheid",
    statistics: "Statistieken",
    since: "sinds",
    next: "Volgende",
    missing: "Ontbreekt",
    last: "laatst",
    now: "nu",
    loading: "Laden...",
    open_history: "geschiedenis openen",
    history: "Geschiedenis",
    train_complete: "Volledig",
    train_incomplete: "Onvolledig",
    today: "Vandaag",
    yesterday: "Gisteren",
    previous_day: "Vorige dag",
    next_day: "Volgende dag",
    history_empty: "Geen geschiedenis voor deze dag.",
    history_failed: "Geschiedenis is niet beschikbaar.",
    available: "Beschikbaar",
    preAlert: "Vooralarm",
    garrison: "Herbestaffing",
    problem_token: "Verdi-login verlopen. Controleer de Verdi Token Relay.",
    problem_paused: "Verdi vroeg om trager te gaan. Er wordt automatisch opnieuw geprobeerd.",
    problem_verdi: "Verdi is niet bereikbaar. Er wordt automatisch opnieuw geprobeerd.",
    problem_stale: "Sommige gegevens zijn mogelijk niet actueel. Er wordt automatisch opnieuw geprobeerd.",
  },
  fr: {
    myStatus: "Mon statut",
    vehicles: "Véhicules",
    personnel: "Personnes",
    until: "Jusqu'à",
    total: "Total",
    noData: "Pas de données",
    unknown: "Inconnu",
    empty: "Aucune donnée Verdi trouvée.",
    incomplete: "Liste incomplète",
    menu: "Menu",
    changeStatus: "Changer le statut",
    chooseStatus: "Choisissez un statut",
    status: "Statut",
    duration: "Durée",
    addException: "Ajouter exception",
    returnToPlanning: "Retour au planning",
    close: "Fermer",
    overruled: "Verdi a accepté, mais un planning fixe l'emporte. Votre statut reste celui affiché.",
    unchecked: "Envoyé à Verdi, mais le résultat n'a pas pu être vérifié. Le statut sur cette page indique ce qui s'applique.",
    unclear: "Pas de réponse claire. Vérifiez dans Verdi si la modification a été faite.",
    sending: "Envoi en cours...",
    readiness: "Disponibilité de départs",
    statistics: "Statistiques",
    since: "depuis",
    next: "Ensuite",
    missing: "Manquant",
    last: "dernier",
    now: "maintenant",
    loading: "Chargement...",
    open_history: "ouvrir l'historique",
    history: "Historique",
    train_complete: "Complet",
    train_incomplete: "Incomplet",
    today: "Aujourd'hui",
    yesterday: "Hier",
    previous_day: "Jour précédent",
    next_day: "Jour suivant",
    history_empty: "Pas d'historique pour ce jour.",
    history_failed: "L'historique n'est pas disponible.",
    available: "Disponible",
    preAlert: "Pré-alerte",
    garrison: "Effectif en caserne",
    problem_token: "Connexion Verdi expirée. Vérifiez Verdi Token Relay.",
    problem_paused: "Verdi a demandé de ralentir. Nouvel essai automatique.",
    problem_verdi: "Verdi est injoignable. Nouvel essai automatique.",
    problem_stale: "Certaines données peuvent ne pas être à jour. Nouvel essai automatique.",
  },
};

export function label(language, key) {
  const base = String(language ?? "").split("-")[0];
  return (LABELS[base] ?? LABELS.en)[key];
}

export function normalizeColor(value) {
  if (typeof value !== "string") return FALLBACK_COLOR;
  return /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(value) ? value : FALLBACK_COLOR;
}

function luminance(hex) {
  const digits = hex.slice(1);
  const full = digits.length === 3 ? [...digits].map((d) => d + d).join("") : digits;
  const [r, g, b] = [0, 2, 4]
    .map((i) => parseInt(full.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function textColor(hex) {
  const light = luminance(hex);
  return (light + 0.05) / 0.05 >= 1.05 / (light + 0.05) ? "#000000" : "#ffffff";
}

export function statusCounts(attributes) {
  const colors = attributes?.availability_colors ?? {};
  return Object.keys(colors)
    .map((name) => ({ name, color: colors[name], count: attributes[name] ?? 0 }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function statusText(language, state) {
  if (!state || state.state === "unavailable") return label(language, "noData");
  if (state.state === "unknown") return label(language, "unknown");
  return state.state;
}

export function statusLabel(language, name) {
  return name === "unknown" ? label(language, "unknown") : name;
}

function minutes(time) {
  const found = /^(\d+):(\d{2}):(\d{2})$/.exec(time ?? "");
  if (!found) return null;
  return Math.round(Number(found[1]) * 60 + Number(found[2]) + Number(found[3]) / 60);
}

export function responseTime(attributes) {
  const fast = minutes(attributes?.fastest_response_time);
  const slow = minutes(attributes?.slowest_response_time);
  if (fast === null && slow === null) return null;
  if (fast === null || slow === null || fast === slow) return `${fast ?? slow} min`;
  return `${fast}–${slow} min`;
}

export function missingPositions(positions) {
  return Object.entries(positions ?? {})
    .filter(([, met]) => !met)
    .map(([name]) => name);
}

function validDate(value) {
  const date = new Date(value);
  return !value || Number.isNaN(date.getTime()) ? null : date;
}

export function moment(value, language, now = new Date()) {
  const date = validDate(value);
  if (!date) return null;
  const clock = { hour: "2-digit", minute: "2-digit" };
  if (date.toDateString() === now.toDateString()) return date.toLocaleTimeString(language, clock);
  return date.toLocaleString(language, { day: "numeric", month: "numeric", ...clock });
}

export function dayMonth(value, language) {
  return validDate(value)?.toLocaleDateString(language, { day: "numeric", month: "numeric" }) ?? null;
}

function percent(value, language) {
  const text = Number(value).toLocaleString(language, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${text} %`;
}

function availabilityTile(state, language, nameStation) {
  const { station, years = {} } = state.attributes;
  const [newest, previous] = Object.keys(years).sort().reverse();
  const title = [label(language, "available"), newest, nameStation ? station : null].filter(Boolean).join(" ");
  const detail = previous ? `${previous}: ${percent(years[previous], language)}` : null;
  return { value: percent(state.state, language), title, detail };
}

export function statisticTile(state, language, nameStation) {
  if (!state || state.state === "unavailable" || state.state === "unknown") return null;
  const { service, last_called: called } = state.attributes;
  if (service === undefined) return availabilityTile(state, language, nameStation);
  const date = dayMonth(called, language);
  return { value: state.state, title: service, detail: date ? `${label(language, "last")} ${date}` : null };
}

export function barSegments(attributes) {
  return statusCounts(attributes).filter(({ count }) => count > 0);
}

export function unavailableIds(ids, states) {
  return ids.filter((id) => !states[id] || states[id].state === "unavailable");
}

export const REFRESH_GAP = 60000;

export function refreshDelay(last, now) {
  return Math.max(0, last + REFRESH_GAP - now);
}

export function vehicleName(friendlyName, title) {
  if (!friendlyName) return "?";
  return friendlyName.startsWith(`${title} `) ? friendlyName.slice(title.length + 1) : friendlyName;
}

export function dayStart(date, days = 0) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function dayLine(day, language, now = new Date()) {
  if (day.getTime() === dayStart(now).getTime()) return label(language, "today");
  if (day.getTime() === dayStart(now, -1).getTime()) return label(language, "yesterday");
  return day.toLocaleDateString(language, { weekday: "long", day: "numeric", month: "numeric" });
}

export function clockTime(value, language) {
  return new Date(value).toLocaleTimeString(language, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
}

export function vehicleRow(row) {
  return { status: row.s, color: normalizeColor(row.a?.color), tone: null, missing: [], since: row.a?.availability_since };
}

// A train has no colour from Verdi; `tone` is the page's own, the same as the train's dot.
export function trainRow(language) {
  return (row) => {
    const complete = row.s === "on";
    return {
      status: label(language, complete ? "train_complete" : "train_incomplete"),
      color: null,
      tone: complete ? "ok" : "short",
      missing: complete ? [] : missingPositions(row.a?.positions),
      since: null,
    };
  };
}

// HA's purge also removes an entity's newest row, so a status held longer than its limit has no row today. The live
// state is that status, held since last_changed (not last_updated: an attribute change doesn't end it).
export function liveRows(rows, state, today) {
  if (!today || rows?.length || !live(state)) return rows ?? [];
  const since = Date.parse(state.last_changed);
  if (!state.last_changed || Number.isNaN(since)) return [];
  return [{ s: state.state, a: state.attributes ?? {}, lu: since / 1000 }];
}

const NOTHING = { status: null, color: null, tone: null, missing: [], since: null };

function sameStatus(a, b) {
  return a.status === b.status && a.missing.join("\n") === b.missing.join("\n");
}

// Rows of HA's history command to periods, oldest first. dayEnd is the next midnight, or now for today.
export function historyPeriods(rows, dayStartTime, dayEnd, read) {
  const periods = [];
  let previous = -Infinity;
  for (const row of rows ?? []) {
    const time = row.lu * 1000;
    const meaning = row.s === "unavailable" || row.s === "unknown" ? NOTHING : read(row);
    const since = validDate(meaning.since)?.getTime();
    const chosen = since !== undefined && since <= time && since > previous ? since : time;
    const start = Math.min(Math.max(chosen, dayStartTime), dayEnd);
    previous = time;
    const last = periods.at(-1);
    if (last && sameStatus(last, meaning)) continue;
    if (last) last.end = start;
    else if (start > dayStartTime) periods.push({ ...NOTHING, start: dayStartTime, end: start });
    const { status, color, tone, missing } = meaning;
    periods.push({ start, end: dayEnd, status, color, tone, missing });
  }
  return periods
    .filter(({ start, end }) => end > start)
    .map(({ start, end, status, color, tone, missing }) => ({ start, end, status, color, tone, missing }));
}

// One row per status, also across a grey part; newest first.
export function historyList(periods) {
  const list = [];
  for (const period of periods) {
    if (period.status === null) continue;
    const last = list.at(-1);
    if (last && sameStatus(last, period)) last.end = period.end;
    else list.push({ ...period });
  }
  return list.reverse();
}

export function barParts(periods, day) {
  const start = day.getTime();
  const length = dayStart(day, 1).getTime() - start;
  return periods.map((period) => ({
    left: ((period.start - start) / length) * 100,
    width: ((period.end - period.start) / length) * 100,
    color: period.color,
    tone: period.tone,
  }));
}

export function dayTicks(day) {
  const start = day.getTime();
  const length = dayStart(day, 1).getTime() - start;
  return [0, 6, 12, 18, 24].map((hour) => {
    const time = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour).getTime();
    return { text: `${String(hour).padStart(2, "0")}:00`, left: ((time - start) / length) * 100 };
  });
}

export function periodTimes(period, day, end, today, language) {
  const start = clockTime(period.start, language);
  if (today && period.end === end) return `${start}–${label(language, "now")}`;
  if (period.end === dayStart(day, 1).getTime()) return `${start}–24:00`;
  return `${start}–${clockTime(period.end, language)}`;
}

export function entityIds(section) {
  const { controls } = section;
  return [
    section.my_availability,
    section.pre_alert,
    section.garrison,
    ...(section.readiness ?? []),
    ...section.vehicles,
    section.personnel,
    ...(section.statistics ?? []),
    controls?.status,
    controls?.duration,
    controls?.back_to_planning,
  ].filter(Boolean);
}

// "unknown" is fine: the Status select has that state whenever nothing is chosen.
export function canChange(controls, states) {
  if (!controls) return false;
  return [states[controls.status], states[controls.duration]].every(
    (state) => state && state.state !== "unavailable" && state.attributes.options?.length > 0,
  );
}

export function canReturn(controls, states) {
  const state = states[controls.back_to_planning];
  return Boolean(state) && state.state !== "unavailable";
}

export function startingDuration(state) {
  const { options } = state.attributes;
  return options.includes(state.state) ? state.state : options[0];
}

export function sendResult(answer) {
  const active = answer?.response?.active;
  if (active === true) return { close: true };
  return { close: false, label: active === false ? "overruled" : "unchecked", canRetry: false };
}

// These two may have changed something, so the dialog doesn't offer the same change again.
const MAYBE_SENT = ["outcome_unknown", "partly_ended"];

// A lost connection arrives as { error: { code, message } } and anything not Verdi's has no reason to translate.
export function sendError(err) {
  if (err?.translation_domain !== "verdi" || !err.translation_key) {
    return { close: false, label: "unclear", canRetry: false };
  }
  const exception = err.translation_key;
  return { close: false, exception, canRetry: !MAYBE_SENT.includes(exception) };
}

const STYLE = `
  :host { display: block; min-height: 100%; background: var(--primary-background-color); color: var(--primary-text-color); }
  header { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 8px;
    background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
  header h1 { margin: 0; font-size: 20px; font-weight: 400; }
  header button { width: 40px; height: 40px; padding: 8px; border: 0; background: none; color: inherit; cursor: pointer; }
  header svg { width: 24px; height: 24px; fill: currentColor; }
  main { container-type: inline-size; box-sizing: border-box; display: flex; flex-direction: column; gap: 12px;
    max-width: 1040px; margin: 0 auto; padding: 16px; }
  :host([narrow]) main { padding: 8px; }
  .numbers { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .columns, .column { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
  @container (min-width: 720px) {
    .columns { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); align-items: start; }
    .columns:has(> :only-child) { grid-template-columns: minmax(0, 1fr); }
    .numbers { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
  }
  h2 { margin: 24px 0 8px; font-size: 18px; font-weight: 500; }
  h2.station { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .gear { flex: none; width: 40px; height: 40px; padding: 8px; border: 0; background: none; color: inherit; cursor: pointer; }
  .gear svg { width: 24px; height: 24px; fill: currentColor; }
  header .gear { margin-left: auto; }
  h3 { margin: 16px 0 8px; font-size: 16px; font-weight: 500; }
  .block { display: flex; flex-direction: column; gap: 8px; min-width: 0; box-sizing: border-box; padding: 16px;
    border-radius: 12px; background: var(--card-background-color, #fff); }
  .block h3 { margin: 0; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; }
  .pills { display: flex; flex-wrap: wrap; gap: 8px; }
  .pill { display: inline-block; padding: 4px 12px; border: 1px solid var(--divider-color); border-radius: 16px; overflow-wrap: anywhere; }
  .pill.large { padding: 8px 16px; font-size: 18px; }
  .muted { color: var(--secondary-text-color); }
  h3.split { display: flex; justify-content: space-between; gap: 8px; }
  h3.split small { color: var(--secondary-text-color, #727272); font-size: 13px; font-weight: 400; }
  .until { flex: none; white-space: nowrap; }
  .tags { display: flex; align-items: center; gap: 6px; height: 24px; }
  .tag { flex: none; padding: 2px 8px; border: 1px solid var(--primary-color, #03a9f4); border-radius: 10px;
    color: var(--primary-color, #03a9f4); font-size: 12px; white-space: nowrap; }
  .next { min-height: 19px; font-size: 13px; }
  .trains { display: flex; flex-direction: column; }
  .train + .train { border-top: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .line { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 0; border: 0; background: none;
    color: inherit; font: inherit; text-align: left; }
  button.line { cursor: pointer; }
  .dot { flex: none; width: 10px; height: 10px; border-radius: 50%; background: ${FALLBACK_COLOR}; }
  .dot.ok { background: var(--success-color, #4caf50); }
  .dot.short { background: var(--error-color, #db4437); }
  .line .name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .line .time { flex: none; color: var(--secondary-text-color, #727272); font-size: 13px; }
  .chevron { flex: none; width: 8px; height: 8px; margin: 0 3px 3px; border-right: 2px solid var(--secondary-text-color, #727272);
    border-bottom: 2px solid var(--secondary-text-color, #727272); transform: rotate(45deg); }
  [aria-expanded="true"] .chevron { margin: 3px 3px 0; transform: rotate(-135deg); }
  .short-line { margin: -4px 0 8px 18px; color: var(--error-color, #db4437); font-size: 13px; overflow-wrap: anywhere; }
  .positions { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 2px 12px;
    margin: -2px 0 8px 18px; padding: 0; font-size: 13px; list-style: none; overflow-wrap: anywhere; }
  .positions li::before { content: "✓ "; color: var(--success-color, #4caf50); }
  .positions li.no { color: var(--error-color, #db4437); font-weight: 500; }
  .positions li.no::before { content: "✕ "; color: var(--error-color, #db4437); }
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 6px; }
  .tile { display: flex; flex-direction: column; align-items: stretch; gap: 2px; width: 100%; min-width: 0; min-height: 88px;
    box-sizing: border-box; padding: 9px; border: 0; border-radius: 10px; font: inherit; text-align: left; cursor: pointer;
    box-shadow: 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .tile.on { box-shadow: inset 0 0 0 3px currentColor, 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .tile ha-icon { --mdc-icon-size: 24px; }
  .tile strong { font-size: 16px; font-weight: 700; overflow-wrap: anywhere; }
  .tile span { font-size: 12px; overflow-wrap: anywhere; }
  .tile.border { border: 3px solid; outline: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); outline-offset: -1px;
    background: var(--secondary-background-color, #e5e5e5); color: var(--primary-text-color, #212121); }
  .vehicle-rows, .stat-rows { display: flex; flex-direction: column; }
  .vehicle-row { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 0; border: 0; background: none;
    color: inherit; font: inherit; text-align: left; cursor: pointer; }
  .vehicle-row .name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .vehicle-row .dot { box-shadow: 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { padding: 4px 12px; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); border-radius: 16px;
    background: none; color: inherit; font: inherit; overflow-wrap: anywhere; }
  button.chip { cursor: pointer; }
  .chip.ok { border-color: #2e7d32; background: #2e7d32; color: #fff; }
  .chip.short { border-color: #c62828; background: #c62828; color: #fff; }
  .tile:hover { filter: brightness(0.95); }
  .tile:focus-visible, .history-link:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .history-link { margin: -4px 0 8px 18px; padding: 0; border: 0; background: none; color: var(--primary-color, #03a9f4);
    font: inherit; font-size: 13px; text-decoration: underline; cursor: pointer; }
  .stack { display: flex; height: 14px; overflow: hidden; border-radius: 7px; }
  .stack span { box-shadow: inset 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; }
  .legend span { display: inline-flex; align-items: center; gap: 5px; overflow-wrap: anywhere; }
  .legend i { flex: none; width: 10px; height: 10px; border-radius: 3px; box-shadow: inset 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .number { min-width: 0; padding: 8px 10px; border-radius: 10px; background: var(--secondary-background-color, #e5e5e5); }
  .number strong { display: block; font-size: 22px; font-weight: 500; }
  .number span { display: block; font-size: 12px; overflow-wrap: anywhere; }
  .number span.muted { color: var(--secondary-text-color, #727272); }
  .problem { --problem-color: var(--error-color, #db4437); padding: 10px 12px; border: 1px solid var(--problem-color);
    border-radius: 12px; background: var(--card-background-color, #fff);
    background: color-mix(in srgb, var(--problem-color) 12%, var(--card-background-color, #fff));
    color: var(--problem-color); font-weight: 500; overflow-wrap: anywhere; }
  .problem.stale { --problem-color: var(--warning-color, #ffa600); color: var(--primary-text-color, #212121); }
  .view { display: contents; }
  button.pill { font: inherit; cursor: pointer; }
  dialog { box-sizing: border-box; width: min(420px, calc(100vw - 32px)); padding: 16px; border: 0; border-radius: 12px;
    background: var(--card-background-color); color: var(--primary-text-color); }
  dialog::backdrop { background: rgba(0, 0, 0, 0.5); }
  dialog:focus { outline: none; }
  dialog.history { margin-top: max(16px, 8vh); }
  dialog.history[open] { display: flex; flex-direction: column; }
  .history-body { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; }
  dialog h2 { margin: 0 0 16px; }
  .history-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; }
  .history-head h2 { margin: 0; min-width: 0; overflow-wrap: anywhere; }
  .pill .dot { display: inline-block; margin-right: 6px; }
  .days { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .days span { flex: 1; text-align: center; }
  .days button { min-width: 44px; min-height: 44px; padding: 4px 12px; font: inherit; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    border-radius: 8px; background: none; color: inherit; cursor: pointer; }
  .days button:disabled { opacity: 0.5; cursor: default; }
  .history-bar { position: relative; flex: none; height: 14px; overflow: hidden; border-radius: 7px;
    background: var(--secondary-background-color, #e5e5e5); }
  .history-bar span { position: absolute; top: 0; bottom: 0; min-width: 2px;
    box-shadow: inset 0 0 0 1px var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .history-bar .ok { background: var(--success-color, #4caf50); }
  .history-bar .short { background: var(--error-color, #db4437); }
  .history-bar .none { background: ${FALLBACK_COLOR}; }
  .ticks { position: relative; flex: none; height: 16px; margin-bottom: 12px; color: var(--secondary-text-color, #727272); font-size: 11px; }
  .ticks span { position: absolute; transform: translateX(-50%); }
  .ticks span:first-child { transform: none; }
  .ticks span:last-child { transform: translateX(-100%); }
  .changes { display: flex; flex-direction: column; flex: 0 1 auto; min-height: 0; gap: 6px; max-height: 40vh; margin: 0 0 12px; padding: 0; overflow-y: auto;
    list-style: none; }
  .changes li { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
  .changes time { flex: none; width: 96px; color: var(--secondary-text-color, #727272); font-size: 12px; }
  .changes .short-line { flex-basis: 100%; margin: 0; }
  .field { display: block; margin-bottom: 12px; }
  .field select { display: block; box-sizing: border-box; width: 100%; margin-top: 4px; padding: 8px; font: inherit;
    border: 1px solid var(--divider-color); border-radius: 8px; background: var(--card-background-color); color: inherit; }
  .message { margin-bottom: 12px; overflow-wrap: anywhere; }
  .message:empty { display: none; }
  .actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
  .actions button { padding: 8px 12px; font: inherit; border: 1px solid var(--divider-color); border-radius: 8px;
    background: none; color: inherit; cursor: pointer; }
  .actions button:disabled { opacity: 0.5; cursor: default; }
`;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pill(text, color, large = false, tag = "span") {
  const node = element(tag, large ? "pill large" : "pill", text);
  const background = normalizeColor(color);
  node.style.background = background;
  node.style.color = textColor(background);
  return node;
}

function changePill(text, color, language, change) {
  const node = pill(text, color, true, "button");
  node.type = "button";
  node.setAttribute("aria-haspopup", "dialog");
  node.setAttribute("aria-label", `${label(language, "changeStatus")}: ${text}`);
  node.addEventListener("click", change);
  return node;
}

function row(name, ...right) {
  const node = element("div", "row");
  node.append(element("span", "", name), ...right);
  return node;
}

export function until(end, language, now = new Date()) {
  const text = moment(end, language, now);
  return text ? `${label(language, "until")} ${text}` : null;
}

function live(state) {
  return Boolean(state) && state.state !== "unavailable" && state.state !== "unknown";
}

function heading(language, key) {
  return element("h3", "", label(language, key));
}

function tagsRow(data, states, language) {
  const row = element("div", "tags");
  for (const [key, text] of [["pre_alert", "preAlert"], ["garrison", "garrison"]]) {
    if (states[data[key]]?.state === "on") row.append(element("span", "tag", label(language, text)));
  }
  return row;
}

function myStatus({ data, states, language, open }) {
  if (!data.my_availability) return null;
  const state = states[data.my_availability];
  const change = canChange(data.controls, states) ? () => open(data) : null;
  const block = element("div", "block");
  block.append(heading(language, "myStatus"));
  const attributes = state?.attributes ?? {};
  const colors = attributes.availability_colors ?? {};
  const main = element("div", "row");
  const text = statusText(language, state);
  const color = live(state) ? attributes.color : null;
  const status = change ? changePill(text, color, language, change) : pill(text, color, true);
  if (change) status.dataset.entry = data.controls.entry_id;
  main.append(status);
  const end = until(attributes.end, language);
  if (end) main.append(element("span", "muted until", end));
  const following = live(state) && attributes.next_status;
  block.append(
    main,
    tagsRow(data, states, language),
    element("div", "muted next", following ? `${label(language, "next")}: ${following}` : ""),
  );
  for (const group of [attributes.stations, attributes.planning_groups]) {
    for (const [name, status] of Object.entries(group ?? {})) {
      block.append(row(name, pill(status ?? label(language, "unknown"), colors[status])));
    }
  }
  return block;
}

function trainDetail(id, name, state, language, opened, history) {
  const known = live(state);
  const attributes = known ? state.attributes : {};
  const positions = Object.entries(attributes.positions ?? {});
  if (opened && positions.length) {
    const list = element("ul", "positions");
    for (const [position, met] of positions) list.append(element("li", met ? "" : "no", position));
    const more = element("button", "history-link", label(language, "history"));
    more.type = "button";
    more.dataset.history = id;
    more.setAttribute("aria-haspopup", "dialog");
    more.addEventListener("click", () => history(id, name, true));
    return [list, more];
  }
  const missing = known && state.state !== "on" ? missingPositions(attributes.positions) : [];
  if (!missing.length) return [];
  return [element("div", "short-line", `${label(language, "missing")}: ${missing.join(", ")}`)];
}

function trainChip(id, name, state, opened, toggle) {
  const known = live(state);
  const positions = Object.keys(known ? (state.attributes.positions ?? {}) : {});
  const tone = known ? (state.state === "on" ? "ok" : "short") : "";
  const chip = element(positions.length ? "button" : "span", `chip ${tone}`, name);
  if (positions.length) {
    chip.type = "button";
    chip.dataset.train = id;
    chip.setAttribute("aria-expanded", String(opened));
    chip.addEventListener("click", () => toggle(id));
  }
  return chip;
}

function train(id, name, state, language, opened, toggle, history) {
  const known = live(state);
  const attributes = known ? state.attributes : {};
  const positions = Object.entries(attributes.positions ?? {});
  const node = element("div", "train");
  const line = element(positions.length ? "button" : "div", "line");
  if (positions.length) {
    line.type = "button";
    line.dataset.train = id;
    line.setAttribute("aria-expanded", String(opened));
    line.addEventListener("click", () => toggle(id));
  }
  const complete = state?.state === "on";
  line.append(
    element("span", known ? `dot ${complete ? "ok" : "short"}` : "dot"),
    element("span", "name", name),
    element("span", "time", responseTime(attributes) ?? ""),
  );
  if (positions.length) line.append(element("span", "chevron"));
  node.append(line, ...trainDetail(id, name, state, language, opened, history));
  return node;
}

function readiness({ data, states, language, opened, toggle, history, view }) {
  if (!data.readiness?.length) return null;
  const block = element("div", "block");
  const named = data.readiness.map((id) => {
    const attributes = states[id]?.attributes ?? {};
    return { id, name: attributes.title ?? vehicleName(attributes.friendly_name, data.title) };
  });
  block.append(heading(language, "readiness"));
  if (view === "chips") {
    const chips = element("div", "chips");
    for (const { id, name } of named) chips.append(trainChip(id, name, states[id], opened.has(id), toggle));
    block.append(chips);
    for (const { id, name } of named) {
      if (opened.has(id)) block.append(element("strong", "", name), ...trainDetail(id, name, states[id], language, true, history));
    }
    return block;
  }
  const list = element("div", "trains");
  for (const { id, name } of named) list.append(train(id, name, states[id], language, opened.has(id), toggle, history));
  block.append(list);
  return block;
}

function vehicleIcon(icon) {
  if (!globalThis.customElements?.get("ha-icon")) return null;
  const node = document.createElement("ha-icon");
  node.setAttribute("icon", icon ?? VEHICLE_ICON);
  return node;
}

function vehicleTile(id, state, title, language, history, view) {
  const known = live(state);
  const attributes = state?.attributes ?? {};
  const color = normalizeColor(known ? attributes.color : null);
  const node = element("button", `tile${view === "border" ? " border" : ""}${known && attributes.on_intervention ? " on" : ""}`);
  node.type = "button";
  node.dataset.vehicle = id;
  node.setAttribute("aria-haspopup", "dialog");
  if (view === "border") {
    node.style.borderColor = color;
  } else {
    node.style.background = color;
    node.style.color = textColor(color);
  }
  const name = vehicleName(attributes.friendly_name, title);
  const status = statusText(language, state);
  node.setAttribute("aria-label", `${name}, ${status}, ${label(language, "open_history")}`);
  node.addEventListener("click", () => history(id, name, false));
  const icon = vehicleIcon(attributes.icon);
  if (icon) node.append(icon);
  node.append(element("strong", "", name));
  node.append(element("span", "", status));
  const since = known ? moment(attributes.availability_since, language) : null;
  if (since) node.append(element("span", "", `${label(language, "since")} ${since}`));
  return node;
}

function vehicleListRow(id, state, title, language, history) {
  const known = live(state);
  const attributes = state?.attributes ?? {};
  const node = element("button", "vehicle-row");
  node.type = "button";
  node.dataset.vehicle = id;
  node.setAttribute("aria-haspopup", "dialog");
  const name = vehicleName(attributes.friendly_name, title);
  const status = statusText(language, state);
  node.setAttribute("aria-label", `${name}, ${status}, ${label(language, "open_history")}`);
  node.addEventListener("click", () => history(id, name, false));
  const dot = element("span", "dot");
  dot.style.background = normalizeColor(known ? attributes.color : null);
  node.append(dot, element("span", "name", name), element("span", "muted", status));
  return node;
}

function vehicles({ data, states, language, history, view }) {
  if (!data.vehicles.length) return null;
  const block = element("div", "block");
  const list = element("div", view === "list" ? "vehicle-rows" : "tiles");
  for (const id of data.vehicles) {
    const draw = view === "list" ? vehicleListRow : vehicleTile;
    list.append(draw(id, states[id], data.title, language, history, view));
  }
  block.append(heading(language, "vehicles"), list);
  return block;
}

function personnel({ data, states, language, view }) {
  if (!data.personnel) return null;
  const state = states[data.personnel];
  const block = element("div", "block");
  if (!live(state)) {
    const pills = element("div", "pills");
    pills.append(pill(statusText(language, state), null));
    block.append(heading(language, "personnel"), pills);
    return block;
  }
  const title = element("h3", "split");
  const total = `${state.state} ${label(language, "total").toLowerCase()}`;
  title.append(element("span", "", label(language, "personnel")), element("small", "", total));
  const counts = statusCounts(state.attributes).map(({ name, color, count }) => ({
    text: `${statusLabel(language, name)} ${count}`,
    color: normalizeColor(color),
  }));
  if (view === "pills") {
    const pills = element("div", "pills");
    for (const { text, color } of counts) pills.append(pill(text, color));
    block.append(title, pills);
  } else {
    const bar = element("div", "stack");
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", counts.map(({ text }) => text).join(", "));
    for (const { color, count } of barSegments(state.attributes)) {
      const segment = element("span");
      segment.style.flex = String(count);
      segment.style.background = normalizeColor(color);
      bar.append(segment);
    }
    const legend = element("div", "legend");
    for (const { text, color } of counts) {
      const item = element("span");
      const square = element("i");
      square.style.background = color;
      item.append(square, text);
      legend.append(item);
    }
    block.append(title, bar, legend);
  }
  if (state.attributes.truncated) block.append(element("div", "muted", label(language, "incomplete")));
  return block;
}

function statistics({ data, states, language, view }) {
  const ids = data.statistics ?? [];
  const availability = ids.filter((id) => states[id]?.attributes.service === undefined);
  const tiles = ids.map((id) => statisticTile(states[id], language, availability.length > 1)).filter(Boolean);
  if (!tiles.length) return null;
  const block = element("div", "block");
  const numbers = element("div", view === "rows" ? "stat-rows" : "numbers");
  for (const { value, title, detail } of tiles) {
    if (view === "rows") {
      numbers.append(row(detail ? `${title} (${detail})` : title, element("strong", "", value)));
      continue;
    }
    const node = element("div", "number");
    node.append(element("strong", "", value), element("span", "", title));
    if (detail) node.append(element("span", "muted", detail));
    numbers.append(node);
  }
  block.append(heading(language, "statistics"), numbers);
  return block;
}

const BLOCK_DRAWERS = { myStatus, readiness, vehicles, personnel, statistics };

function drawBlock(context, layout, name) {
  return BLOCK_DRAWERS[name]({ ...context, view: layout.blocks[name].view });
}

function drawColumn(context, layout, names) {
  const column = element("div", "column");
  column.append(...names.map((name) => drawBlock(context, layout, name)).filter(Boolean));
  return column;
}

function section(context, withHeading) {
  const { data, language, set, wide } = context;
  const nodes = [];
  if (withHeading) {
    const title = element("h2", "station", data.title);
    title.append(context.gear(data));
    nodes.push(title);
  }
  if (data.problem) {
    const line = element("div", `problem ${data.problem}`, label(language, `problem_${data.problem}`));
    line.setAttribute("role", "alert");
    nodes.push(line);
  }
  const layout = settings.resolve(set);
  for (const row of settings.rows(layout, wide)) {
    if (row.full) {
      const block = drawBlock(context, layout, row.full);
      if (block) nodes.push(block);
      continue;
    }
    const columns = element("div", "columns");
    for (const names of [row.left, row.right]) {
      const column = drawColumn(context, layout, names);
      if (column.childElementCount) columns.append(column);
    }
    if (columns.childElementCount) nodes.push(columns);
  }
  return nodes;
}

function iconButton(path, title) {
  const button = element("button");
  button.type = "button";
  button.setAttribute("aria-label", title);
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  const shape = document.createElementNS("http://www.w3.org/2000/svg", "path");
  shape.setAttribute("d", path);
  icon.append(shape);
  button.append(icon);
  return button;
}

function gearButton(data, language, open) {
  const button = iconButton(GEAR_ICON, `${settings.settingsLabel(language, "settings")}: ${data.title}`);
  button.classList.add("gear");
  button.dataset.settings = data.entry_id;
  button.setAttribute("aria-haspopup", "dialog");
  button.addEventListener("click", () => open(data));
  return button;
}

function menuButton(host, language) {
  const button = iconButton(MENU_ICON, label(language, "menu"));
  // HA decides what this does: the drawer on a phone, collapse or expand on a wide screen.
  button.addEventListener("click", () =>
    host.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true })),
  );
  return button;
}

function selectField(title, options, value) {
  const select = element("select");
  for (const option of options) {
    const node = element("option", "", option.label);
    node.value = option.value;
    select.append(node);
  }
  select.value = value;
  const field = element("label", "field", title);
  field.append(select);
  return { field, select };
}

function actionButton(language, key) {
  const node = element("button", "", label(language, key));
  node.type = "button";
  return node;
}

function tonePill(text, tone) {
  const node = element("span", "pill");
  node.append(element("span", `dot ${tone}`), element("span", "", text));
  return node;
}

function periodPill(period) {
  return period.tone ? tonePill(period.status, period.tone) : pill(period.status, period.color);
}

function currentPill(state, language, train) {
  if (!live(state)) return pill(statusText(language, state), null);
  if (train) return periodPill(trainRow(language)({ s: state.state }));
  return pill(state.state, state.attributes.color);
}

function historyBody(periods, day, end, today, language) {
  const list = historyList(periods);
  if (!list.length) return [element("div", "message", label(language, "history_empty"))];
  const bar = element("div", "history-bar");
  bar.setAttribute("aria-hidden", "true"); // the list says the same
  // Last first, so an earlier part paints over the next one and keeps its min-width.
  for (const { left, width, color, tone } of barParts(periods, day).reverse()) {
    const part = element("span", tone ?? (color ? "" : "none"));
    part.style.left = `${left}%`;
    part.style.width = `${width}%`;
    if (color) part.style.background = color;
    bar.append(part);
  }
  const ticks = element("div", "ticks");
  ticks.setAttribute("aria-hidden", "true");
  for (const { text, left } of dayTicks(day)) {
    const tick = element("span", "", text);
    tick.style.left = `${left}%`;
    ticks.append(tick);
  }
  const changes = element("ul", "changes");
  for (const period of list) {
    const item = element("li");
    item.append(element("time", "", periodTimes(period, day, end, today, language)), periodPill(period));
    if (period.missing.length) {
      item.append(element("div", "short-line", `${label(language, "missing")}: ${period.missing.join(", ")}`));
    }
    changes.append(item);
  }
  return [bar, ticks, changes];
}

function definePanel() {
  class VerdiPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = undefined;
      this._sections = undefined;
      this._drawn = undefined;
      this._drafts = new Map();
      this._wide = undefined;
      this._resize = new ResizeObserver(() => this._measure());
      this._sending = false;
      this._openTrains = new Set();
      this._unavailable = "";
      this._loadedAt = 0;
      this._timer = undefined;
      this._historyCall = 0;
      this._historyTarget = undefined;
      this._settingsTarget = undefined;
      // `ha-icon` may arrive after the first drawing.
      customElements.whenDefined("ha-icon").then(() => {
        this._drawn = undefined;
        this._render();
      });
      // Outside what _render replaces: taking a modal dialog out of the page closes it.
      this._view = element("div", "view");
      this._dialog = element("dialog");
      this._dialog.tabIndex = -1;
      // HA's keyboard shortcuts listen on the window; typing in a select isn't for them. Escape is the browser's,
      // except while a call runs.
      this._dialog.addEventListener("keydown", (event) => {
        event.stopPropagation();
        if (event.key === "Escape" && this._sending) event.preventDefault();
      });
      this._dialog.addEventListener("cancel", (event) => {
        if (this._sending) event.preventDefault();
        else if (this._settingsTarget) this._drafts.delete(this._settingsTarget);
      });
      // The pill or tile the browser would return focus to has been replaced by a redraw, so hand it to the current one.
      this._dialog.addEventListener("close", () => {
        this._historyCall += 1; // an answer still on its way has nowhere to go
        this._dialog.classList.remove("history");
        this._dialog.classList.remove("settings");
        const gear = this._settingsTarget;
        this._settingsTarget = undefined;
        this._dialog.replaceChildren();
        const target = this._historyTarget;
        this._historyTarget = undefined;
        // The draft is gone by now, so the page goes back to what's stored. Before the focus check, which can return.
        if (gear) {
          this._drawn = undefined;
          this._render();
        }
        const active = this.shadowRoot.activeElement;
        if (active && active !== this._dialog) return;
        if (gear) this._view.querySelector(`[data-settings="${gear}"]`)?.focus();
        else (target ? this._historyButton(target) : this._pill(this._opened))?.focus();
      });
      this.shadowRoot.append(element("style", "", STYLE + settings.SETTINGS_STYLE), this._view, this._dialog);
    }

    connectedCallback() {
      this._resize.observe(this);
      if (this._hass) this._arm();
    }

    disconnectedCallback() {
      this._resize.disconnect();
      clearTimeout(this._timer);
      this._dialog.close();
    }

    _measure() {
      const wide = settings.isWide(this.clientWidth, this.hasAttribute("narrow"));
      if (wide === this._wide) return;
      this._wide = wide;
      this._drawn = undefined;
      this._render();
    }

    _setOf(data) {
      const sets = this._drafts.get(data.entry_id) ?? data.settings;
      return sets?.[this._wide ? "wide" : "phone"];
    }

    _pill(entryId) {
      return [...this._view.querySelectorAll("button.pill")].find((node) => node.dataset.entry === entryId);
    }

    _toggle(id) {
      if (!this._openTrains.delete(id)) this._openTrains.add(id);
      this._drawn = undefined;
      this._render();
    }

    // The next ask, at most once a minute. One timer only: this replaces any earlier one. A detached page has none.
    _arm() {
      clearTimeout(this._timer);
      if (this.isConnected) this._timer = setTimeout(() => this._load(), refreshDelay(this._loadedAt, Date.now()));
    }

    // Why data is missing comes from the server, so ask again when what's missing changes.
    _check(ids) {
      const key = unavailableIds(ids, this._hass.states).join(",");
      if (key === this._unavailable) return;
      this._unavailable = key;
      this._arm();
    }

    set narrow(value) {
      this.toggleAttribute("narrow", Boolean(value));
      if (this._hass) this._measure();
    }

    set hass(hass) {
      const reload = !this._hass || hass.entities !== this._hass.entities;
      this._hass = hass;
      if (reload) this._load();
      this._render();
    }

    // One local call, no Verdi call. Asked every minute, because why data is missing can change without an entity
    // changing. _render still runs each time, so the page notices a new day.
    async _load() {
      this._loadedAt = Date.now();
      try {
        const { sections } = await this._hass.callWS({ type: "verdi/status_page" });
        // A redraw replaces the buttons, so one every minute would lose a press that spans it.
        if (JSON.stringify(sections) !== JSON.stringify(this._sections)) this._drawn = undefined;
        this._sections = sections;
      } catch (err) {
        console.error("verdi/status_page failed", err);
      } finally {
        this._arm();
      }
      this._render();
    }

    _render() {
      const hass = this._hass;
      if (!hass) return;
      const sections = this._sections ?? [];
      this._wide ??= settings.isWide(this.clientWidth, this.hasAttribute("narrow"));
      const ids = sections.flatMap(entityIds);
      this._check(ids);
      const states = ids.map((id) => hass.states[id]);
      const drawn = this._drawn;
      const day = new Date().toDateString(); // "sinds 23:10" needs its date after midnight
      if (
        drawn?.language === hass.language &&
        drawn.day === day &&
        drawn.states.length === states.length &&
        states.every((state, i) => state === drawn.states[i])
      ) {
        return;
      }
      this._drawn = { language: hass.language, day, states };
      const language = hass.language;
      const header = element("header");
      header.append(menuButton(this, language), element("h1", "", "Verdi (unofficial)"));
      const main = element("main");
      const withHeading = sections.length > 1;
      const open = (data) => this._open(data);
      const toggle = (id) => this._toggle(id);
      const history = (id, name, train) => this._openHistory(id, name, train);
      const gear = (data) => gearButton(data, language, (target) => this._openSettings(target));
      if (sections.length === 1) header.append(gear(sections[0]));
      const shared = { states: hass.states, language, open, opened: this._openTrains, toggle, history, gear, wide: this._wide };
      for (const data of sections) main.append(...section({ ...shared, data, set: this._setOf(data) }, withHeading));
      if (this._sections && !this._sections.length) main.append(element("div", "muted", label(language, "empty")));
      const active = this.shadowRoot.activeElement?.dataset ?? {};
      this._view.replaceChildren(header, main);
      if (active.entry) this._pill(active.entry)?.focus({ preventScroll: true });
      if (active.train) this._trainButton(active.train)?.focus({ preventScroll: true });
      const target = active.vehicle ?? active.history;
      if (target) this._historyButton(target)?.focus({ preventScroll: true });
      if (active.settings) this._view.querySelector(`[data-settings="${active.settings}"]`)?.focus({ preventScroll: true });
    }

    _openSettings(data) {
      if (!this.isConnected || this._sending || this._dialog.open) return;
      const language = this._hass.language;
      this._settingsTarget = data.entry_id;
      this._dialog.classList.add("settings");
      this._dialog.setAttribute("aria-label", `${settings.settingsLabel(language, "settings")}: ${data.title}`);
      settings.drawSettings(this._dialog, {
        language,
        title: data.title,
        names: Object.fromEntries(settings.BLOCKS.map((name) => [name, label(language, name)])),
        current: this._wide ? "wide" : "phone",
        fine: matchMedia("(pointer: fine)").matches,
        draft: data.settings ?? {},
        actions: {
          change: (next) => {
            this._drafts.set(data.entry_id, next);
            this._drawn = undefined;
            this._render();
          },
          cancel: () => {
            this._drafts.delete(data.entry_id);
            this._dialog.close();
          },
          save: (next, edited) => this._saveSettings(data.entry_id, next, edited),
        },
      });
      this._dialog.showModal();
    }

    async _saveSettings(entryId, draft, edited) {
      this._sending = true;
      const sets = Object.fromEntries(edited.map((key) => [key, draft[key]]));
      try {
        await this._hass.callWS({ type: "verdi/save_page_settings", entry_id: entryId, ...sets });
      } catch (err) {
        console.error("verdi/save_page_settings failed", err);
        return false;
      } finally {
        this._sending = false;
      }
      // The sections may be newer than the ones the dialog opened with.
      for (const data of this._sections ?? []) {
        if (data.entry_id === entryId) data.settings = { ...data.settings, ...sets };
      }
      this._drafts.delete(entryId);
      this._dialog.close();
      return true;
    }

    _trainButton(id) {
      return [...this._view.querySelectorAll("[data-train]")].find((node) => node.dataset.train === id);
    }

    _historyButton(id) {
      return [...this._view.querySelectorAll("[data-vehicle], [data-history]")].find(
        (node) => node.dataset.vehicle === id || node.dataset.history === id,
      );
    }

    _openHistory(id, name, train) {
      if (!this.isConnected || this._sending || this._dialog.open) return;
      const hass = this._hass;
      const language = hass.language;
      this._historyTarget = id;
      this._dialog.setAttribute("aria-label", `${name}: ${label(language, "history")}`);
      const head = element("div", "history-head");
      head.append(element("h2", "", name), currentPill(hass.states[id], language, train));
      const arrow = (text, key) => {
        const node = element("button", "", text);
        node.type = "button";
        node.setAttribute("aria-label", label(language, key));
        return node;
      };
      const back = arrow("‹", "previous_day");
      const next = arrow("›", "next_day");
      const line = element("span");
      line.setAttribute("aria-live", "polite"); // the day is read after each arrow; the body would read "Loading..." too
      const days = element("div", "days");
      days.append(back, line, next);
      const body = element("div", "history-body");
      const close = actionButton(language, "close");
      close.addEventListener("click", () => this._dialog.close());
      const actions = element("div", "actions");
      actions.append(close);
      const view = { id, train, language, day: dayStart(new Date()), oldest: null, back, next, line, body };
      const step = (count) => {
        view.day = dayStart(view.day, count);
        this._historyDay(view);
      };
      back.addEventListener("click", () => step(-1));
      next.addEventListener("click", () => step(1));
      this._dialog.replaceChildren(head, days, body, actions);
      this._dialog.classList.add("history");
      this._dialog.showModal();
      this._historyDay(view);
    }

    // An arrow that turns off loses focus to body, where the dialog no longer sees Escape. The other arrow takes it.
    _historyArrows({ back, next, day, oldest }) {
      const active = this.shadowRoot.activeElement;
      back.disabled = oldest !== null && day.getTime() <= oldest;
      next.disabled = day.getTime() >= dayStart(new Date()).getTime();
      if (active !== back && active !== next) return;
      if (!active.disabled) return;
      const other = active === back ? next : back;
      (other.disabled ? this._dialog : other).focus();
    }

    // One local call, no Verdi call. Only the newest request may fill the dialog.
    async _historyDay(view) {
      this._historyCall += 1;
      const call = this._historyCall;
      const now = new Date();
      const { id, train, language, day, body } = view;
      const today = day.getTime() === dayStart(now).getTime();
      const end = today ? now : dayStart(day, 1);
      view.line.textContent = dayLine(day, language, now);
      this._historyArrows(view);
      body.replaceChildren(element("div", "message", label(language, "loading")));
      let rows;
      try {
        const answer = await this._hass.callWS({
          type: "history/history_during_period",
          start_time: day.toISOString(),
          end_time: end.toISOString(),
          entity_ids: [id],
          include_start_time_state: true,
          significant_changes_only: !train, // which position is missing is only in a train's attributes
          minimal_response: false,
          no_attributes: false,
        });
        rows = answer[id] ?? [];
      } catch {
        if (call === this._historyCall) body.replaceChildren(element("div", "message", label(language, "history_failed")));
        return;
      }
      if (call !== this._historyCall) return;
      if (!rows.length) {
        view.oldest = day.getTime(); // HA has nothing older either
        this._historyArrows(view);
      }
      rows = liveRows(rows, this._hass.states[id], today);
      const periods = historyPeriods(rows, day.getTime(), end.getTime(), train ? trainRow(language) : vehicleRow);
      body.replaceChildren(...historyBody(periods, day, end.getTime(), today, language));
    }

    async _reason(err) {
      try {
        const localize = await this._hass.loadBackendTranslation("exceptions", "verdi");
        const text = localize(`component.verdi.exceptions.${err.translation_key}.message`, err.translation_placeholders);
        if (text) return text;
      } catch {
        // The English text below is still the reason.
      }
      return err.message;
    }

    async _open(data) {
      try {
        await this._hass.loadBackendTranslation("entity", "verdi");
      } catch {
        // The duration labels fall back to their keys.
      }
      const { controls } = data;
      this._opened = controls.entry_id;
      const hass = this._hass;
      // Again after the await: a call may be running, a second click may have opened it, or the select may have gone.
      if (!this.isConnected || this._sending || this._dialog.open || !canChange(controls, hass.states)) return;
      const language = hass.language;
      this._dialog.setAttribute("aria-label", label(language, "changeStatus"));
      const statusOptions = hass.states[controls.status].attributes.options.map((name) => ({ value: name, label: name }));
      const status = selectField(
        label(language, "status"),
        [{ value: "", label: label(language, "chooseStatus") }, ...statusOptions],
        "",
      );
      const durationState = hass.states[controls.duration];
      const duration = selectField(
        label(language, "duration"),
        durationState.attributes.options.map((key) => ({ value: key, label: hass.formatEntityState(durationState, key) })),
        startingDuration(durationState),
      );
      const add = actionButton(language, "addException");
      const back = actionButton(language, "returnToPlanning");
      const close = actionButton(language, "close");
      const message = element("div", "message");
      message.setAttribute("role", "alert");
      const actions = element("div", "actions");
      if (canReturn(controls, hass.states)) actions.append(back);
      actions.append(close, add);

      add.disabled = true;
      status.select.addEventListener("change", () => {
        add.disabled = !status.select.value;
      });

      const send = async (call) => {
        this._sending = true;
        message.textContent = label(language, "sending");
        for (const node of [add, back, close, status.select, duration.select]) node.disabled = true;
        // Disabling them drops focus to body, where the dialog no longer sees Escape or HA's shortcuts get the keys.
        this._dialog.focus();
        let outcome;
        let reason;
        try {
          try {
            outcome = await call();
          } catch (err) {
            outcome = sendError(err);
            if (outcome.exception) reason = await this._reason(err);
          }
        } finally {
          this._sending = false;
          close.disabled = false;
        }
        if (outcome.close) {
          this._dialog.close();
          return;
        }
        message.textContent = reason ?? label(language, outcome.label);
        // The selects stay locked after "only Close": the change may have gone through.
        if (outcome.canRetry) {
          status.select.disabled = false;
          duration.select.disabled = false;
          add.disabled = !status.select.value;
          back.disabled = false;
        }
      };

      add.addEventListener("click", () =>
        send(async () =>
          sendResult(
            await this._hass.callService(
              "verdi",
              "add_exception",
              { config_entry_id: controls.entry_id, status: status.select.value, duration: duration.select.value },
              undefined,
              false,
              true,
            ),
          ),
        ),
      );
      back.addEventListener("click", () =>
        send(async () => {
          await this._hass.callService("verdi", "return_to_planning", { config_entry_id: controls.entry_id }, undefined, false);
          return { close: true };
        }),
      );
      close.addEventListener("click", () => this._dialog.close());

      this._dialog.replaceChildren(
        element("h2", "", label(language, "changeStatus")),
        status.field,
        duration.field,
        message,
        actions,
      );
      this._dialog.showModal();
    }
  }
  customElements.define("verdi-panel", VerdiPanel);
}

// Node, in the tests, has no customElements. A second load must not throw.
if (globalThis.customElements && !customElements.get("verdi-panel")) definePanel();
