// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 jertech and contributors
// Additional terms under GPL section 7 apply; see ADDITIONAL_TERMS.md.
// The status page's settings: the presets, the layout worked out from a stored set, and the dialog.
// verdi-panel.js imports this with its own ?v= query, so an update isn't stuck in the browser's cache.

export const BLOCKS = ["myStatus", "readiness", "vehicles", "personnel", "statistics"];
export const VIEWS = {
  vehicles: ["tiles", "border", "list"],
  readiness: ["lines", "chips"],
  personnel: ["bar", "pills"],
  statistics: ["numbers", "rows"],
};
export const PLACES = ["left", "right", "full"];
const WIDE_FROM = 720;
const PAGE_WIDTH = 1040;

const LEADING = ["myStatus", "vehicles", "readiness", "personnel", "statistics"];
const everywhere = (views) =>
  Object.fromEntries(BLOCKS.map((name) => [name, { shown: true, place: "full", view: views[name] }]));

export const PRESETS = {
  overzicht: {
    order: [...BLOCKS],
    blocks: {
      myStatus: { shown: true, place: "left" },
      readiness: { shown: true, place: "left", view: "lines" },
      vehicles: { shown: true, place: "right", view: "tiles" },
      personnel: { shown: true, place: "right", view: "bar" },
      statistics: { shown: true, place: "full", view: "numbers" },
    },
  },
  bord: {
    order: LEADING,
    blocks: everywhere({ vehicles: "tiles", readiness: "chips", personnel: "bar", statistics: "numbers" }),
  },
  lijst: {
    order: LEADING,
    blocks: everywhere({ vehicles: "list", readiness: "lines", personnel: "bar", statistics: "rows" }),
  },
};

const isObject = (value) => typeof value === "object" && value !== null && !Array.isArray(value);
const presetName = (set) => (Object.hasOwn(PRESETS, set?.preset) ? set.preset : "overzicht");

function resolvedOrder(preset, changes) {
  const stored = Array.isArray(changes.order) ? changes.order : [];
  const known = [...new Set(stored.filter((name) => BLOCKS.includes(name)))];
  return [...known, ...preset.order.filter((name) => !known.includes(name))];
}

function resolvedBlock(name, base, stored) {
  const block = { ...base };
  if (!isObject(stored)) return block;
  if (typeof stored.shown === "boolean") block.shown = stored.shown;
  if (PLACES.includes(stored.place)) block.place = stored.place;
  if (VIEWS[name]?.includes(stored.view)) block.view = stored.view;
  return block;
}

/** What to draw for a stored set. Stored data isn't trusted: anything unknown takes the preset's value. */
export function resolve(set) {
  const name = presetName(set);
  const preset = PRESETS[name];
  const changes = isObject(set?.changes) ? set.changes : {};
  const stored = isObject(changes.blocks) ? changes.blocks : {};
  const blocks = Object.fromEntries(
    BLOCKS.map((block) => [block, resolvedBlock(block, preset.blocks[block], stored[block])]),
  );
  if (!BLOCKS.some((block) => blocks[block].shown)) blocks[preset.order[0]].shown = true;
  return { preset: name, order: resolvedOrder(preset, changes), blocks };
}

/** The page's rows: `{ left, right }` columns, or `{ full }`. A phone is one column. */
export function rows(layout, wide) {
  const visible = layout.order.filter((name) => layout.blocks[name].shown);
  if (!wide) return [{ left: visible, right: [] }];
  const result = [];
  let current = null;
  for (const name of visible) {
    const { place } = layout.blocks[name];
    if (place === "full") {
      current = null;
      result.push({ full: name });
      continue;
    }
    if (!current) {
      current = { left: [], right: [] };
      result.push(current);
    }
    current[place].push(name);
  }
  return result;
}

export function isCustom(set) {
  return Object.keys(set?.changes ?? {}).length > 0;
}

export function setPreset(set, preset) {
  return { preset, changes: {} };
}

/** Only real differences are stored, so a value back at the preset's clears Aangepast by itself. */
export function setOption(set, name, field, value) {
  const preset = PRESETS[presetName(set)];
  const { blocks: storedBlocks, ...changes } = isObject(set.changes) ? set.changes : {};
  const block = { ...storedBlocks?.[name], [field]: value };
  if (preset.blocks[name][field] === value) delete block[field];
  const blocks = { ...storedBlocks, [name]: block };
  if (!Object.keys(block).length) delete blocks[name];
  if (Object.keys(blocks).length) changes.blocks = blocks;
  return { ...set, changes };
}

function withOrder(set, order) {
  const preset = PRESETS[presetName(set)];
  const { order: _, ...changes } = isObject(set.changes) ? set.changes : {};
  if (order.join() !== preset.order.join()) changes.order = order;
  return { ...set, changes };
}

export function moveBlock(set, name, step) {
  const order = [...resolve(set).order];
  const from = order.indexOf(name);
  const to = from + step;
  if (to < 0 || to >= order.length) return set;
  [order[from], order[to]] = [order[to], order[from]];
  return withOrder(set, order);
}

export function moveBefore(set, name, target) {
  const order = resolve(set).order.filter((block) => block !== name);
  order.splice(order.indexOf(target), 0, name);
  return withOrder(set, order);
}

export function moveAfter(set, name, target) {
  const order = resolve(set).order.filter((block) => block !== name);
  order.splice(order.indexOf(target) + 1, 0, name);
  return withOrder(set, order);
}

export function canHide(set, name) {
  const { blocks } = resolve(set);
  return BLOCKS.some((block) => block !== name && blocks[block].shown);
}

/** The same line as the CSS's `@container (min-width: 720px)`: main's width without its padding. */
export function isWide(hostWidth, narrow) {
  return Math.min(hostWidth, PAGE_WIDTH) - (narrow ? 16 : 32) >= WIDE_FROM;
}

export const SETTINGS_LABELS = {
  en: {
    settings: "Page settings",
    settingsFor: "Set up for",
    phone: "Phone",
    wide: "Wide",
    preset: "Preset",
    overzicht: "Overview",
    bord: "Board",
    lijst: "List",
    aangepast: "Custom",
    blocks: "Blocks",
    dragHint: "Drag to reorder",
    arrowHint: "Use the arrows to reorder",
    show: "Show",
    lastBlock: "One block always stays visible.",
    moveUp: "Move up",
    moveDown: "Move down",
    placeLeft: "Left",
    placeRight: "Right",
    placeFull: "Full width",
    viewTiles: "Colour tiles",
    viewBorder: "Tiles with a coloured border",
    viewList: "List",
    viewLines: "Lines",
    viewChips: "Chips",
    viewBar: "Bar",
    viewPills: "Pills",
    viewNumbers: "Separate numbers",
    viewRows: "Rows",
    resetTo: "Reset to {preset}",
    cancel: "Cancel",
    save: "Save",
    otherWidth: "This set isn't shown on this screen.",
    saveFailed: "Couldn't save. Your choice stays until you close this page.",
  },
  nl: {
    settings: "Pagina-instellingen",
    settingsFor: "Instellen voor",
    phone: "Telefoon",
    wide: "Breed",
    preset: "Voorinstelling",
    overzicht: "Overzicht",
    bord: "Bord",
    lijst: "Lijst",
    aangepast: "Aangepast",
    blocks: "Blokken",
    dragHint: "Sleep om de volgorde te wijzigen",
    arrowHint: "Gebruik de pijlen om de volgorde te wijzigen",
    show: "Tonen",
    lastBlock: "Eén blok blijft altijd zichtbaar.",
    moveUp: "Omhoog",
    moveDown: "Omlaag",
    placeLeft: "Links",
    placeRight: "Rechts",
    placeFull: "Volledige breedte",
    viewTiles: "Kleurtegels",
    viewBorder: "Tegels met gekleurde rand",
    viewList: "Lijst",
    viewLines: "Regels",
    viewChips: "Chips",
    viewBar: "Balk",
    viewPills: "Pillen",
    viewNumbers: "Losse cijfers",
    viewRows: "Rijen",
    resetTo: "Terug naar {preset}",
    cancel: "Annuleren",
    save: "Opslaan",
    otherWidth: "Deze set is op dit scherm niet te zien.",
    saveFailed: "Opslaan is mislukt. Je keuze blijft staan tot je deze pagina sluit.",
  },
  fr: {
    settings: "Paramètres de la page",
    settingsFor: "Configurer pour",
    phone: "Téléphone",
    wide: "Large",
    preset: "Préréglage",
    overzicht: "Vue d'ensemble",
    bord: "Tableau",
    lijst: "Liste",
    aangepast: "Personnalisé",
    blocks: "Blocs",
    dragHint: "Faites glisser pour réorganiser",
    arrowHint: "Utilisez les flèches pour réorganiser",
    show: "Afficher",
    lastBlock: "Un bloc reste toujours visible.",
    moveUp: "Monter",
    moveDown: "Descendre",
    placeLeft: "Gauche",
    placeRight: "Droite",
    placeFull: "Pleine largeur",
    viewTiles: "Tuiles colorées",
    viewBorder: "Tuiles à bordure colorée",
    viewList: "Liste",
    viewLines: "Lignes",
    viewChips: "Pastilles",
    viewBar: "Barre",
    viewPills: "Pilules",
    viewNumbers: "Chiffres séparés",
    viewRows: "Rangées",
    resetTo: "Revenir à {preset}",
    cancel: "Annuler",
    save: "Enregistrer",
    otherWidth: "Cet ensemble n'est pas affiché sur cet écran.",
    saveFailed: "Enregistrement impossible. Votre choix reste jusqu'à la fermeture de cette page.",
  },
};

export function settingsLabel(language, key) {
  const base = String(language ?? "").split("-")[0];
  return (SETTINGS_LABELS[base] ?? SETTINGS_LABELS.en)[key];
}

function node(tag, className = "", text = "") {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text) item.textContent = text;
  return item;
}

function button(text, className, onClick) {
  const item = node("button", className, text);
  item.type = "button";
  item.addEventListener("click", onClick);
  return item;
}

function segmented(title, key, choices, current, onPick) {
  const group = node("div", "segments");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", title);
  for (const { value, text, disabled } of choices) {
    const item = button(text, "segment", () => onPick(value));
    item.dataset.focus = `${key}:${value}`;
    item.disabled = Boolean(disabled);
    item.setAttribute("aria-pressed", String(value === current));
    group.append(item);
  }
  return group;
}

const capitalised = (text) => text[0].toUpperCase() + text.slice(1);

function viewSelect(language, title, name, value, onPick) {
  const select = node("select");
  select.dataset.focus = `view:${name}`;
  select.setAttribute("aria-label", title);
  for (const view of VIEWS[name]) {
    const option = node("option", "", settingsLabel(language, `view${capitalised(view)}`));
    option.value = view;
    select.append(option);
  }
  select.value = value;
  select.addEventListener("change", () => onPick(select.value));
  return select;
}

function blockRow(state, name, index, last) {
  const { language, names, set, layout, change, fine, width } = state;
  const block = layout.blocks[name];
  const line = node("div", "setting");
  line.dataset.block = name;
  if (fine) {
    // Not a button: Firefox doesn't start a drag on one.
    const handle = node("span", "handle", "⋮⋮");
    handle.tabIndex = 0;
    handle.setAttribute("role", "button");
    handle.dataset.focus = `handle:${name}`;
    handle.setAttribute("aria-label", `${names[name]}: ${settingsLabel(language, "dragHint")}`);
    handle.addEventListener("keydown", (event) => {
      const step = { ArrowUp: -1, ArrowDown: 1 }[event.key];
      if (!step) return;
      event.preventDefault();
      change(moveBlock(set, name, step));
    });
    line.draggable = true;
    line.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", name));
    line.addEventListener("dragover", (event) => event.preventDefault());
    line.addEventListener("drop", (event) => {
      event.preventDefault();
      const dragged = event.dataTransfer.getData("text/plain");
      if (!BLOCKS.includes(dragged) || dragged === name) return;
      const { top, height } = line.getBoundingClientRect();
      change((event.clientY < top + height / 2 ? moveBefore : moveAfter)(set, dragged, name));
    });
    line.append(handle);
  }
  const shown = node("input");
  shown.type = "checkbox";
  shown.dataset.focus = `shown:${name}`;
  shown.checked = block.shown;
  shown.disabled = block.shown && !canHide(set, name);
  shown.setAttribute("aria-label", `${settingsLabel(language, "show")}: ${names[name]}`);
  shown.addEventListener("change", () => change(setOption(set, name, "shown", shown.checked)));
  line.append(shown, node("span", "block-name", names[name]));
  if (VIEWS[name]) {
    line.append(viewSelect(language, names[name], name, block.view, (view) => change(setOption(set, name, "view", view))));
  }
  if (width === "wide") {
    const places = PLACES.map((value) => ({
      value,
      text: settingsLabel(language, `place${capitalised(value)}`),
    }));
    line.append(
      segmented(names[name], `place:${name}`, places, block.place, (value) => change(setOption(set, name, "place", value))),
    );
  }
  if (!fine) {
    const up = button("↑", "arrow", () => change(moveBlock(set, name, -1), `up:${name}`));
    up.dataset.focus = `up:${name}`;
    up.setAttribute("aria-label", `${names[name]}: ${settingsLabel(language, "moveUp")}`);
    up.disabled = index === 0;
    const down = button("↓", "arrow", () => change(moveBlock(set, name, 1), `down:${name}`));
    down.dataset.focus = `down:${name}`;
    down.setAttribute("aria-label", `${names[name]}: ${settingsLabel(language, "moveDown")}`);
    down.disabled = index === last;
    line.append(up, down);
  }
  return line;
}

const PRESET_DEFAULT = { preset: "overzicht", changes: {} };

/**
 * Fills the page's dialog. `actions` are `change(draft)`, `save(draft)` and `cancel()`; `save` returns a promise.
 * The dialog owns nothing but what's on screen: the page keeps the draft, so a redraw of the page can't touch it.
 */
export function drawSettings(dialog, options) {
  const { language, title, names, current, fine, actions } = options;
  let width = current;
  let failed = false;
  const draft = { wide: options.draft.wide ?? PRESET_DEFAULT, phone: options.draft.phone ?? PRESET_DEFAULT };
  const edited = new Set();

  const enabled = (key) => dialog.querySelector(`[data-focus="${key}"]:not(:disabled)`);
  // An arrow at the end of the list turns off, so focus crosses to its block's other arrow.
  const otherArrow = (key) => key.replace(/^(up|down):/, (_, way) => `${way === "up" ? "down" : "up"}:`);

  // Drawing replaces every control, so the one in use is found again by its key. A tap doesn't focus a button on every
  // browser, so an arrow names itself.
  const redraw = (focusKey = dialog.getRootNode().activeElement?.dataset.focus) => {
    const set = draft[width];
    const layout = resolve(set);
    const change = (next, focus) => {
      draft[width] = next;
      edited.add(width);
      failed = false;
      actions.change({ ...draft }, [...edited]);
      redraw(focus);
    };
    const sets = ["phone", "wide"].map((value) => ({ value, text: settingsLabel(language, value) }));
    const presets = Object.keys(PRESETS).map((value) => ({ value, text: settingsLabel(language, value) }));
    const custom = isCustom(set);
    presets.push({ value: "aangepast", text: settingsLabel(language, "aangepast"), disabled: true });
    const list = node("div", "settings-blocks");
    layout.order.forEach((name, index) => {
      const state = { language, names, set, layout, change, fine, width };
      list.append(blockRow(state, name, index, layout.order.length - 1));
    });
    const reset = button(
      settingsLabel(language, "resetTo").replace("{preset}", settingsLabel(language, layout.preset)),
      "",
      () => change(setPreset(set, layout.preset)),
    );
    reset.dataset.focus = "reset";
    reset.disabled = !custom;
    const cancel = button(settingsLabel(language, "cancel"), "", () => actions.cancel());
    cancel.dataset.focus = "cancel";
    const save = button(settingsLabel(language, "save"), "primary", async () => {
      // Nothing here can be used while it runs. A disabled control drops focus to body, where the dialog sees no Escape.
      dialog.focus();
      for (const control of dialog.querySelectorAll("button, input, select")) control.disabled = true;
      for (const handle of dialog.querySelectorAll(".handle")) handle.removeAttribute("tabindex");
      for (const line of dialog.querySelectorAll(".setting")) line.draggable = false;
      failed = !(await actions.save({ ...draft }, [...edited]));
      if (failed) redraw("save");
    });
    save.dataset.focus = "save";
    const heading = node("div", "settings-title");
    const close = button("✕", "close", () => actions.cancel());
    close.dataset.focus = "close";
    close.setAttribute("aria-label", settingsLabel(language, "cancel"));
    heading.append(node("h2", "", `${settingsLabel(language, "settings")}: ${title}`), close);
    const children = [
      heading,
      node("div", "settings-label", settingsLabel(language, "settingsFor")),
      segmented(settingsLabel(language, "settingsFor"), "width", sets, width, (value) => {
        width = value;
        redraw();
      }),
      node("div", "settings-label", settingsLabel(language, "preset")),
      segmented(settingsLabel(language, "preset"), "preset", presets, custom ? "aangepast" : layout.preset, (value) =>
        change(setPreset(set, value)),
      ),
    ];
    if (width !== current) children.push(node("div", "muted", settingsLabel(language, "otherWidth")));
    children.push(
      node("div", "settings-label", settingsLabel(language, "blocks")),
      node("div", "muted", settingsLabel(language, fine ? "dragHint" : "arrowHint")),
      list,
    );
    if (layout.order.filter((name) => layout.blocks[name].shown).length === 1) {
      children.push(node("div", "muted", settingsLabel(language, "lastBlock")));
    }
    if (failed) {
      const line = node("div", "message", settingsLabel(language, "saveFailed"));
      line.setAttribute("role", "alert");
      children.push(line);
    }
    const actionRow = node("div", "settings-actions");
    actionRow.append(reset, node("span", "grow"), cancel, save);
    children.push(actionRow);
    dialog.replaceChildren(...children);
    if (focusKey) (enabled(focusKey) ?? enabled(otherArrow(focusKey)) ?? dialog).focus();
  };
  redraw();
}

export const SETTINGS_STYLE = `
  dialog.settings { width: min(640px, 100%); max-width: 100%; }
  dialog.settings .settings-label { margin-top: 12px; color: var(--secondary-text-color, #727272); font-size: 13px; }
  .segments { display: flex; flex-wrap: wrap; overflow: hidden; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    border-radius: 8px; }
  .segment { flex: 1 1 auto; padding: 6px 10px; border: 0; background: none; color: inherit; font: inherit; cursor: pointer; }
  .segment[aria-pressed="true"] { background: color-mix(in srgb, var(--primary-color, #03a9f4) 20%, var(--card-background-color, #fff));
    box-shadow: inset 0 0 0 2px var(--primary-color, #03a9f4); color: var(--primary-text-color, #212121); }
  .segment:focus-visible { outline: 2px solid var(--primary-text-color, #212121); outline-offset: -4px; }
  .segment:disabled { cursor: default; }
  .segment:disabled:not([aria-pressed="true"]) { color: var(--secondary-text-color, #727272); }
  .settings-blocks { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
  .setting { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 6px 8px;
    border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); border-radius: 8px; }
  .setting .block-name { flex: 1; min-width: 96px; }
  .setting .segments { flex: none; }
  .handle { padding: 4px; border: 0; background: none; color: inherit; cursor: grab; }
  .arrow { min-width: 40px; min-height: 40px; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); border-radius: 8px;
    background: none; color: inherit; font: inherit; cursor: pointer; }
  .settings-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .settings-title h2 { margin: 0; }
  .settings-title .close { flex: none; width: 40px; height: 40px; border: 0; background: none; color: inherit; font: inherit;
    cursor: pointer; }
  .settings-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
  .settings-actions .grow { flex: 1; }
  .settings-actions button, .setting select { padding: 8px 12px; border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    border-radius: 8px; background: var(--card-background-color, #fff); color: var(--primary-text-color, #212121); font: inherit; }
  .settings-actions button { cursor: pointer; }
  .settings-actions .primary { border-color: var(--primary-color, #03a9f4);
    background: color-mix(in srgb, var(--primary-color, #03a9f4) 20%, var(--card-background-color, #fff)); }
  dialog.settings :disabled:not(.segment), dialog.settings .handle:not([tabindex]) { opacity: 0.5; cursor: default; }
  @media (max-width: 480px) {
    dialog.settings { width: 100%; height: 100%; max-height: 100%; margin: 0; border-radius: 0; }
  }
`;
