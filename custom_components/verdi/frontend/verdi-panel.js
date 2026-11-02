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

export function vehicleName(friendlyName, title) {
  if (!friendlyName) return "?";
  return friendlyName.startsWith(`${title} `) ? friendlyName.slice(title.length + 1) : friendlyName;
}

export function entityIds(section) {
  return [section.my_availability, ...section.vehicles, section.personnel].filter(Boolean);
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
`;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pill(text, color, large = false) {
  const node = element("span", large ? "pill large" : "pill", text);
  const background = normalizeColor(color);
  node.style.background = background;
  node.style.color = textColor(background);
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

function myStatus(state, language) {
  const block = element("div", "block");
  block.append(element("h3", "", label(language, "myStatus")));
  const attributes = state?.attributes ?? {};
  const colors = attributes.availability_colors ?? {};
  const main = element("div", "row");
  main.append(pill(statusText(language, state), live(state) ? attributes.color : null, true));
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
  rows.sort((a, b) => a.name.localeCompare(b.name));
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

function section(data, states, language, heading) {
  const nodes = [];
  if (heading) nodes.push(element("h2", "", data.title));
  if (data.my_availability) nodes.push(myStatus(states[data.my_availability], language));
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

function definePanel() {
  class VerdiPanel extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._hass = undefined;
      this._sections = undefined;
      this._drawn = undefined;
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
      for (const data of sections) main.append(...section(data, hass.states, language, heading));
      if (this._sections && !this._sections.length) main.append(element("div", "muted", label(language, "empty")));
      const style = element("style", "", STYLE);
      this.shadowRoot.replaceChildren(style, header, main);
    }
  }
  customElements.define("verdi-panel", VerdiPanel);
}

// Node, in the tests, has no customElements. A second load must not throw.
if (globalThis.customElements && !customElements.get("verdi-panel")) definePanel();
