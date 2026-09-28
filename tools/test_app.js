/**
 * End-to-end test for index.html driven through a real DOM (jsdom).
 *
 * It plays a complete 33-question round, tracking the score independently,
 * and asserts the app's result matches.  Requires jsdom:
 *
 *   npm install jsdom
 *   node tools/test_app.js
 */

const path = require("path");
const { pathToFileURL } = require("url");
const { JSDOM } = require("jsdom");

const INDEX = path.join(__dirname, "..", "index.html");

let failures = 0;
function check(condition, message) {
  if (condition) {
    console.log("  ok   " + message);
  } else {
    failures++;
    console.log("  FAIL " + message);
  }
}

function q(dom, sel) {
  return dom.window.document.querySelector(sel);
}
function qa(dom, sel) {
  return Array.from(dom.window.document.querySelectorAll(sel));
}

JSDOM.fromFile(INDEX, {
  runScripts: "dangerously",
  resources: "usable",
  pretendToBeVisual: true,
  beforeParse(window) {
    window.scrollTo = function () {};
    window.confirm = function () { return true; };
    // Deterministic RNG so the random draw is reproducible across runs.
    let seed = 20250507;
    window.Math.random = function () {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    // jsdom refuses localStorage for file:// URLs (opaque origin), so provide
    // an in-memory implementation with the same surface.
    const mem = new Map();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (k) => (mem.has(k) ? mem.get(k) : null),
        setItem: (k, v) => mem.set(k, String(v)),
        removeItem: (k) => mem.delete(k),
        clear: () => mem.clear(),
        get length() { return mem.size; },
      },
    });
  },
}).then((dom) => {
  const { window } = dom;
  window.addEventListener("load", () => {
    try {
      run(window);
    } catch (err) {
      console.error("\nUNEXPECTED ERROR:", err);
      failures++;
    }
    console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
    process.exit(failures === 0 ? 0 : 1);
  });
});

function run(window) {
  console.log("Startbildschirm");
  const app = q(window, "#app");
  check(!!app, "#app existiert");
  check(/Einbürgerungstest/.test(app.textContent), "Titel wird angezeigt");
  check(!!q(window, "#state"), "Bundesland-Auswahl vorhanden");
  check(
    q(window, "#state").value === "HE",
    "Hessen ist vorausgewählt (war: " + q(window, "#state").value + ")"
  );
  check(qa(window, "#state option").length === 16, "16 Bundesländer zur Auswahl");
  check(q(window, '[data-act="start"]') !== null, "Startknopf vorhanden");

  // --- one full round, answering a deterministic mix -----------------------
  q(window, '[data-act="start"]').click();

  const N = 33;
  let expectedScore = 0;
  let hessen = 0;
  let images = 0;
  let seenIds = new Set();

  console.log("\nDurchlauf (" + N + " Fragen)");
  for (let i = 0; i < N; i++) {
    const meta = q(window, ".qmeta").textContent;
    check(
      new RegExp("Frage " + (i + 1) + " von " + N).test(
        qa(window, ".qmeta").map((e) => e.textContent).join(" | ")
      ),
      "Fortschritt zeigt Frage " + (i + 1) + " von " + N
    );

    const opts = qa(window, ".opt");
    check(opts.length === 4, "Frage " + (i + 1) + ": genau 4 Antwortoptionen");

    if (q(window, ".qimg")) images++;
    if (/Hessen/.test(q(window, ".qmeta").textContent)) hessen++;
    seenIds.add(q(window, ".qmeta").textContent);

    // Mix of right and wrong picks; skip every 11th question entirely.
    const skip = i % 11 === 10;
    if (skip) {
      check(
        q(window, '[data-act="next"]').textContent.includes("Ohne Antwort"),
        "Frage " + (i + 1) + ": Knopf bietet Überspringen an"
      );
      q(window, '[data-act="next"]').click();
      continue;
    }

    const pick = i % 4;
    opts[pick].click();

    const okOpt = qa(window, ".opt.state-ok");
    check(okOpt.length === 1, "Frage " + (i + 1) + ": genau eine richtige Antwort markiert");
    const correctIndex = qa(window, ".opt").indexOf(okOpt[0]);
    if (correctIndex === pick) expectedScore++;

    const verdict = q(window, ".verdict");
    check(!!verdict, "Frage " + (i + 1) + ": Rückmeldung erscheint sofort");
    check(
      verdict.classList.contains(pick === correctIndex ? "ok" : "bad"),
      "Frage " + (i + 1) + ": Rückmeldung passt zur Antwort"
    );
    check(
      /Richtige Antwort:/.test(verdict.textContent),
      "Frage " + (i + 1) + ": richtige Antwort wird genannt"
    );

    // locked after answering: a second click must not change the choice
    const before = qa(window, ".opt").map((o) => o.className).join();
    qa(window, ".opt")[(pick + 1) % 4].click();
    check(
      qa(window, ".opt").map((o) => o.className).join() === before,
      "Frage " + (i + 1) + ": Antwort ist nach der Rückmeldung gesperrt"
    );

    q(window, '[data-act="next"]').click();
  }
  console.log("\nAuswertung");
  const scoreEl = q(window, ".score");
  check(!!scoreEl, "Ergebnis wird angezeigt");
  const shown = parseInt(scoreEl.textContent, 10);
  check(
    shown === expectedScore,
    "Ergebnis stimmt mit unabhängig gezählter Punktzahl überein (angezeigt " +
      shown + ", erwartet " + expectedScore + ")"
  );
  check(/von 33/.test(scoreEl.textContent), "Ergebnis nennt die Gesamtzahl 33");

  const tags = qa(window, ".tag");
  check(tags.length === 33, "Überblicksliste enthält alle 33 Fragen (war " + tags.length + ")");
  const skipped = tags.filter((t) => t.textContent === "nicht beantwortet").length;
  check(skipped === 3, "3 übersprungene Fragen sind als unbeantwortet markiert (war " + skipped + ")");
  const okTags = tags.filter((t) => t.textContent === "richtig").length;
  check(
    okTags === expectedScore,
    "Anzahl grüner Markierungen entspricht der Punktzahl (" + okTags + ")"
  );

  console.log("\nZusammenstellung");
  check(hessen === 3, "genau 3 Fragen zu Hessen (war " + hessen + ")");
  check(images >= 1, "Bildfragen werden mit Bild dargestellt (war " + images + ")");
  check(seenIds.size === 33, "keine Frage doppelt im Test (eindeutige Labels: " + seenIds.size + ")");

  console.log("\nNeuer Test / Bundesland");
  q(window, '[data-act="home"]').click();
  check(!!q(window, "#state"), "Zurück zum Startbildschirm");
  q(window, "#state").value = "BY";
  q(window, '[data-act="start"]').click();
  let bayern = 0;
  for (let i = 0; i < 33; i++) {
    if (/Bayern/.test(q(window, ".qmeta").textContent)) bayern++;
    qa(window, ".opt")[0].click();
    q(window, '[data-act="next"]').click();
  }
  check(bayern === 3, "mit Bayern werden 3 bayerische Fragen gezogen (war " + bayern + ")");

  // ---------------- adaptive Auswahl und Lernstand ----------------
  console.log("\nLernstand speichern");
  const api = window.__EIT__;
  check(!!api, "Testzugang vorhanden");
  check(
    window.localStorage.getItem("eit.progress.v1") !== null,
    "Lernstand liegt im localStorage"
  );

  api.store.reset();
  check(
    window.localStorage.getItem("eit.progress.v1") === null,
    "Zurücksetzen entfernt den gespeicherten Lernstand"
  );

  console.log("\nVergessen und Dringlichkeit");
  for (let i = 0; i < 4; i++) api.store.record("5", false);
  let s5 = api.store.get("5");
  check(s5.w === 4 && s5.c === 0, "viermal falsch -> w=4, c=0 (war w=" + s5.w + ", c=" + s5.c + ")");
  api.store.record("5", true);
  s5 = api.store.get("5");
  check(s5.w === 3 && s5.c === 1, "richtige Antwort verringert die Dringlichkeit (w=" + s5.w + ", c=" + s5.c + ")");

  console.log("\nAdaptive Auswahl");
  api.store.reset();
  const hard = "5", easy = "6";
  api.store.data[hard] = { s: 4, w: 4, c: 0 };
  api.store.data[easy] = { s: 4, w: 0, c: 4 };
  const wHard = api.weight(hard), wEasy = api.weight(easy), wNew = api.weight("7");
  check(wHard > wEasy, "falsch beantwortete Frage wiegt schwerer (" + wHard + " > " + wEasy + ")");
  check(wNew > wEasy, "nie gesehene Frage hat Vorrang vor beherrschter (" + wNew + " > " + wEasy + ")");

  const RUNS = 400;
  let hardCount = 0, easyCount = 0;
  for (let i = 0; i < RUNS; i++) {
    const test = api.buildTest("HE");
    if (test.some((x) => x.id === hard)) hardCount++;
    if (test.some((x) => x.id === easy)) easyCount++;
  }
  check(
    hardCount > easyCount * 2,
    "falsch beantwortete Frage kommt deutlich häufiger vor (" +
      hardCount + "x vs " + easyCount + "x bei " + RUNS + " Durchläufen)"
  );

  console.log("\nHinweis auf Wiederholung");
  api.store.data["1"] = { s: 3, w: 3, c: 0 };
  let found = false;
  for (let attempt = 0; attempt < 60 && !found; attempt++) {
    q(window, '[data-act="home"]').click();
    q(window, "#state").value = "HE";
    q(window, '[data-act="start"]').click();
    const at = api.view.test.findIndex((x) => x.id === "1");
    if (at === -1) continue;
    for (let step = 0; step < at; step++) q(window, '[data-act="next"]').click();
    found = !!q(window, ".repeat-hint");
  }
  check(found, "bereits falsch beantwortete Frage wird als Wiederholung gekennzeichnet");

  console.log("\nZurücksetzen über die Oberfläche");
  api.store.record("2", false);
  api.view.phase = "start";
  api.render();
  const resetBtn = q(window, '[data-act="reset"]');
  check(!!resetBtn, "Knopf zum Zurücksetzen erscheint, sobald Fortschritt existiert");
  check(/von 460 Fragen bearbeitet/.test(q(window, "#app").textContent), "Lernstand wird angezeigt");
  if (resetBtn) resetBtn.click();
  check(
    window.localStorage.getItem("eit.progress.v1") === null,
    "Zurücksetzen über die Oberfläche löscht den Lernstand"
  );
  check(
    /0 von 460 Fragen bearbeitet/.test(q(window, "#app").textContent),
    "Anzeige steht nach dem Zurücksetzen wieder auf 0"
  );
}
