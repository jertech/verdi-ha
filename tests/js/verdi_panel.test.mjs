// SPDX-License-Identifier: GPL-3.0-or-later
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  entityIds,
  label,
  normalizeColor,
  statusCounts,
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
  for (const key of ["myStatus", "vehicles", "personnel", "until", "total", "noData", "unknown", "empty", "incomplete", "notice", "menu"]) {
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
