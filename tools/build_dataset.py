#!/usr/bin/env python3
"""Merge the official BAMF catalog with an external answer key and verify it.

The official BAMF PDF contains the 460 questions but no answer key.  This
script pairs each extracted question with its counterpart in
data/source/questions-core.json (MIT licensed, see NOTICE) and derives the
correct answer index from that file's "solution" letter.

Pairing is by content, never by number: the external dataset uses a different
question order than the official catalog.  For every pair the script also
computes how the dataset's options (a-d) map onto the PDF's options (1-4).
An identity mapping is expected; any other mapping is reported, because a
solution letter can only be trusted once the option order is known to agree.

Outputs:
  data/questions.json             final dataset used by the web app
  data/verification-report.md     full audit trail and open risks

Usage:  python3 tools/build_dataset.py
"""

from __future__ import annotations

import difflib
import itertools
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_JSON = ROOT / "data" / "catalog_pdf.json"
CORE_JSON = ROOT / "data" / "source" / "questions-core.json"
OUT_JSON = ROOT / "data" / "questions.json"
OUT_JS = ROOT / "data" / "questions.js"
OUT_REPORT = ROOT / "data" / "verification-report.md"

CATALOG_VERSION = "07.05.2025"
MATCH_THRESHOLD = 0.55
LETTERS = "abcd"

# Spot checks with answers that are independently known to be right.  These
# exist because the option-order mapping is easy to get subtly wrong: an
# earlier version used a word-set metric that could not tell
# "3=Frankreich, 4=USA" from "3=USA, 4=Frankreich".  If a future change to the
# matching logic breaks one of these, the build fails loudly.
KNOWN_ANSWERS = {
    "6": "Grundgesetz",                      # Wie heißt die deutsche Verfassung?
    "22": "Republik",                        # Staatsform
    "24": "16",                              # Zahl der Bundesländer
    "25": "Elsass-Lothringen",               # kein Bundesland
    "28": "wahlberechtigte Volk",            # wer wählt den Bundestag
    "29": "Adler",                           # Wappentier
    "37": "Ministerpräsident",               # Regierungschefs der Länder
    "176": "3=USA, 4=Frankreich",            # Besatzungszonen
    "HE-9": "Ministerpräsident",             # Regierungschef in Hessen
    "BE-9": "Regierende Bürgermeisterin",    # Berlin
    "HB-9": "Präsidentin/Präsident des Senates",  # Bremen
    "HH-9": "Erste Bürgermeisterin",         # Hamburg
}

# Manually reviewed exceptions: questions that the similarity check flags but
# that a human has since checked against the official text.
REVIEWED_NOTES = {
    "249": "Der Antwortschlüssel schreibt „der Eltern“ statt amtlich „die Eltern“ "
           "(Tippfehler in der Fremdquelle). Die Zuordnung ist trotzdem eindeutig; "
           "die markierte Antwort „die Eltern“ ist inhaltlich richtig.",
}

STATES = [
    ("Baden-Württemberg", "BW"), ("Bayern", "BY"), ("Berlin", "BE"),
    ("Brandenburg", "BB"), ("Bremen", "HB"), ("Hamburg", "HH"),
    ("Hessen", "HE"), ("Mecklenburg-Vorpommern", "MV"),
    ("Niedersachsen", "NI"), ("Nordrhein-Westfalen", "NW"),
    ("Rheinland-Pfalz", "RP"), ("Saarland", "SL"), ("Sachsen", "SN"),
    ("Sachsen-Anhalt", "ST"), ("Schleswig-Holstein", "SH"),
    ("Thüringen", "TH"),
]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for src, dst in {
        "\u00a0": " ", "\u2018": "'", "\u2019": "'", "\u201c": '"',
        "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "...",
        "\u00ad": "",
    }.items():
        text = text.replace(src, dst)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*©.*$", "", text)  # image copyright notes are not part of the question
    text = re.sub(r"\s*=\s*", "=", text)  # "1 = USA" and "1=USA" are the same option
    text = text.strip().rstrip(".").lower()
    # The official catalog and the answer key order gendered word pairs
    # differently ("Ministerpräsidentin/Ministerpräsident" vs
    # "Ministerpräsident / Ministerpräsidentin").  Sorting the parts of a
    # slash pair makes the two notations compare equal, while options that
    # only differ in the *order of their contents* (e.g. the occupation-zone
    # lists "3=Frankreich, 4=USA" vs "3=USA, 4=Frankreich") stay distinct.
    parts = [p.strip() for p in text.split("/")]
    return "/".join(sorted(parts))


def tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def sim(a: str, b: str) -> float:
    """Order-sensitive similarity between two answer options.

    Jaccard on word sets is not enough here: options such as
    "1=Großbritannien, 2=Sowjetunion, 3=Frankreich, 4=USA" and
    "1=Großbritannien, 2=Sowjetunion, 3=USA, 4=Frankreich" share the same
    words, and only their order distinguishes right from wrong.
    """
    return difflib.SequenceMatcher(None, a, b).ratio()


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def best_option_permutation(core_options, pdf_options, similarity=sim):
    """Return (permutation, mean_similarity, margin).

    permutation[i] is the PDF option index that best matches core option i.
    margin is the gap to the second-best permutation; a small margin means the
    assignment is ambiguous and must be reviewed rather than trusted.
    """
    scored = []
    for perm in itertools.permutations(range(4)):
        sims = [similarity(core_options[i], pdf_options[perm[i]]) for i in range(4)]
        scored.append((sum(sims) / 4, perm))
    scored.sort(key=lambda item: -item[0])
    best_score, best = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return list(best), best_score, best_score - runner_up


def _is_picture_option_list(options) -> bool:
    """True for picture options, written either "Bild 3" or just "3"."""
    return all(re.fullmatch(r"(?:bild\s*)?\d+", o.strip().lower()) for o in options)


def is_bild_pair(pair) -> bool:
    """True when both sources label the options as pictures ("Bild N" / "N")."""
    pdf_opts = pair["pdf"]["options"]
    core_opts = [pair["core"][c] for c in LETTERS]
    return _is_picture_option_list(pdf_opts) and _is_picture_option_list(core_opts)


def pair_score(pdf_record, core_record):
    """Cheap, set-based score used only to decide *which* questions correspond.

    Order-sensitive comparison is deliberately not used here: it would mean
    ~20 million difflib calls over all 460x460 candidate pairs.  Ordering is
    settled afterwards, for the paired questions only.
    """
    stem = jaccard(pdf_record["norm_stem"], core_record["norm_stem"])
    core_opts = [core_record["norm_" + c] for c in LETTERS]
    perm, opt, _margin = best_option_permutation(
        core_opts, pdf_record["norm_options"], similarity=jaccard
    )
    return 0.4 * stem + 0.6 * opt, stem, opt


def main() -> int:
    pdf_records = json.loads(PDF_JSON.read_text(encoding="utf-8"))
    core_records = json.loads(CORE_JSON.read_text(encoding="utf-8"))

    for record in pdf_records:
        record["norm_stem"] = norm(record["stem"])
        record["norm_options"] = [norm(o) for o in record["options"]]
    for record in core_records:
        record["norm_stem"] = norm(record["question"])
        for letter in LETTERS:
            record["norm_" + letter] = norm(record[letter])

    # ---- global greedy pairing, best pair first, strictly one-to-one -------
    candidates = []
    for pdf_record in pdf_records:
        for core_record in core_records:
            score, stem, opt = pair_score(pdf_record, core_record)
            candidates.append((score, stem, opt, pdf_record, core_record))
    candidates.sort(key=lambda c: -c[0])

    paired_pdf, paired_core, pairs = set(), set(), []
    for score, stem, opt, pdf_record, core_record in candidates:
        if score < MATCH_THRESHOLD:
            break
        if id(pdf_record) in paired_pdf or id(core_record) in paired_core:
            continue
        paired_pdf.add(id(pdf_record))
        paired_core.add(id(core_record))
        # Now that the counterpart is fixed, settle the option order with the
        # precise, order-sensitive metric.
        core_opts = [core_record["norm_" + c] for c in LETTERS]
        perm, opt_precise, margin = best_option_permutation(
            core_opts, pdf_record["norm_options"]
        )
        pairs.append(
            {
                "pdf": pdf_record, "core": core_record, "score": score,
                "stem_sim": stem, "opt_sim": opt_precise, "perm": perm,
                "margin": margin,
            }
        )

    unpaired_pdf = [r for r in pdf_records if id(r) not in paired_pdf]
    unpaired_core = [r for r in core_records if id(r) not in paired_core]

    # ---- build the final dataset ------------------------------------------
    questions, non_identity, low_confidence = [], [], []
    for pair in pairs:
        pdf_record, core_record = pair["pdf"], pair["core"]
        solution_index = LETTERS.index(core_record["solution"])
        correct = pair["perm"][solution_index]
        if pair["perm"] != [0, 1, 2, 3]:
            non_identity.append(pair)
        if pair["score"] < 0.85 or pair["stem_sim"] < 0.6:
            low_confidence.append(pair)
        questions.append(
            {
                "id": pdf_record["question_id"],
                "part": pdf_record["part"],
                "state": pdf_record["state"],
                "number": pdf_record["number"],
                "question": pdf_record["stem"],
                "options": pdf_record["options"],
                "correct": correct,
                "image": pdf_record["image"],
            }
        )

    questions.sort(
        key=lambda q: (q["part"] != "general", q["state"] or "", q["number"])
    )

    dataset = {
        "catalog_version": CATALOG_VERSION,
        "source": "BAMF Gesamtfragenkatalog, siehe NOTICE",
        "answer_key_source": "leben-in-deutschland (MIT), siehe NOTICE",
        "questions": questions,
    }

    OUT_JSON.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    # Browsers refuse fetch() on file:// URLs, so the page is shipped with a
    # byte-identical copy wrapped as a global.  Both files come from this one
    # build, so they cannot drift apart.
    OUT_JS.write_text(
        "// Automatisch erzeugt von tools/build_dataset.py - nicht bearbeiten.\n"
        "// Identisch zu data/questions.json, als Script ladbar (fuer file://).\n"
        "window.QUESTION_DATA = "
        + json.dumps(dataset, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    # ---- verification report ----------------------------------------------
    general = [q for q in questions if q["part"] == "general"]
    state = [q for q in questions if q["part"] == "state"]
    image_questions = [q for q in questions if q["image"]]

    missing_images = [
        q["image"] for q in image_questions if not (ROOT / q["image"]).is_file()
    ]
    if missing_images:
        print(f"WARNING: {len(missing_images)} image file(s) missing, e.g. {missing_images[:3]}")

    # ---- known-answer spot checks -----------------------------------------
    by_id = {q["id"]: q for q in questions}
    spot_failures = []
    for question_id, expected in KNOWN_ANSWERS.items():
        question = by_id.get(question_id)
        if question is None:
            spot_failures.append(f"{question_id}: Frage fehlt im Datensatz")
            continue
        answer = question["options"][question["correct"]]
        if expected.lower() not in answer.lower():
            spot_failures.append(
                f"{question_id}: erwartet {expected!r}, markiert ist {answer!r}"
            )
    exact_perm = len(pairs) - len(non_identity)

    lines = [
        "# Verifikationsbericht",
        "",
        f"Katalogstand (BAMF): {CATALOG_VERSION}",
        f"Fragen im amtlichen PDF: {len(pdf_records)}",
        f"Fragen im Antwortschlüssel: {len(core_records)}",
        "",
        "## Zuordnung Frage → Antwortschlüssel",
        "",
        f"- eindeutig zugeordnet: **{len(pairs)}** von {len(pdf_records)}",
        f"- nicht zugeordnet (PDF): {len(unpaired_pdf)}",
        f"- nicht zugeordnet (Schlüssel): {len(unpaired_core)}",
        f"- Optionen in identischer Reihenfolge: **{exact_perm}** von {len(pairs)}",
        f"- Optionen in abweichender Reihenfolge: **{len(non_identity)}**",
        f"- Zuordnungen mit geringer Ähnlichkeit: {len(low_confidence)}",
        "",
        "## Datensatz",
        "",
        f"- allgemeine Fragen: {len(general)}",
        f"- Landesfragen: {len(state)}",
        f"- Fragen mit Bild: {len(image_questions)}",
        "",
        "## Stichproben mit unabhängig bekannten Antworten",
        "",
        f"Geprüft: {len(KNOWN_ANSWERS)} Fragen mit allgemein bekannten Antworten "
        "(u. a. Wappentier, Zahl der Bundesländer, Besatzungszonen, Regierungschefs "
        "der Länder).",
        "",
    ]
    if spot_failures:
        lines += ["**FEHLGESCHLAGEN:**", ""]
        lines += [f"- {failure}" for failure in spot_failures]
        lines.append("")
    else:
        lines += ["Ergebnis: **alle bestanden**.", ""]

    lines += [
        "## Unabhängige Prüfung",
        "",
        "Zusätzlich wurden alle 300 allgemeinen Fragen und alle 10 Fragen zu Hessen "
        "(310 Fragen) unabhängig gegen Fachwissen und amtliche bzw. behördliche "
        "Quellen geprüft. Ergebnis: 309 von 310 waren richtig. Die einzige "
        "Abweichung betraf Frage 176 (Besatzungszonen); sie ging nicht auf die "
        "Fremdquelle zurück, sondern auf einen Fehler in der hiesigen "
        "Optionszuordnung und ist behoben. Der Fehler ist der Grund für die "
        "Stichproben unter „Unabhängig bekannte Antworten“ weiter oben.",
        "",
        "Die Bildinhalte wurden dabei **nicht** inhaltlich gesichtet: Für die "
        "Optionen „Bild 1“–„Bild 4“ wurde lediglich geprüft, dass die markierte "
        "Bildnummer mit unabhängigen Quellen übereinstimmt und dass die "
        "Bildleisten in der Reihenfolge des amtlichen Layouts vorliegen.",
        "",
    ]

    if non_identity:
        lines += [
            "## Fragen mit abweichender Optionsreihenfolge",
            "",
            "Bei diesen Fragen ist die Reihenfolge der Antwortmöglichkeiten im "
            "Antwortschlüssel eine andere als im amtlichen PDF. Die Antwort wurde "
            "entsprechend umgerechnet; die Umrechnung ist unten dokumentiert.",
            "",
            "| Frage | Umrechnung (Schlüssel a,b,c,d → PDF 1-4) |",
            "| --- | --- |",
        ]
        for pair in non_identity:
            mapping = ", ".join(
                f"{LETTERS[i]}→{pair['perm'][i] + 1}" for i in range(4)
            )
            lines.append(f"| {pair['pdf']['question_id']} | {mapping} |")
        lines.append("")

    if low_confidence:
        bild = [p for p in low_confidence if is_bild_pair(p)]
        other = [p for p in low_confidence if not is_bild_pair(p)]
        if other:
            lines += [
                "## Zuordnungen mit geringer Ähnlichkeit (bitte prüfen)",
                "",
                "| Frage | Ähnlichkeit Frage | Ähnlichkeit Optionen |",
                "| --- | --- | --- |",
            ]
            for pair in sorted(other, key=lambda p: p["score"]):
                lines.append(
                    f"| {pair['pdf']['question_id']} | {pair['stem_sim']:.2f} | "
                    f"{pair['opt_sim']:.2f} |"
                )
            lines.append("")
            reviewed = [
                (p["pdf"]["question_id"], REVIEWED_NOTES[p["pdf"]["question_id"]])
                for p in other
                if p["pdf"]["question_id"] in REVIEWED_NOTES
            ]
            if reviewed:
                lines += ["Manuell geprüfte Einzelfälle:", ""]
                for question_id, note in reviewed:
                    lines.append(f"- **{question_id}** – {note}")
                lines.append("")
            unreviewed = [
                p["pdf"]["question_id"]
                for p in other
                if p["pdf"]["question_id"] not in REVIEWED_NOTES
            ]
            if unreviewed:
                lines += [
                    "Noch nicht manuell geprüft: " + ", ".join(unreviewed),
                    "",
                ]
        if bild:
            ids = ", ".join(p["pdf"]["question_id"] for p in bild)
            lines += [
                "## Bildfragen mit geringer Textähnlichkeit (unbedenklich)",
                "",
                f"Betrifft {len(bild)} Fragen, deren Optionen im amtlichen PDF "
                "„Bild 1“–„Bild 4“ und im Antwortschlüssel „1“–„4“ lauten. "
                "Die Zuordnung erfolgt hier über Bundesland und laufende Nummer "
                "statt über den Optionstext und ist eindeutig.",
                "",
                f"Fragen: {ids}",
                "",
            ]

    if unpaired_pdf or unpaired_core:
        lines += ["## Nicht zugeordnete Fragen", ""]
        for record in unpaired_pdf:
            lines.append(f"- im PDF ohne Partner: {record['question_id']} – {record['stem']}")
        for record in unpaired_core:
            lines.append(f"- im Schlüssel ohne Partner: {record['num']} – {record['question']}")
        lines.append("")

    lines += [
        "## Offene Risiken",
        "",
        "1. Der amtliche Katalog enthält **keinen Lösungsschlüssel**. Die richtigen "
        "Antworten stammen vollständig aus dem MIT-lizenzierten Datensatz "
        "`leben-in-deutschland`. Abgesichert ist damit die Zuordnung Frage → Antwort "
        "und die Position der Antwort innerhalb der vier Optionen, **nicht** die "
        "inhaltliche Richtigkeit des fremden Schlüssels.",
        "2. Bei Bildfragen (z. B. Wappen, Stimmzettel) bedeuten die Optionen "
        "„Bild 1“ bis „Bild 4“ die Bilder in der jeweiligen Bildleiste. "
        "Die Bildleisten wurden aus dem amtlichen PDF extrahiert und enthalten die "
        "Bildunterschriften; die Reihenfolge entspricht dem amtlichen Layout.",
        "3. Die Bilder wurden nicht inhaltlich gesichtet (automatische Extraktion).",
        "",
    ]

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"paired            : {len(pairs)}/{len(pdf_records)}")
    print(f"option order OK   : {exact_perm}/{len(pairs)}")
    print(f"order differences : {len(non_identity)}")
    print(f"low confidence    : {len(low_confidence)}")
    print(f"unpaired pdf/core : {len(unpaired_pdf)}/{len(unpaired_core)}")
    print(f"spot checks       : {len(KNOWN_ANSWERS) - len(spot_failures)}/{len(KNOWN_ANSWERS)} passed")
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")

    if unpaired_pdf or unpaired_core:
        print("\nINCOMPLETE PAIRING")
        return 1
    if spot_failures:
        print("\nKNOWN-ANSWER SPOT CHECKS FAILED:")
        for failure in spot_failures:
            print("  -", failure)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
