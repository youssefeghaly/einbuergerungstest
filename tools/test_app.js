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
  // Bildfragen werden weiter unten gezielt geprüft (die Ziehung ist zufällig).
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

  // ---------------- Lernstand, Fehlerstapel, Auswahl ----------------
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

  console.log("\nFehlerstapel: zwei richtige Antworten nötig");
  api.store.record("5", false);
  let s5 = api.store.get("5");
  check(s5.bad === true && s5.streak === 0, "falsche Antwort landet im Fehlerstapel");
  api.store.record("5", true);
  s5 = api.store.get("5");
  check(s5.bad === true && s5.streak === 1, "eine richtige Antwort reicht noch nicht (Serie " + s5.streak + ")");
  api.store.record("5", true);
  check(api.store.get("5").bad === false, "zwei richtige Antworten in Folge entfernen die Frage");
  api.store.record("6", false);
  api.store.record("6", true);
  api.store.record("6", false);
  check(api.store.get("6").streak === 0, "ein erneuter Fehler setzt die Serie zurück");

  console.log("\nKeine Wiederholung zwischen zwei Tests");
  api.store.reset();
  const first = api.buildTest("HE").map((x) => x.id);
  first.forEach((id) => {
    api.store.data[id] = { s: 1, t: Date.now(), bad: false, streak: 0 };
  });
  const second = api.buildTest("HE").map((x) => x.id);
  const overlap = second.filter((id) => first.indexOf(id) !== -1);
  check(
    overlap.length === 0,
    "zweiter Test wiederholt keine Frage des ersten (" + overlap.length + " Überschneidungen)"
  );

  console.log("\nLandesfragen gehen zur Neige");
  api.store.reset();
  const seenState = new Set();
  const counts = [];
  for (let round = 0; round < 5; round++) {
    const test = api.buildTest("HE");
    const st = test.filter((x) => x.part === "state");
    counts.push(st.length);
    st.forEach((x) => seenState.add(x.id));
    test.forEach((x) => {
      api.store.data[x.id] = { s: 1, t: Date.now(), bad: false, streak: 0 };
    });
    check(test.length === 33, "Durchlauf " + (round + 1) + " hat 33 Fragen");
  }
  check(seenState.size === 10, "alle 10 Landesfragen kamen vor (" + seenState.size + ")");
  check(counts[4] === 0, "im 5. Durchlauf keine Landesfrage mehr (" + counts.join(", ") + ")");

  console.log("\nErschöpfter Vorrat: am längsten nicht gesehen");
  api.store.reset();
  const poolIds = api.poolFor("HE").map((x) => x.id);
  check(poolIds.length === 310, "Vorrat umfasst 310 Fragen (" + poolIds.length + ")");
  poolIds.forEach((id, i) => {
    api.store.data[id] = { s: 2, t: 1000 + i, bad: false, streak: 0 };
  });
  const lru = api.buildTest("HE");
  check(lru.length === 33, "auch nach dem Erschöpfen 33 Fragen");
  const generalPicked = lru.filter((x) => x.part === "general");
  const oldestGeneral = poolIds.slice(0, 60);
  check(
    generalPicked.every((x) => oldestGeneral.indexOf(x.id) !== -1),
    "die allgemeinen Fragen kommen aus den am längsten nicht gesehenen"
  );
  check(
    lru.filter((x) => x.part === "state").length === 3,
    "nach dem Erschöpfen wieder 3 Landesfragen"
  );

  console.log("\nFehler-Übung");
  api.store.reset();
  const pool = api.poolFor("HE");
  const badGeneral = pool.filter((q) => q.part === "general").slice(0, 50);
  const badState = pool.filter((q) => q.part === "state").slice(0, 10);
  badGeneral.concat(badState).forEach((q) => {
    api.store.data[q.id] = { s: 1, t: Date.now(), bad: true, streak: 0 };
  });
  check(api.wrongPool("HE").length === 60, "Fehlerstapel enthält 60 Fragen");
  const wt = api.buildWrongTest("HE");
  check(wt.length === 33, "Fehler-Test hat 33 Fragen");
  check(wt.every((x) => api.store.get(x.id).bad), "Fehler-Test enthält ausschliesslich falsche Fragen");
  check(
    wt.filter((x) => x.part === "state").length === 3,
    "Fehler-Test hält 30 + 3 ein (Landesfragen: " + wt.filter((x) => x.part === "state").length + ")"
  );

  console.log("\nRoter Knopf erst ab mehr als 33 Fehlern");
  api.store.reset();
  api.view.phase = "start";
  api.view.stateCode = "HE";
  api.render();
  let wrongBtn = q(window, '[data-act="start-wrong"]');
  check(!!wrongBtn, "roter Knopf ist vorhanden");
  check(wrongBtn.disabled === true, "bei 0 Fehlern gesperrt");
  const first33 = pool.filter((q) => q.part === "general").slice(0, 33);
  first33.forEach((q) => { api.store.data[q.id] = { s: 1, t: 1, bad: true, streak: 0 }; });
  api.render();
  check(
    q(window, '[data-act="start-wrong"]').disabled === true,
    "bei genau 33 Fehlern noch gesperrt"
  );
  api.store.data[pool.filter((q) => q.part === "general")[33].id] = {
    s: 1, t: 1, bad: true, streak: 0,
  };
  api.render();
  check(
    q(window, '[data-act="start-wrong"]').disabled === false,
    "ab 34 Fehlern freigeschaltet"
  );
  q(window, '[data-act="start-wrong"]').click();
  check(api.view.mode === "wrong", "Klick startet die Fehler-Übung");
  check(/Fehler-Übung/.test(q(window, ".qmeta").textContent), "die Frage ist als Fehler-Übung gekennzeichnet");

  console.log("\nHinweis auf Wiederholung");
  api.store.reset();
  const hintPool = api.poolFor("HE").filter((x) => x.part === "general").slice(0, 40);
  hintPool.forEach((x) => {
    api.store.data[x.id] = { s: 1, t: 1, bad: true, streak: 0 };
  });
  api.view.stateCode = "HE";
  api.beginTest("wrong");
  check(api.view.test.length === 33, "Fehler-Übung startet mit 33 Fragen");
  check(!!q(window, ".repeat-hint"), "bereits falsch beantwortete Frage wird als Wiederholung gekennzeichnet");

  console.log("\nBildfragen werden angezeigt");
  api.store.reset();
  api.poolFor("HE").forEach((x) => {
    if (!x.image) api.store.data[x.id] = { s: 3, t: 1, bad: false, streak: 0 };
  });
  const imgTest = api.buildTest("HE");
  const imgAt = imgTest.findIndex((x) => x.image);
  check(imgAt !== -1, "Bildfrage wird gezogen");
  if (imgAt !== -1) {
    api.view.test = imgTest;
    api.view.answers = imgTest.map(() => null);
    api.view.index = imgAt;
    api.view.phase = "quiz";
    api.render();
    check(!!q(window, ".qimg"), "Bild wird im Test dargestellt");
  }

  console.log("\nZurücksetzen über die Oberfläche");
  api.store.record("2", false);
  api.view.phase = "start";
  api.render();
  const resetBtn = q(window, '[data-act="reset"]');
  check(!!resetBtn, "Knopf zum Zurücksetzen erscheint, sobald Fortschritt existiert");
  check(/von 310 Fragen gesehen/.test(q(window, "#app").textContent), "Lernstand wird angezeigt");
  if (resetBtn) resetBtn.click();
  check(
    window.localStorage.getItem("eit.progress.v1") === null,
    "Zurücksetzen über die Oberfläche löscht den Lernstand"
  );
  check(
    /0 von 310 Fragen gesehen/.test(q(window, "#app").textContent),
    "Anzeige steht nach dem Zurücksetzen wieder auf 0"
  );

  console.log("\nKein doppelter Fragetext im selben Test");
  // Mehrere amtliche Fragen haben denselben Wortlaut (z. B. "Welches Land ist
  // ein Nachbarland von Deutschland?" kommt fünfmal vor). Früher konnten zwei
  // davon im selben Durchlauf landen.
  const data = window.QUESTION_DATA.questions;
  const groups = {};
  data.forEach((x) => {
    const k = api.stemKey(x.question);
    groups[k] = (groups[k] || 0) + 1;
  });
  const repeated = Object.values(groups).filter((n) => n > 1).length;
  check(
    repeated > 0,
    "Katalog enthält tatsächlich mehrfach vorkommende Fragetexte (" + repeated + " Gruppen)"
  );

  api.store.reset();
  const DRAWS = 2000;
  let collisions = 0, wrongSize = 0, wrongState = 0, firstBad = null;
  for (let i = 0; i < DRAWS; i++) {
    const test = api.buildTest("HE");
    if (test.length !== 33) wrongSize++;
    if (test.filter((x) => x.part === "state").length !== 3) wrongState++;
    const seen = new Set();
    for (const x of test) {
      const k = api.stemKey(x.question);
      if (seen.has(k)) {
        collisions++;
        if (!firstBad) firstBad = x.question.slice(0, 60);
        break;
      }
      seen.add(k);
    }
  }
  check(
    collisions === 0,
    "in " + DRAWS + " Durchläufen kein doppelter Fragetext (gefunden: " + collisions +
      (firstBad ? ", z. B. " + firstBad : "") + ")"
  );
  check(wrongSize === 0, "jeder Durchlauf hat genau 33 Fragen");
  check(wrongState === 0, "jeder Durchlauf hat genau 3 Landesfragen");

  // Extremfall: alle Fragen maximal dringlich - der Test muss trotzdem voll sein.
  data.forEach((x) => { api.store.data[x.id] = { s: 9, t: 1, bad: true, streak: 0 }; });
  let incomplete = 0;
  for (let i = 0; i < 300; i++) {
    if (api.buildTest("HE").length !== 33) incomplete++;
  }
  check(incomplete === 0, "auch bei durchweg hoher Gewichtung bleiben es 33 Fragen");
  api.store.reset();
}
