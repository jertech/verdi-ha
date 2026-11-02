// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 jertech and contributors
// Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
// The Verdi status page: current status in the colours Verdi sends. One file on purpose: a second
// module would be imported without the version in the URL and could stay cached after an update.

export const FALLBACK_COLOR = "#D3D3D3";

const MENU_ICON = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";

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
  main { max-width: 760px; margin: 0 auto; padding: 16px; }
  :host([narrow]) main { padding: 8px; }
  h2 { margin: 24px 0 8px; font-size: 18px; font-weight: 500; }
  h3 { margin: 16px 0 8px; font-size: 16px; font-weight: 500; }
  .block { margin-bottom: 16px; padding: 16px; border-radius: 12px; background: var(--card-background-color); }
  .block h3:first-child { margin-top: 0; }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 0; }
  .pills { display: flex; flex-wrap: wrap; gap: 8px; }
  .pill { display: inline-block; padding: 4px 12px; border: 1px solid var(--divider-color); border-radius: 16px; overflow-wrap: anywhere; }
  .pill.large { padding: 8px 16px; font-size: 18px; }
  .muted { color: var(--secondary-text-color); }
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

function myStatus(state, language, change) {
  const block = element("div", "block");
  block.append(element("h3", "", label(language, "myStatus")));
  const attributes = state?.attributes ?? {};
  const colors = attributes.availability_colors ?? {};
  const main = element("div", "row");
  const text = statusText(language, state);
  const color = live(state) ? attributes.color : null;
  main.append(change ? changePill(text, color, language, change) : pill(text, color, true));
  const end = until(attributes.end, language);
  if (end) main.append(element("span", "muted", end));
  block.append(main);
  for (const group of [attributes.stations, attributes.planning_groups]) {
    for (const [name, status] of Object.entries(group ?? {})) {
      block.append(row(name, pill(status ?? label(language, "unknown"), colors[status])));
    }
  }
  return block;
}

function vehicles(ids, states, title, language) {
  const block = element("div", "block");
  block.append(element("h3", "", label(language, "vehicles")));
  const rows = ids.map((id) => ({ state: states[id], name: vehicleName(states[id]?.attributes.friendly_name, title) }));
  for (const { state, name } of rows) {
    block.append(row(name, pill(statusText(language, state), live(state) ? state.attributes.color : null)));
  }
  return block;
}

function personnel(state, language) {
  const block = element("div", "block");
  block.append(element("h3", "", label(language, "personnel")));
  if (!live(state)) {
    const pills = element("div", "pills");
    pills.append(pill(statusText(language, state), null));
    block.append(pills);
    return block;
  }
  const pills = element("div", "pills");
  for (const { name, color, count } of statusCounts(state.attributes)) {
    pills.append(pill(`${statusLabel(language, name)}: ${count}`, color));
  }
  block.append(pills, row(label(language, "total"), element("span", "", state.state)));
  if (state.attributes.truncated) block.append(element("div", "muted", label(language, "incomplete")));
  return block;
}

function section(data, states, language, heading, open) {
  const nodes = [];
  if (heading) nodes.push(element("h2", "", data.title));
  if (data.my_availability) {
    const change = canChange(data.controls, states) ? () => open(data) : null;
    const block = myStatus(states[data.my_availability], language, change);
    const button = block.querySelector("button.pill");
    if (button) button.dataset.entry = data.controls.entry_id;
    nodes.push(block);
  }
  if (data.vehicles.length) nodes.push(vehicles(data.vehicles, states, data.title, language));
  if (data.personnel) nodes.push(personnel(states[data.personnel], language));
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
      this._dialog.close();
    }

    _pill(entryId) {
      return [...this._view.querySelectorAll("button.pill")].find((node) => node.dataset.entry === entryId);
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
      const states = sections.flatMap(entityIds).map((id) => hass.states[id]);
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
      const heading = sections.length > 1;
      const open = (data) => this._open(data);
      for (const data of sections) main.append(...section(data, hass.states, language, heading, open));
      if (this._sections && !this._sections.length) main.append(element("div", "muted", label(language, "empty")));
      const focused = this.shadowRoot.activeElement?.dataset?.entry;
      this._view.replaceChildren(header, main);
      if (focused) this._pill(focused)?.focus();
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
