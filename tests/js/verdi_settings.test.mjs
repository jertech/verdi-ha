// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BLOCKS,
  canHide,
  isCustom,
  isWide,
  moveBlock,
  moveAfter,
  moveBefore,
  PRESETS,
  resolve,
  rows,
  setOption,
  setPreset,
  settingsLabel,
  SETTINGS_LABELS,
} from "../../custom_components/verdi/frontend/verdi-settings.js";

const shown = (layout) => layout.order.filter((name) => layout.blocks[name].shown);

test("no stored set is Overzicht, the page as it was", () => {
  const layout = resolve(undefined);
  assert.equal(layout.preset, "overzicht");
  assert.deepEqual(layout.order, ["myStatus", "readiness", "vehicles", "personnel", "statistics"]);
  assert.deepEqual(rows(layout, true), [
    { left: ["myStatus", "readiness"], right: ["vehicles", "personnel"] },
    { full: "statistics" },
  ]);
  assert.equal(layout.blocks.vehicles.view, "tiles");
  assert.equal(layout.blocks.readiness.view, "lines");
  assert.equal(layout.blocks.personnel.view, "bar");
  assert.equal(layout.blocks.statistics.view, "numbers");
});

test("Bord has My status on top and every block full width", () => {
  const layout = resolve({ preset: "bord", changes: {} });
  assert.deepEqual(layout.order, ["myStatus", "vehicles", "readiness", "personnel", "statistics"]);
  assert.deepEqual(rows(layout, true), layout.order.map((full) => ({ full })));
  assert.equal(layout.blocks.readiness.view, "chips");
});

test("Lijst is one column of rows", () => {
  const layout = resolve({ preset: "lijst", changes: {} });
  assert.deepEqual(layout.order, ["myStatus", "vehicles", "readiness", "personnel", "statistics"]);
  assert.deepEqual(rows(layout, true), layout.order.map((full) => ({ full })));
  assert.equal(layout.blocks.vehicles.view, "list");
  assert.equal(layout.blocks.readiness.view, "lines");
  assert.equal(layout.blocks.statistics.view, "rows");
});

test("a phone is one column in the set's order", () => {
  const layout = resolve({ preset: "bord", changes: {} });
  assert.deepEqual(rows(layout, false), [{ left: layout.order, right: [] }]);
});

test("a Full block ends a row", () => {
  const set = { preset: "overzicht", changes: { blocks: { vehicles: { place: "full" } } } };
  assert.deepEqual(rows(resolve(set), true), [
    { left: ["myStatus", "readiness"], right: [] },
    { full: "vehicles" },
    { left: [], right: ["personnel"] },
    { full: "statistics" },
  ]);
});

test("changes apply on top of the preset", () => {
  const set = { preset: "bord", changes: { blocks: { vehicles: { view: "list", shown: false } } } };
  const layout = resolve(set);
  assert.equal(layout.blocks.vehicles.view, "list");
  assert.equal(layout.blocks.vehicles.shown, false);
  assert.equal(layout.blocks.readiness.view, "chips");
});

test("a preset that improves reaches its users", () => {
  const before = PRESETS.bord.blocks.personnel.view;
  PRESETS.bord.blocks.personnel.view = "pills";
  assert.equal(resolve({ preset: "bord", changes: {} }).blocks.personnel.view, "pills");
  PRESETS.bord.blocks.personnel.view = before;
});

test("anything unknown is ignored", () => {
  assert.equal(resolve({ preset: "gone", changes: {} }).preset, "overzicht");
  assert.equal(resolve("nonsense").preset, "overzicht");
  assert.equal(resolve(null).preset, "overzicht");
  const odd = {
    preset: "bord",
    changes: {
      order: ["map", "vehicles", "vehicles"],
      blocks: { map: { shown: false }, vehicles: { view: "chips", place: "middle", shown: "no" } },
    },
  };
  const layout = resolve(odd);
  assert.deepEqual([...layout.order].sort(), [...BLOCKS].sort());
  assert.equal(layout.order[0], "vehicles");
  assert.equal(layout.blocks.vehicles.view, "tiles");
  assert.equal(layout.blocks.vehicles.place, "full");
  assert.equal(layout.blocks.vehicles.shown, true);
  assert.deepEqual(resolve({ preset: "bord", changes: { order: "x", blocks: "y" } }).order, PRESETS.bord.order);
  assert.equal(resolve({ preset: "bord", changes: "z" }).preset, "bord");
});

test("a set with everything hidden still shows the preset's first block", () => {
  const blocks = Object.fromEntries(BLOCKS.map((name) => [name, { shown: false }]));
  const layout = resolve({ preset: "bord", changes: { blocks } });
  assert.deepEqual(shown(layout), ["myStatus"]);
});

test("the last shown block can't be hidden", () => {
  let set = { preset: "overzicht", changes: {} };
  for (const name of ["myStatus", "readiness", "vehicles", "personnel"]) {
    assert.equal(canHide(set, name), true);
    set = setOption(set, name, "shown", false);
  }
  assert.equal(canHide(set, "statistics"), false);
});

test("a value equal to the preset's isn't stored", () => {
  const set = { preset: "bord", changes: {} };
  const changed = setOption(set, "vehicles", "view", "list");
  assert.equal(isCustom(changed), true);
  assert.equal(isCustom(setOption(changed, "vehicles", "view", "tiles")), false);
  assert.deepEqual(setOption(changed, "vehicles", "view", "tiles").changes, {});
  assert.deepEqual(set.changes, {}); // the original stays as it was
});

test("picking a preset clears the changes", () => {
  const set = setOption({ preset: "bord", changes: {} }, "vehicles", "view", "list");
  assert.deepEqual(setPreset(set, "lijst"), { preset: "lijst", changes: {} });
});

test("moving a block up and down", () => {
  const set = moveBlock({ preset: "overzicht", changes: {} }, "vehicles", -1);
  assert.deepEqual(resolve(set).order, ["myStatus", "vehicles", "readiness", "personnel", "statistics"]);
  assert.deepEqual(moveBlock(set, "myStatus", -1), set);
  assert.equal(isCustom(moveBlock(set, "vehicles", 1)), false);
});

test("dragging a block before another", () => {
  const set = moveBefore({ preset: "overzicht", changes: {} }, "statistics", "readiness");
  assert.deepEqual(resolve(set).order, ["myStatus", "statistics", "readiness", "vehicles", "personnel"]);
});

test("dragging a block after another", () => {
  const base = { preset: "overzicht", changes: {} };
  const last = moveAfter(base, "readiness", "statistics");
  assert.deepEqual(resolve(last).order, ["myStatus", "vehicles", "personnel", "statistics", "readiness"]);
  const oneDown = moveAfter(base, "readiness", "vehicles");
  assert.deepEqual(resolve(oneDown).order, ["myStatus", "vehicles", "readiness", "personnel", "statistics"]);
  assert.equal(isCustom(moveAfter(oneDown, "vehicles", "readiness")), false);
});

test("wide starts at 720 px of content", () => {
  assert.equal(isWide(751, false), false);
  assert.equal(isWide(752, false), true);
  assert.equal(isWide(735, true), false);
  assert.equal(isWide(736, true), true);
  assert.equal(isWide(4000, false), true);
});

test("every label is there in all three languages", () => {
  const keys = Object.keys(SETTINGS_LABELS.en);
  assert.equal(keys.length, 33);
  for (const language of ["nl", "fr"]) assert.deepEqual(Object.keys(SETTINGS_LABELS[language]), keys);
  assert.equal(settingsLabel("nl-BE", "save"), "Opslaan");
  assert.equal(settingsLabel("de", "save"), "Save");
});
