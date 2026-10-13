# subgraph-sat-solver-econ

Python-Implementierung der zentralen Aussagen der wissenschaftlichen Arbeit „Wirtschaftliche Konsequenzen eines effizienten SAT-Solvers".

Dieses Repository bietet ein strukturiertes Framework, das die in der Arbeit beschriebenen ökonomischen Entscheidungsprobleme als SAT-/CNF-Modelle kodiert, einfache SAT-Löser zum Testen enthält und eine native Shim-Schnittstelle zum C++-SAT-Solver (Stub) bereitstellt.

## Aktueller Stand (aktualisiert)

- Quellcode liegt flach unter `src/` (keine zusätzliche Paket-Ebene).
- Implementierte Module (Auswahl):
  - `src/solver.py` – DPLL-basierte Kleine-SAT-Engine (`solve_cnf`) und Hilfstyp `SATResult`.
  - `src/foundation.py` – Grundlegende Tseitin-Gadgets, 3-CNF-Transformation, Vergleichs- und Summiergadgets.
  - `src/encodings.py` / `src/models.py` (frühere Versionen) – Hilfsfunktionen zur Kodierung (historisch erhalten).
  - `src/decision.py` – Entscheidungen, Wohlfahrtsfunktionen, Pareto/lexikographische Werkzeuge.
  - `src/auctions.py` – Kodierung der Winner Determination Problem (WDP) und VCG-Hilfen.
  - `src/market.py` – Repacking, cycle-exchange / Matching-Modelle.
  - `src/production.py` – Scheduling- und Produktkonfigurations-Kodierungen.
  - `src/games.py` – Kemeny, Nash/Approx-Gleichgewichte (kompakte, testbare Kodierungen).
  - `src/crypto.py` – symbolische Kodierungen zu Einwegfunktionen / Signaturen (modellhaft).
  - `src/welfare.py` – Wohlfahrtskennzahlen und Informationsgrenzen.
  - `src/native/subgraph_sat_solver_shim.cpp` – C++-Shim (Name: `subgraph_sat_solver_shim`) als native Schnittstelle (aktuell als Stub).
  - `src/__init__.py` – Top-Level Exporte (direkt `src/` als Paketquelle konfiguriert).

- Tests: Vollständige Teststruktur unter `tests/` mit Unit- und Integrationstests für alle Module.
- Projektmetadaten: `pyproject.toml` enthält pytest-/coverage-Konfiguration (HTML-Report nach `doc/coverage/`).

## Architektur (kurz)

Wirtschaftliche Problembeschreibung → Kodierung als CNF → (optional) native Shim → SAT-Solver → Interpretation und Analyse.

Der Entwicklungszweck ist primär reproduzierbare, testbare Kodierungen der Aussagen aus der Arbeit; die native C++-Integration ist als klar benannte Shim-Schnittstelle vorhanden, wird aber standardmäßig als Stub behandelt, damit Tests lokal ohne C++-Toolchain laufen.

## Benutzung (Beispiel)

```bash
git clone https://github.com/naphez86/subgraph-sat-solver-econ.git
cd subgraph-sat-solver-econ
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Kurzes Python-Beispiel:

```python
from solver import solve_cnf
from decision import lexicographic_optimize
from auctions import encode_wdp

m = encode_wdp([[0,1],[1,2],[2]], [1,1,1], threshold=2)
res = solve_cnf(m.clauses)
print('satisfiable=', res.satisfiable)
```

## Tests & Coverage

- `pytest` führt die Test-Suite aus. Die `pyproject.toml`-Konfiguration erzeugt einen HTML-Coverage-Report unter `doc/coverage/`.
- Hinweis: In diesem Chat-Kontext wurden die Tests nicht ausgeführt. Die Testdateien sind angelegt und sollten auf einem Laufzeit-Runner (lokal oder CI) ausgeführt werden.

## Native Shim

Die native Shim-Datei heißt `src/native/subgraph_sat_solver_shim.cpp` und stellt die ABI-Oberfläche für eine spätere echte Anbindung an den C++-Solver dar. Aktuell ist sie als Stub implementiert, um die Entwicklung und Tests von Python-Seite unabhängig zu halten.

## Projektstruktur (vereinfachte Übersicht)

```
subgraph-sat-solver-econ/
├── LICENSE
├── README.md
├── .gitignore
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── solver.py
│   ├── foundation.py
│   ├── encodings.py
│   ├── models.py
│   ├── decision.py
│   ├── auctions.py
│   ├── market.py
│   ├── production.py
│   ├── games.py
│   ├── crypto.py
│   ├── welfare.py
│   └── native/
│       └── subgraph_sat_solver_shim.cpp
└── tests/
    ├── test_solver.py
    ├── test_encodings.py
    ├── test_foundation.py
    ├── test_decision.py
    ├── test_auctions.py
    ├── test_market.py
    ├── test_production.py
    ├── test_games.py
    ├── test_crypto.py
    └── test_welfare.py
```

## Nächste Schritte / Empfehlungen

- CI: Ich empfehle eine GitHub Actions-Workflow hinzuzufügen, um `pytest --cov=src --cov-report=html:doc/coverage` automatisch auszuführen und die Coverage sichtbar zu machen.
- Native-Build: Falls du die echte native Bibliothek (`subgraph-sat-solver`) aufbauen möchtest, ergänze die Build-Anweisungen und optional Umgebungsvariablen (z. B. `CSUBGRAPH_LIB_PATH`).

---

Hinweis zur Commit-Historie: Die oben beschriebenen Quell- und Testdateien wurden kürzlich in einem Commit mit der Nachricht "Add source code and tests" in `main` eingefügt. Diese README-Aktualisierung wurde nun separat committet.
