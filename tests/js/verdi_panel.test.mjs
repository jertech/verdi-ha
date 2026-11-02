// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  barSegments,
  canChange,
  canReturn,
  dayMonth,
  entityIds,
  label,
  missingPositions,
  moment,
  normalizeColor,
  refreshDelay,
  responseTime,
  sendError,
  sendResult,
  startingDuration,
  statisticTile,
  statusCounts,
  statusLabel,
  statusText,
  textColor,
  unavailableIds,
  until,
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
    "readiness", "statistics", "since", "next", "missing", "last", "available", "preAlert", "garrison",
    "problem_token", "problem_paused", "problem_verdi",
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

test("response time in whole minutes, a range when they differ", () => {
  const time = (fastest_response_time, slowest_response_time) => ({ fastest_response_time, slowest_response_time });
  assert.equal(responseTime(time("00:05:00", "00:05:00")), "5 min");
  assert.equal(responseTime(time("00:05:00", "00:08:00")), "5–8 min");
  assert.equal(responseTime(time("01:02:00", "01:02:00")), "62 min");
  assert.equal(responseTime(time("00:05:00", null)), "5 min");
  assert.equal(responseTime(time(null, "00:08:00")), "8 min");
  assert.equal(responseTime(time(null, undefined)), null);
  assert.equal(responseTime(time("soon", "later")), null);
  assert.equal(responseTime(undefined), null);
});

test("missing positions keep Verdi's order", () => {
  assert.deepEqual(missingPositions({ Driver: true, Crew: false, Aide: false }), ["Crew", "Aide"]);
  assert.deepEqual(missingPositions({ Driver: true }), []);
  assert.deepEqual(missingPositions(undefined), []);
});

test("a moment is a time today, and a date and time on another day", () => {
  const now = new Date(2026, 5, 15, 20, 0);
  assert.equal(moment(new Date(2026, 5, 15, 9, 5).toISOString(), "nl", now), "09:05");
  assert.match(moment(new Date(2026, 5, 14, 9, 5).toISOString(), "nl", now), /14.*6.*09:05/);
  assert.equal(moment(null, "nl", now), null);
  assert.equal(moment("not a date", "nl", now), null);
});

test("until is the time today, and a date and time on another day", () => {
  const now = new Date(2026, 5, 15, 8, 0);
  assert.equal(until(new Date(2026, 5, 15, 9, 5).toISOString(), "nl", now), "tot 09:05");
  assert.match(until(new Date(2026, 5, 16, 9, 5).toISOString(), "nl", now), /^tot .*16.*6.*09:05/);
  assert.equal(until(null, "nl", now), null);
  assert.equal(until("not a date", "nl", now), null);
});

test("a day and a month, or nothing", () => {
  assert.match(dayMonth(new Date(2026, 9, 21, 17, 31).toISOString(), "nl"), /21.*10/);
  assert.equal(dayMonth(null, "nl"), null);
  assert.equal(dayMonth("not a date", "nl"), null);
});

test("an availability tile has the newest year, and the year before", () => {
  const state = { state: "34.7", attributes: { station: "North", years: { 2025: 44.1, 2026: 34.7 } } };
  assert.deepEqual(statisticTile(state, "nl", false), {
    value: "34,7 %",
    title: "Beschikbaar 2026",
    detail: "2025: 44,1 %",
  });
  assert.equal(statisticTile(state, "en", false).value, "34.7 %");
  assert.equal(statisticTile(state, "nl", true).title, "Beschikbaar 2026 North");
});

test("an availability tile copes with one year or none yet", () => {
  const one = { state: "34.7", attributes: { station: "North", years: { 2026: 34.7 } } };
  assert.equal(statisticTile(one, "nl", false).detail, null);
  const restored = { state: "34.7", attributes: { station: "North" } };
  assert.deepEqual(statisticTile(restored, "nl", false), { value: "34,7 %", title: "Beschikbaar", detail: null });
});

test("a counter tile has a plain number, the service and the last call", () => {
  const state = { state: "24", attributes: { service: "Fire", last_called: new Date(2026, 9, 21).toISOString() } };
  const tile = statisticTile(state, "nl", false);
  assert.equal(tile.value, "24");
  assert.equal(tile.title, "Fire");
  assert.match(tile.detail, /^laatst 21.*10/);
  assert.equal(statisticTile({ state: "24", attributes: { service: "Fire" } }, "nl", false).detail, null);
});

test("no tile without a value", () => {
  assert.equal(statisticTile(undefined, "nl", false), null);
  assert.equal(statisticTile({ state: "unavailable", attributes: {} }, "nl", false), null);
  assert.equal(statisticTile({ state: "unknown", attributes: {} }, "nl", false), null);
});

test("the bar leaves out statuses nobody has", () => {
  const colors = { A: "#111111", B: "#222222", C: null };
  const segments = barSegments({ availability_colors: colors, A: 3, B: 0, C: 1 });
  assert.deepEqual(segments, [
    { name: "A", color: "#111111", count: 3 },
    { name: "C", color: null, count: 1 },
  ]);
});

test("a section's entities include the new blocks, and sections may lack them", () => {
  assert.deepEqual(
    entityIds({
      my_availability: "sensor.a",
      pre_alert: "binary_sensor.p",
      garrison: "binary_sensor.g",
      readiness: ["binary_sensor.r"],
      vehicles: ["sensor.b"],
      personnel: null,
      statistics: ["sensor.s"],
    }),
    ["sensor.a", "binary_sensor.p", "binary_sensor.g", "binary_sensor.r", "sensor.b", "sensor.s"],
  );
});

test("unavailable means missing or unavailable, not unknown", () => {
  const states = { "sensor.a": { state: "unavailable" }, "sensor.b": { state: "unknown" }, "sensor.c": { state: "x" } };
  assert.deepEqual(unavailableIds(["sensor.a", "sensor.b", "sensor.c", "sensor.d"], states), ["sensor.a", "sensor.d"]);
});

test("the page asks at most once a minute", () => {
  assert.equal(refreshDelay(0, 60000), 0);
  assert.equal(refreshDelay(0, 90000), 0);
  assert.equal(refreshDelay(0, 15000), 45000);
});
