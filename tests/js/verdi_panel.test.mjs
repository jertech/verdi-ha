// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  byName,
  canChange,
  canReturn,
  entityIds,
  label,
  normalizeColor,
  sendError,
  sendResult,
  startingDuration,
  statusCounts,
  statusLabel,
  statusText,
  textColor,
  vehicleName,
} from "../../custom_components/verdi/frontend/verdi-panel.js";

test("keeps Verdi's colours as they are", () => {
  for (const color of ["#fff", "#FFF", "#ffffff", "#015511", "#46FC4C"]) {
    assert.equal(normalizeColor(color), color);
  }
});

test("anything else is the web app's grey", () => {
  for (const color of [undefined, null, "", "red", "#12", "#12345", "#1234567", "#ggg", 17, {}]) {
    assert.equal(normalizeColor(color), "#D3D3D3");
  }
});

test("text is whichever of black and white reads better", () => {
  assert.equal(textColor("#015511"), "#ffffff");
  assert.equal(textColor("#ffffff"), "#000000");
  assert.equal(textColor("#fff"), "#000000");
  assert.equal(textColor("#08f133"), "#000000");
  assert.equal(textColor("#D3D3D3"), "#000000");
});

test("only statuses count, largest first", () => {
  const attributes = {
    Available: 2,
    Urgent: 7,
    unknown: 2,
    present: 9,
    on_intervention: 1,
    friendly_name: "Verdi Personnel",
    availability_colors: { Available: "#fff", Urgent: "#f00", unknown: null },
  };
  assert.deepEqual(statusCounts(attributes), [
    { name: "Urgent", color: "#f00", count: 7 },
    { name: "Available", color: "#fff", count: 2 },
    { name: "unknown", color: null, count: 2 },
  ]);
});

test("no attributes, no statuses", () => {
  assert.deepEqual(statusCounts(undefined), []);
  assert.deepEqual(statusCounts({}), []);
});

test("a sensor without data doesn't look like a Verdi status", () => {
  assert.equal(statusText("nl", undefined), "Geen gegevens");
  assert.equal(statusText("nl", { state: "unavailable" }), "Geen gegevens");
  assert.equal(statusText("nl", { state: "unknown" }), "Onbekend");
  assert.equal(statusText("nl", { state: "Niet beschikbaar" }), "Niet beschikbaar");
});

test("labels follow the language, default English", () => {
  assert.equal(label("nl", "vehicles"), "Voertuigen");
  assert.equal(label("fr", "vehicles"), "Véhicules");
  assert.equal(label("nl-BE", "vehicles"), "Voertuigen");
  assert.equal(label("de", "vehicles"), "Vehicles");
  assert.equal(label(undefined, "vehicles"), "Vehicles");
});

test("every language has every label", () => {
  for (const key of [
    "myStatus", "vehicles", "personnel", "until", "total", "noData", "unknown", "empty", "incomplete", "menu",
    "changeStatus", "chooseStatus", "status", "duration", "addException", "returnToPlanning", "close", "overruled", "unchecked", "unclear", "sending",
  ]) {
    for (const language of ["en", "nl", "fr"]) {
      assert.ok(label(language, key), `${language} ${key}`);
    }
  }
});

test("a vehicle's name drops the device name", () => {
  assert.equal(vehicleName("Verdi P100", "Verdi"), "P100");
  assert.equal(vehicleName("P100", "Verdi"), "P100");
  assert.equal(vehicleName(undefined, "Verdi"), "?");
});

test("a section's entities", () => {
  assert.deepEqual(
    entityIds({ my_availability: "sensor.a", vehicles: ["sensor.b", "sensor.c"], personnel: null }),
    ["sensor.a", "sensor.b", "sensor.c"],
  );
});

test("a personnel pill names the status, and says Unknown for the key unknown", () => {
  assert.equal(statusLabel("en", "unknown"), "Unknown");
  assert.equal(statusLabel("nl", "unknown"), "Onbekend");
  assert.equal(statusLabel("nl", "Beschikbaar"), "Beschikbaar");
});

test("vehicles sort by name with numbers in order", () => {
  const names = ["P100", "A9", "P20", "A10"].map((name) => ({ name }));
  assert.deepEqual(names.sort(byName).map((row) => row.name), ["A9", "A10", "P20", "P100"]);
});

const CONTROLS = {
  entry_id: "e1",
  status: "select.status",
  duration: "select.duration",
  back_to_planning: "button.back",
};
const select = (state, options = ["a", "b"]) => ({ state, attributes: { options } });
const STATES = { "select.status": select("unknown"), "select.duration": select("5m", ["5m", "1h"]) };

test("a section's entities include what the dialog depends on", () => {
  assert.deepEqual(
    entityIds({ my_availability: "sensor.a", vehicles: [], personnel: null, controls: CONTROLS }),
    ["sensor.a", "select.status", "select.duration", "button.back"],
  );
});

test("the pill works with both selects live, and nothing chosen counts as live", () => {
  assert.equal(canChange(CONTROLS, STATES), true);
});

test("the pill stays plain without what the dialog needs", () => {
  assert.equal(canChange(null, STATES), false);
  assert.equal(canChange(undefined, STATES), false);
  assert.equal(canChange(CONTROLS, {}), false);
  assert.equal(canChange(CONTROLS, { ...STATES, "select.status": select("unavailable") }), false);
  assert.equal(canChange(CONTROLS, { ...STATES, "select.duration": select("unavailable") }), false);
  assert.equal(canChange(CONTROLS, { ...STATES, "select.status": select("unknown", []) }), false);
  assert.equal(canChange(CONTROLS, { ...STATES, "select.status": { state: "unknown", attributes: {} } }), false);
});

test("return to planning shows when the button can be pressed", () => {
  assert.equal(canReturn(CONTROLS, { "button.back": { state: "unknown", attributes: {} } }), true);
  assert.equal(canReturn(CONTROLS, { "button.back": { state: "unavailable", attributes: {} } }), false);
  assert.equal(canReturn(CONTROLS, {}), false);
  assert.equal(canReturn({ ...CONTROLS, back_to_planning: null }, {}), false);
});

test("the duration starts where the select is", () => {
  assert.equal(startingDuration(select("1h", ["5m", "1h"])), "1h");
  assert.equal(startingDuration(select("unknown", ["5m", "1h"])), "5m");
});

test("an active exception closes the dialog", () => {
  assert.deepEqual(sendResult({ response: { active: true } }), { close: true });
});

test("an answer that isn't a plain yes keeps the dialog open, with only Close", () => {
  const stays = (label) => ({ close: false, label, canRetry: false });
  assert.deepEqual(sendResult({ response: { active: false } }), stays("overruled"));
  assert.deepEqual(sendResult({ response: { active: null } }), stays("unchecked"));
  assert.deepEqual(sendResult({ response: {} }), stays("unchecked"));
  assert.deepEqual(sendResult({}), stays("unchecked"));
});

const verdi = (translation_key) => ({ code: "home_assistant_error", translation_domain: "verdi", translation_key });

test("a refusal can be tried again", () => {
  for (const key of ["verdi_refused", "busy", "verdi_busy", "no_right", "token_refused", "unknown_status"]) {
    assert.deepEqual(sendError(verdi(key)), { close: false, exception: key, canRetry: true });
  }
});

test("a change that may have gone through can't be sent again", () => {
  for (const key of ["outcome_unknown", "partly_ended"]) {
    assert.deepEqual(sendError(verdi(key)), { close: false, exception: key, canRetry: false });
  }
});

test("an error that isn't Verdi's is unclear, and needs no server to say so", () => {
  const unclear = { close: false, label: "unclear", canRetry: false };
  assert.deepEqual(sendError({ error: { code: 3, message: "Connection lost" } }), unclear);
  assert.deepEqual(sendError({ code: "unauthorized", message: "Unauthorized" }), unclear);
  assert.deepEqual(sendError({ code: "x", translation_domain: "homeassistant", translation_key: "y" }), unclear);
  assert.deepEqual(sendError(undefined), unclear);
});
