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
