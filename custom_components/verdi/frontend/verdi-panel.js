// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 jertech and contributors
// Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
// The Verdi status page: current status in the colours Verdi sends. One file on purpose: a second
// module would be imported without the version in the URL and could stay cached after an update.

export const FALLBACK_COLOR = "#D3D3D3";

const MENU_ICON = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";
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
    available: "Available",
    preAlert: "Pre-alert",
    garrison: "Garrison",
    problem_token: "Verdi login expired. Check the Verdi Token Relay.",
    problem_paused: "Verdi asked to slow down. It will retry by itself.",
    problem_verdi: "Verdi can't be reached. It will retry by itself.",
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
    available: "Beschikbaar",
    preAlert: "Vooralarm",
    garrison: "Herbestaffing",
    problem_token: "Verdi-login verlopen. Controleer de Verdi Token Relay.",
    problem_paused: "Verdi vroeg om trager te gaan. Er wordt automatisch opnieuw geprobeerd.",
    problem_verdi: "Verdi is niet bereikbaar. Er wordt automatisch opnieuw geprobeerd.",
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
    available: "Disponible",
    preAlert: "Pré-alerte",
    garrison: "Effectif en caserne",
    problem_token: "Connexion Verdi expirée. Vérifiez Verdi Token Relay.",
    problem_paused: "Verdi a demandé de ralentir. Nouvel essai automatique.",
    problem_verdi: "Verdi est injoignable. Nouvel essai automatique.",
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
  h3 { margin: 16px 0 8px; font-size: 16px; font-weight: 500; }
  .block { display: flex; flex-direction: column; gap: 8px; min-width: 0; box-sizing: border-box; padding: 16px;
    border-radius: 12px; background: var(--card-background-color); }
  .block h3 { margin: 0; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; }
  .pills { display: flex; flex-wrap: wrap; gap: 8px; }
  .pill { display: inline-block; padding: 4px 12px; border: 1px solid var(--divider-color); border-radius: 16px; overflow-wrap: anywhere; }
  .pill.large { padding: 8px 16px; font-size: 18px; }
  .muted { color: var(--secondary-text-color); }
  h3.split { display: flex; justify-content: space-between; gap: 8px; }
  h3.split small { color: var(--secondary-text-color); font-size: 13px; font-weight: 400; }
  .until { flex: none; white-space: nowrap; }
  .tags { display: flex; align-items: center; gap: 6px; height: 24px; }
  .tag { flex: none; padding: 2px 8px; border: 1px solid var(--primary-color); border-radius: 10px;
    color: var(--primary-color); font-size: 12px; white-space: nowrap; }
  .next { min-height: 19px; font-size: 13px; }
  .trains { display: flex; flex-direction: column; }
  .train + .train { border-top: 1px solid var(--divider-color); }
  .line { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 0; border: 0; background: none;
    color: inherit; font: inherit; text-align: left; }
  button.line { cursor: pointer; }
  .dot { flex: none; width: 10px; height: 10px; border-radius: 50%; background: ${FALLBACK_COLOR}; }
  .dot.ok { background: var(--success-color, #4caf50); }
  .dot.short { background: var(--error-color, #db4437); }
  .line .name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .line .time { flex: none; color: var(--secondary-text-color); font-size: 13px; }
  .chevron { flex: none; width: 8px; height: 8px; margin: 0 3px 3px; border-right: 2px solid var(--secondary-text-color);
    border-bottom: 2px solid var(--secondary-text-color); transform: rotate(45deg); }
  [aria-expanded="true"] .chevron { margin: 3px 3px 0; transform: rotate(-135deg); }
  .short-line { margin: -4px 0 8px 18px; color: var(--error-color, #db4437); font-size: 13px; overflow-wrap: anywhere; }
  .positions { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 2px 12px;
    margin: -2px 0 8px 18px; padding: 0; font-size: 13px; list-style: none; overflow-wrap: anywhere; }
  .positions li::before { content: "✓ "; color: var(--success-color, #4caf50); }
  .positions li.no { color: var(--error-color, #db4437); font-weight: 500; }
  .positions li.no::before { content: "✕ "; color: var(--error-color, #db4437); }
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 6px; }
  .tile { display: flex; flex-direction: column; gap: 2px; min-width: 0; min-height: 88px; box-sizing: border-box;
    padding: 9px; border-radius: 10px; box-shadow: 0 0 0 1px var(--divider-color); }
  .tile.on { box-shadow: inset 0 0 0 3px currentColor, 0 0 0 1px var(--divider-color); }
  .tile ha-icon { --mdc-icon-size: 24px; }
  .tile strong { font-size: 16px; font-weight: 700; overflow-wrap: anywhere; }
  .tile span { font-size: 12px; overflow-wrap: anywhere; }
  .stack { display: flex; height: 14px; overflow: hidden; border-radius: 7px; }
  .stack span { box-shadow: inset 0 0 0 1px var(--divider-color); }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; }
  .legend span { display: inline-flex; align-items: center; gap: 5px; overflow-wrap: anywhere; }
  .legend i { flex: none; width: 10px; height: 10px; border-radius: 3px; box-shadow: inset 0 0 0 1px var(--divider-color); }
  .number { min-width: 0; padding: 8px 10px; border-radius: 10px; background: var(--secondary-background-color); }
  .number strong { display: block; font-size: 22px; font-weight: 500; }
  .number span { display: block; font-size: 12px; overflow-wrap: anywhere; }
  .number span.muted { color: var(--secondary-text-color); }
  .problem { padding: 10px 12px; border: 1px solid var(--error-color, #db4437); border-radius: 12px;
    background: var(--card-background-color);
    background: color-mix(in srgb, var(--error-color, #db4437) 12%, var(--card-background-color));
    color: var(--error-color, #db4437); font-weight: 500; overflow-wrap: anywhere; }
  .view { display: contents; }
  button.pill { font: inherit; cursor: pointer; }
  dialog { box-sizing: border-box; width: min(420px, calc(100vw - 32px)); padding: 16px; border: 0; border-radius: 12px;
    background: var(--card-background-color); color: var(--primary-text-color); }
  dialog::backdrop { background: rgba(0, 0, 0, 0.5); }
  dialog:focus { outline: none; }
  dialog h2 { margin: 0 0 16px; }
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

function until(end, language) {
  const date = new Date(end);
  if (!end || Number.isNaN(date.getTime())) return null;
  const text = date.toLocaleString(language, { dateStyle: "short", timeStyle: "short" });
  return `${label(language, "until")} ${text}`;
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

function train(id, name, state, language, opened, toggle) {
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
  node.append(line);
  const missing = known && !complete ? missingPositions(attributes.positions) : [];
  if (opened && positions.length) {
    const list = element("ul", "positions");
    for (const [name, met] of positions) list.append(element("li", met ? "" : "no", name));
    node.append(list);
  } else if (missing.length) {
    node.append(element("div", "short-line", `${label(language, "missing")}: ${missing.join(", ")}`));
  }
  return node;
}

function readiness({ data, states, language, opened, toggle }) {
  if (!data.readiness?.length) return null;
  const block = element("div", "block");
  const list = element("div", "trains");
  for (const id of data.readiness) {
    const attributes = states[id]?.attributes ?? {};
    const name = attributes.title ?? vehicleName(attributes.friendly_name, data.title);
    list.append(train(id, name, states[id], language, opened.has(id), toggle));
  }
  block.append(heading(language, "readiness"), list);
  return block;
}

function vehicleIcon(icon) {
  if (!globalThis.customElements?.get("ha-icon")) return null;
  const node = document.createElement("ha-icon");
  node.setAttribute("icon", icon ?? VEHICLE_ICON);
  return node;
}

function vehicleTile(state, title, language) {
  const known = live(state);
  const attributes = state?.attributes ?? {};
  const background = normalizeColor(known ? attributes.color : null);
  const node = element("div", known && attributes.on_intervention ? "tile on" : "tile");
  node.style.background = background;
  node.style.color = textColor(background);
  const icon = vehicleIcon(attributes.icon);
  if (icon) node.append(icon);
  node.append(element("strong", "", vehicleName(attributes.friendly_name, title)));
  node.append(element("span", "", statusText(language, state)));
  const since = known ? moment(attributes.availability_since, language) : null;
  if (since) node.append(element("span", "", `${label(language, "since")} ${since}`));
  return node;
}

function vehicles({ data, states, language }) {
  if (!data.vehicles.length) return null;
  const block = element("div", "block");
  const tiles = element("div", "tiles");
  for (const id of data.vehicles) tiles.append(vehicleTile(states[id], data.title, language));
  block.append(heading(language, "vehicles"), tiles);
  return block;
}

function personnel({ data, states, language }) {
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
  if (state.attributes.truncated) block.append(element("div", "muted", label(language, "incomplete")));
  return block;
}

function statistics({ data, states, language }) {
  const ids = data.statistics ?? [];
  const availability = ids.filter((id) => states[id]?.attributes.service === undefined);
  const tiles = ids.map((id) => statisticTile(states[id], language, availability.length > 1)).filter(Boolean);
  if (!tiles.length) return null;
  const block = element("div", "block");
  const numbers = element("div", "numbers");
  for (const { value, title, detail } of tiles) {
    const node = element("div", "number");
    node.append(element("strong", "", value), element("span", "", title));
    if (detail) node.append(element("span", "muted", detail));
    numbers.append(node);
  }
  block.append(heading(language, "statistics"), numbers);
  return block;
}

// The later settings reorder, hide and restyle blocks here.
const BLOCKS = { myStatus, readiness, vehicles, personnel, statistics };
const COLUMNS = [
  ["myStatus", "readiness"],
  ["vehicles", "personnel"],
];
const FULL_WIDTH = ["statistics"];

function section(context, withHeading) {
  const { data, language } = context;
  const nodes = [];
  if (withHeading) nodes.push(element("h2", "", data.title));
  if (data.problem) {
    const line = element("div", "problem", label(language, `problem_${data.problem}`));
    line.setAttribute("role", "alert");
    nodes.push(line);
  }
  const columns = element("div", "columns");
  for (const names of COLUMNS) {
    const column = element("div", "column");
    column.append(...names.map((name) => BLOCKS[name](context)).filter(Boolean));
    if (column.childElementCount) columns.append(column);
  }
  if (columns.childElementCount) nodes.push(columns);
  nodes.push(...FULL_WIDTH.map((name) => BLOCKS[name](context)).filter(Boolean));
  return nodes;
}

function menuButton(host, language) {
  const button = element("button");
  button.type = "button";
  button.setAttribute("aria-label", label(language, "menu"));
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", MENU_ICON);
  icon.append(path);
  button.append(icon);
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

function definePanel() {
  class VerdiPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = undefined;
      this._sections = undefined;
      this._drawn = undefined;
      this._sending = false;
      this._openTrains = new Set();
      this._unavailable = "";
      this._loadedAt = 0;
      this._timer = undefined;
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
      });
      // The pill the browser would return focus to has been replaced by a redraw, so hand it to the current one.
      this._dialog.addEventListener("close", () => {
        this._dialog.replaceChildren();
        const active = this.shadowRoot.activeElement;
        if (!active || active === this._dialog) this._pill(this._opened)?.focus();
      });
      this.shadowRoot.append(element("style", "", STYLE), this._view, this._dialog);
    }

    disconnectedCallback() {
      clearTimeout(this._timer);
      this._dialog.close();
    }

    _pill(entryId) {
      return [...this._view.querySelectorAll("button.pill")].find((node) => node.dataset.entry === entryId);
    }

    _toggle(id) {
      if (!this._openTrains.delete(id)) this._openTrains.add(id);
      this._drawn = undefined;
      this._render();
    }

    // Why data is missing comes from the server, so ask again when what's missing changes.
    _check(ids) {
      const key = unavailableIds(ids, this._hass.states).join(",");
      if (key === this._unavailable) return;
      this._unavailable = key;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._load(), refreshDelay(this._loadedAt, Date.now()));
    }

    set narrow(value) {
      this.toggleAttribute("narrow", Boolean(value));
    }

    set hass(hass) {
      const reload = !this._hass || hass.entities !== this._hass.entities;
      this._hass = hass;
      if (reload) this._load();
      this._render();
    }

    async _load() {
      this._loadedAt = Date.now();
      try {
        const { sections } = await this._hass.callWS({ type: "verdi/status_page" });
        this._sections = sections;
      } catch (err) {
        console.error("verdi/status_page failed", err);
      }
      this._drawn = undefined;
      this._render();
    }

    _render() {
      const hass = this._hass;
      if (!hass) return;
      const sections = this._sections ?? [];
      const ids = sections.flatMap(entityIds);
      this._check(ids);
      const states = ids.map((id) => hass.states[id]);
      const drawn = this._drawn;
      if (
        drawn?.language === hass.language &&
        drawn.states.length === states.length &&
        states.every((state, i) => state === drawn.states[i])
      ) {
        return;
      }
      this._drawn = { language: hass.language, states };
      const language = hass.language;
      const header = element("header");
      header.append(menuButton(this, language), element("h1", "", "Verdi (unofficial)"));
      const main = element("main");
      const withHeading = sections.length > 1;
      const open = (data) => this._open(data);
      const toggle = (id) => this._toggle(id);
      const shared = { states: hass.states, language, open, opened: this._openTrains, toggle };
      for (const data of sections) main.append(...section({ ...shared, data }, withHeading));
      if (this._sections && !this._sections.length) main.append(element("div", "muted", label(language, "empty")));
      const active = this.shadowRoot.activeElement?.dataset ?? {};
      this._view.replaceChildren(header, main);
      if (active.entry) this._pill(active.entry)?.focus();
      if (active.train) this._trainButton(active.train)?.focus();
    }

    _trainButton(id) {
      return [...this._view.querySelectorAll("button.line")].find((node) => node.dataset.train === id);
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
