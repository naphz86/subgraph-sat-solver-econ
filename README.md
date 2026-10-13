# subgraph-sat-solver-econ

Python-Modelle ökonomischer Entscheidungsprobleme treffen hier auf einen leistungsfähigen SAT-Solver in C++: Das Projekt `subgraph-sat-solver` reduziert SAT systematisch über 3-SAT und Clique auf das exakte Subgraph-Problem. Auktionen, Märkte, Planung, Konfiguration, Spiele und Wahlen aus diesem Repository lassen sich als SAT-Instanzen formulieren und mit austauschbaren Entscheidern untersuchen. Die C++-Reduktionskette ist das zentrale Integrationsziel; DPLL und die Python-Referenz dienen zum Vergleichen und Testen. Die theoretische Grundlage ist die Arbeit des Autors, siehe [Wissenschaftlicher Hintergrund](#wissenschaftlicher-hintergrund).

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-72%20passed-4c1)](tests/)
[![Test Coverage](https://img.shields.io/badge/Test%20Coverage-91%25-brightgreen)](doc/coverage/index.html)
[![scicov](https://img.shields.io/badge/scicov-10-ff69b4)](doc/coverage/index.html)

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Kernfeature: C++-SAT-Solver](#kernfeature-c-sat-solver)
- [Reduktionskette](#reduktionskette)
- [Projektstruktur](#projektstruktur)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Grundkonzepte](#grundkonzepte)
- [Verwendung](#verwendung)
- [Schnittstelle zum Subgraph-Programm](#schnittstelle-zum-subgraph-programm)
- [Anbindung des C++-Solvers](#anbindung-des-c-solvers)
- [Tests](#tests)
- [Wissenschaftlicher Hintergrund](#wissenschaftlicher-hintergrund)
- [Erwerb](#erwerb)

## Überblick

Die Arbeit untersucht, welche Folgen ein exakter und effizienter SAT-Entscheider für die Wirtschaft hätte. Dieses Repository macht die dort bewiesenen Konstruktionen ausführbar und überprüfbar. Im Zentrum steht nicht nur die Modellierung in Python, sondern die Verbindung dieser Modelle mit dem eigenständigen C++-Projekt [`subgraph-sat-solver`](https://github.com/naphez86/subgraph-sat-solver):

- ein Schaltkreis-Baukasten mit Tseitin-Kodierung, Addierern, Vergleichern und Summierern (`circuits`),
- das Modell eines wirtschaftlichen Optimierungsproblems sowie die Verfahren „Entscheiden ⇒ Finden" und „Optimieren aus Entscheiden" (`foundation`),
- Kodierungen und Löser für Entscheidungstheorie, Auktionen (einschließlich VCG), Märkte, Produktion, Spiele, Kryptographie und Wohlfahrtsmodelle,
- mehrere SAT-Entscheider hinter einer gemeinsamen Schnittstelle (`backends`), darunter die native C++-Reduktionskette, eine Python-Referenz und unabhängige DPLL- und Enumerations-Backends,
- ein exaktes Subgraph-Orakel, das ausschließlich die Standardbibliothek benötigt (`oracle`).

Alle ökonomischen Algorithmen sprechen die Schnittstelle `SatBackend` an. Dadurch kann dieselbe SAT-Kodierung je nach Einsatz mit dem C++-Solver, der Python-Referenz, DPLL oder vollständiger Enumeration gelöst und verglichen werden.

Die Aussagen der Arbeit sind zum Teil konditional, das heißt, sie gelten unter einer Effizienzhypothese für den SAT-Entscheider. Dieses Repository führt keinen Beweis für diese Hypothesen. Es setzt die Konstruktionen um, zählt Entscheideraufrufe und erlaubt Messungen auf kleinen und mittleren Instanzen.

## Kernfeature: C++-SAT-Solver

Das zentrale Rechen-Backend ist [`subgraph-sat-solver`](https://github.com/naphez86/subgraph-sat-solver): ein eigenständiges C++17-Projekt, das eine CNF-Formel nicht mit einem eingebetteten Python-SAT-Verfahren löst, sondern sie in einer expliziten Reduktionskette an einen Subgraph-Entscheider weitergibt. Die ökonomischen Modelle in diesem Repository erzeugen die SAT-Formeln; die C++-Bibliothek `satlib` und das Programm `SubgraphSATSolver` bilden den leistungsfähigen nativen Solver-Kern.

### Was der C++-Solver ausführt

1. **CNF einlesen und prüfen:** Der Solver verarbeitet DIMACS-CNF und stellt Variablen, Klauseln und Belegungen in C++-Datenstrukturen bereit.
2. **Auf 3-SAT reduzieren:** Klauseln mit mehr als drei Literalen werden mit frischen Hilfsvariablen auf höchstens drei Literale pro Klausel aufgeteilt.
3. **Auf Clique reduzieren:** Für jedes Literalvorkommen entsteht ein Knoten. Kanten verbinden kompatible Literale aus verschiedenen Klauseln. Eine Clique der Größe der Klauselzahl entspricht einer erfüllenden Auswahl.
4. **Als Subgraph-Instanz formulieren:** Der Clique-Graph wird als Quellgraph `G`, die gesuchte Clique `K_k` als Zielgraph `H` ausgegeben.
5. **Den nativen Subgraph-Entscheider aufrufen:** Das externe Programm entscheidet exakt, ob `H` in `G` enthalten ist, und kann ein Mapping zurückgeben.
6. **Eine SAT-Belegung rekonstruieren und validieren:** Aus dem Mapping gewinnt der Solver eine Belegung und kann sie gegen die ursprüngliche Formel prüfen. Status, Fehler und Phasenlaufzeiten werden im Ergebnis ausgegeben.

`subgraph-sat-solver` stellt sowohl die statische C++-Bibliothek **`satlib`** als auch das Kommandozeilenprogramm **`SubgraphSATSolver`** bereit. Der C++-Solver verwendet dabei das separate Projekt [`csubgraph`](https://github.com/naphez86/csubgraph) als Subgraph-Implementierung. Das sind zwei klar getrennte Rollen: `satlib` orchestriert SAT-Reduktion und Belegungsrekonstruktion; `csubgraph` entscheidet die erzeugte Graphinstanz.

Die Reduktionskette beschreibt den Lösungsweg, ist aber kein Beweis für eine polynomielle Laufzeit auf allgemeinen SAT-Instanzen. Laufzeit- und Effizienzaussagen dieser Arbeit gelten nur unter den jeweils genannten Hypothesen; siehe [Wissenschaftlicher Hintergrund](#wissenschaftlicher-hintergrund).

### C++-Builds und Verwendung

Wenn die beiden Nachbar-Repositories wie in der Entwicklungsumgebung neben diesem Repository liegen, können ihre nativen Ziele gebaut werden:

```powershell
cmake --build ..\subgraph-sat-solver\build --config Release -j 4
cmake --build ..\csubgraph\build --config Release -j 4
```

Der SAT-Solver kann auch eigenständig mit einer DIMACS-Datei verwendet werden. Dabei muss der Pfad zum Subgraph-Programm explizit übergeben werden; unter Windows ist außerdem ein existierendes temporäres Verzeichnis anzugeben:

```powershell
..\subgraph-sat-solver\build\SubgraphSATSolver.exe `
  .\instance.cnf `
  --subgraph-binary ..\csubgraph\build\subgraph.exe `
  --temp-dir $env:TEMP `
  --stats
```

Die Optionen entsprechen der CLI des SAT-Solver-Projekts. Ein vollständiger Aufruf dieser CLI mit dem Subgraph-Programm ist in der aktuellen Windows-Umgebung noch nicht end-to-end verifiziert; die vorhandenen Integrationstests prüfen separat die SAT-Testsuite, die Subgraph-Testsuite und das Subgraph-CLI.

In einem eigenen C++-Projekt kann `satlib` als statische Bibliothek eingebunden werden. Die öffentliche API liegt in `SubgraphSATSolver.h`: `CNFFormula` repräsentiert die Eingabe, `SATSolverConfig` konfiguriert Subgraph-Programm, temporäres Verzeichnis, Validierung und Ausgaben, und `SubgraphSATSolver::solve_formula` liefert `SAT`, `UNSAT`, `UNKNOWN` oder `SAT_ERROR` samt optionalem Modell und Metriken. Der SAT-Solver-Checkout enthält Build- und API-Beispiele.

### Verwendung aus den ökonomischen Python-Modellen

Die Python-Modelle erzeugen Formeln des Typs `Cnf`; die gemeinsame Schnittstelle `SatBackend` ist so ausgelegt, dass dafür auch der native C++-Entscheider genutzt werden kann. [`src/native.py`](./src/native.py) enthält den ctypes-Wrapper `NativeBackend`, und `src/native/wsat_shim.cpp` stellt dafür den C-ABI-Einstieg `wsat_solve` bereit. Um den Shim im aktuellen Layout manuell mit CMake zu bauen, aus dem Repository-Wurzelverzeichnis:

```powershell
cmake -S src/native -B build `
  -DSUBGRAPH_SAT_SOLVER_DIR=..\subgraph-sat-solver `
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 4
```

Anschließend die erzeugte `wsat_shim.dll` mit ihrem tatsächlichen Pfad laden. Der Python-Helper `build_shim()` ist derzeit wegen eines Pfadfehlers nicht verwendbar: Er sucht das CMake-Projekt unter `<repo>\native`, obwohl es unter `src\native` liegt. Außerdem muss der Shim den externen Subgraph-Entscheider ausführen können.

```python
from src.auctions import Bid, solve_wdp
from src.native import NativeBackend, NativeLibrary

library = NativeLibrary.load(r"C:\path\to\wsat_shim.dll")
backend = NativeBackend(
    library,
    subgraph_binary=r"C:\path\to\subgraph.exe",
    work_dir=r"C:\Temp\wsat",
    timeout_sec=60,
)
try:
    bids = [
        Bid(frozenset({0, 1}), 4, agent=0),
        Bid(frozenset({2}), 2, agent=1),
    ]
    result = solve_wdp(bids, backend)
    print(result.revenue, result.winners)
finally:
    backend.close()
```

Der Wrapper validiert ein vom nativen Solver geliefertes Modell erneut mit der ursprünglichen Python-CNF und übersetzt `UNSAT` in `None`; `UNKNOWN` und Fehler werden als `BackendError` sichtbar gemacht. Die vorhandenen Tests bauen den Shim nicht und führen die Python-zu-C++-Bridge nicht end-to-end aus. Die Integrationstests in [`tests/test_native_integration.py`](./tests/test_native_integration.py) führen stattdessen die kompilierten SAT- und Subgraph-C++-Testsuiten sowie das Subgraph-CLI aus. Die direkte SAT-zu-Subgraph-End-to-End-Ausführung über `SubgraphSATSolver.exe` ist damit noch nicht durch diese Tests abgesichert.

## Reduktionskette

```
Ökonomisches Problem  →  Schaltkreis (F, U)  →  CNF (Tseitin)  →  3-SAT  →  Clique  →  Subgraph
```

| Stufe | Beschreibung | Komponente |
|-------|--------------|------------|
| Problem → Schaltkreis | Entscheidungsbits `x`, Zulässigkeit `F`, Zielfunktionen `U` als Bitwörter | `foundation.Problem`, `circuits.CircuitBuilder` |
| Schaltkreis → CNF | Tseitin-Kodierung, höchstens 12 Literalvorkommen je Gatter | `circuits.CircuitBuilder` |
| CNF → 3-SAT | Klauseln mit mehr als drei Literalen werden mit Hilfsvariablen aufgespalten | `cnf.Cnf.to_3cnf` |
| 3-SAT → Clique | Ein Knoten je Literalvorkommen, Kanten zwischen Knoten verschiedener Klauseln mit nicht widersprüchlichen Literalen. Eine Clique der Größe m (Klauselzahl) existiert genau dann, wenn die Formel erfüllbar ist | `reduction.three_sat_to_clique`, `reduction.sat_to_clique` |
| Clique → Subgraph | Der Clique-Graph ist der Quellgraph, der vollständige Graph K_m der Zielgraph | `reduction.CliqueReduction`, `reduction.subgraph_instance_json` |
| Subgraph-Entscheidung | Exakte Suche nach einer kantenerhaltenden, injektiven Abbildung H → G | `oracle.find_embedding` |
| Belegung | Aus der Einbettung wird die Belegung der ursprünglichen Variablen abgeleitet | `reduction.extract_assignment` |

Auktionsprobleme besitzen zusätzlich eine direkte Reduktion auf Clique (Kompatibilitätsgraph beziehungsweise Zwillingsgraph), siehe `auctions.compatibility_graph` und `auctions.twin_graph`.

## Projektstruktur

| Datei | Inhalt |
|-------|--------|
| `src/cnf.py` | Klasse `Cnf`: Klauseln, DIMACS-Ein- und Ausgabe, Auswertung, Substitution `restrict`, Umwandlung in 3-CNF, Größe |φ| als Zahl der Literalvorkommen |
| `src/circuits.py` | `CircuitBuilder`: Gatter mit Konstantenfaltung, Volladdierer, Summierer, Multiplikation, Vergleicher, Minimum |
| `src/backends.py` | SAT-Entscheider: `DpllBackend`, `ChainBackend`, `BruteForceBackend`, außerdem `CountingBackend` und `DecisionOnlyBackend` |
| `src/reduction.py` | Klasse `Graph`, Reduktion 3-SAT → Clique, JSON-Serialisierung der Subgraph-Instanz, Extraktion der Belegung |
| `src/oracle.py` | Exaktes Subgraph-Orakel (Cliquensuche mit Bitmengen, Backtracking für allgemeine Zielgraphen) mit Kommandozeilenschnittstelle |
| `src/foundation.py` | `Problem`, Selbstreduzierbarkeit (`selfreduce`), Optimierung (`maximize`, `minimize`), Zeugensuche, Größen- und Laufzeitschranken |
| `src/decision.py` | Nutzen, rationale Wahl, lexikographische Optimierung, Pareto-Front, soziale Wohlfahrt, Erwartungsnutzen, Maximin, Minimax-Regret, CEGAR für robuste Entscheidungen |
| `src/auctions.py` | Kombinatorische Auktionen: Gebote, Winner Determination, VCG, Reduktion auf Clique und Subgraph, NP-Härte-Konstruktion |
| `src/markets.py` | Frequenzzuteilung (Station Repacking) und Nierenaustausch als Zyklenpackung |
| `src/production.py` | Terminplanung, Produktkonfiguration (`Configurator`), Standortplanung |
| `src/games.py` | Normalformspiele, Näherungsgleichgewichte, Kemeny-Rangaggregation, Manipulation von Wahlregeln |
| `src/crypto.py` | Urbildsuche für Schaltkreise, Proof-of-Work, One-Time-Pad (Demonstration der Aussagen zu Einwegfunktionen) |
| `src/welfare.py` | Wohlfahrtsmodell: Rechenlücke, Gesamtoutput, relativer Zugewinn, Kommunikationsbedarf |
| `src/native.py` | Python-Anbindung (ctypes) des C++-Solvers: `NativeLibrary`, `NativeBackend`, `build_shim` |
| `src/native/wsat_shim.h`, `src/native/wsat_shim.cpp` | C-Schnittstelle (`wsat_solve`) um die C++-Bibliothek des Subgraph-SAT-Solvers |
| `src/native/CMakeLists.txt` | Build des Shims als Shared Library `wsat_shim` |
| `src/solver.py` | Eigenständiger DPLL-Löser als Python-Referenz und unabhängiges Vergleichs-Backend |
| `src/native/subgraph_sat_solver_shim.cpp` | Altbestand früherer Versionen; nicht Teil des aktuellen CMake-Builds |
| `tests/` | Testdateien je Modul |
| `science/subgraph-sat-solver-econ.tex`, `.pdf` | Wissenschaftliche Arbeit (Quelltext und PDF) |
| `pyproject.toml` | Projektmetadaten sowie pytest- und Coverage-Konfiguration |
| `LICENSE` | Lizenzbedingungen |

## Voraussetzungen

- Python ab Version 3.11
- Für die Python-Module (`cnf`, `circuits`, `backends`, `reduction`, `oracle`, `foundation` und alle Anwendungsmodule) wird ausschließlich die Standardbibliothek benötigt.
- Für Tests: `pytest` und `pytest-cov`
- Nur für die Anbindung des C++-Solvers: CMake ab Version 3.16, ein Compiler mit C++17-Unterstützung und ein Checkout des Projekts subgraph-sat-solver (Dateien `Cnf.cpp`, `Reduction.cpp`, `SubgraphSATSolver.cpp` und `SubgraphSATSolver.h`)

## Installation

```bash
git clone https://github.com/naphez86/subgraph-sat-solver-econ.git
cd subgraph-sat-solver-econ
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Unter Windows wird das Virtual Environment mit `.venv\Scripts\activate` aktiviert.

`pyproject.toml` deklariert die Abhängigkeiten `numpy` und `subgraph`. Der Quellcode des Projekts importiert beide derzeit nicht, der exakte Entscheider ist in `src/oracle.py` enthalten. Zum reinen Ausführen der Beispiele genügt Python.

Die Module liegen flach unter `src/` und werden aus dem Wurzelverzeichnis des Repositories über das Paket `src` importiert, zum Beispiel `from src.backends import DpllBackend`. Alle Beispiele dieser README sind von dort aus auszuführen.

## Grundkonzepte

**Literale und Belegungen.** Literale sind von 0 verschiedene ganze Zahlen (DIMACS-Konvention): `+v` bezeichnet die Variable `v`, `-v` ihre Negation. Eine Belegung ist ein `dict[int, bool]`.

**Signale.** Im Schaltkreis-Baukasten ist ein Signal entweder ein Literal (`int`) oder eine Konstante (`bool`). Konstanten werden beim Aufbau gefaltet. Ein Wort ist eine Liste von Signalen, Bit 0 zuerst.

**Entscheider (Backends).** Ein Entscheider liefert zu einer `Cnf` eine erfüllende Belegung oder `None`.

| Klasse | Beschreibung |
|--------|--------------|
| `DpllBackend` | DPLL mit Einheitspropagation, unabhängig von der Subgraph-Kette. Schneller Standard für Kodierungen und Tests |
| `ChainBackend` | Python-Referenz der Kette CNF → 3-SAT → Clique → Subgraph mit dem exakten Orakel. Jede Antwort wird gegen die ursprüngliche Formel geprüft |
| `BruteForceBackend` | Vollständige Enumeration, höchstens 22 Variablen. Unabhängige Referenz für kleine Formeln |
| `NativeBackend` | C++-Solver über den Shim, siehe [Anbindung des C++-Solvers](#anbindung-des-c-solvers) |
| `CountingBackend` | Hüllklasse, die die Aufrufe eines Entscheiders zählt |
| `DecisionOnlyBackend` | Hüllklasse, die nur die Entscheidung `is_sat` freigibt und keine Modelle liefert. Damit lässt sich prüfen, dass ein Algorithmus mit einem reinen Entscheider auskommt |

**Optimierung aus Entscheidung.** Die Optimierungsfunktionen (`maximize`, `minimize` und alle darauf aufbauenden Löser) benötigen standardmäßig nur die Entscheidung `is_sat`. Der Optimalwert wird durch binäre Suche bestimmt, die Optimallösung durch Selbstreduktion. Die Zahl der Entscheideraufrufe ist höchstens `L + n + 2` (`L` Bitbreite der Zielfunktion, `n` Zahl der Entscheidungsbits), siehe `foundation.opt_call_bound`. Mit `use_models=True` wird stattdessen das Modell des Entscheiders gelesen. Das spart Aufrufe, setzt aber einen Entscheider voraus, der Modelle liefert.

## Verwendung

### SAT-Formeln und Entscheider

```python
from src.cnf import Cnf
from src.backends import DpllBackend, ChainBackend

cnf = Cnf.from_dimacs("""p cnf 3 3
1 -2 0
2 3 0
-1 -3 0
""")

print(cnf.num_vars, cnf.num_clauses, cnf.size)    # 3 3 6

model = DpllBackend().solve(cnf)
print(model, cnf.evaluate(model))                 # {1: False, 2: False, 3: True} True

chain_model = ChainBackend().solve(cnf)           # Kette über das Subgraph-Orakel
print(chain_model, cnf.evaluate(chain_model))     # {1: True, 2: True, 3: False} True
```

Verschiedene Entscheider können verschiedene erfüllende Belegungen liefern. Für dieselbe Formel stimmen sie in der Antwort erfüllbar oder unerfüllbar überein.

Formeln lassen sich auch direkt aufbauen und als DIMACS ausgeben:

```python
from src.cnf import Cnf

cnf = Cnf()
x, y = cnf.new_vars(2)
cnf.add_clause(x, y)
cnf.add_clause(-x, y)
print(cnf.to_dimacs())
```

### Reduktionskette und Subgraph-Orakel

```python
from src.cnf import Cnf
from src.reduction import sat_to_clique, extract_assignment, subgraph_instance_json
from src.oracle import find_embedding

cnf = Cnf.from_dimacs("p cnf 3 3\n1 -2 0\n2 3 0\n-1 -3 0\n")

red = sat_to_clique(cnf)
print(red.graph.n, red.graph.num_edges, red.k)    # 6 9 3

mapping = find_embedding(red.graph.adj, red.target.adj)
print(mapping)                                    # [0, 2, 5]
print(extract_assignment(red, mapping))           # {1: True, 2: True, 3: False}

# Eingabe für ein externes Subgraph-Programm
instance_json = subgraph_instance_json(red.graph, red.target)
```

`red.graph` ist der Clique-Graph, `red.target` der vollständige Graph K_m. Ein Mapping ist die Zuordnung der Knoten von K_m auf Knoten des Clique-Graphen; daraus folgt die Belegung.

### Optimierung aus Entscheidung

```python
from src.foundation import Problem, maximize
from src.backends import CountingBackend, DpllBackend

problem = Problem(3)                              # drei Entscheidungsbits
x = problem.x
problem.cnf.add_clause(-x[0], -x[2])              # Bit 0 und Bit 2 nicht zugleich

objective = problem.cb.weighted_sum(x, [2, 3, 4]) # Zielfunktion 2*x0 + 3*x1 + 4*x2
problem.add_objective(objective)

backend = CountingBackend(DpllBackend())
result = maximize(problem, objective, backend)
print(result.value, result.x, backend.calls)      # 7 [False, True, True] 9
```

### Kombinatorische Auktionen und VCG

```python
from src.auctions import Bid, solve_wdp, vcg
from src.backends import DpllBackend

bids = [
    Bid(frozenset({0, 1}), 4, agent=0),
    Bid(frozenset({1, 2}), 3, agent=1),
    Bid(frozenset({2}),    2, agent=2),
]

wdp = solve_wdp(bids, DpllBackend())
print(wdp.revenue, wdp.winners)                   # 6 [0, 2]

result = vcg(bids, DpllBackend())
print(result.winners, result.payments)            # [0, 2] {0: 1, 1: 0, 2: 0}
```

Jedes Gebot besteht aus einer Gütermenge, einem Preis und optional einem Agenten (XOR-Bietersprache). Für VCG ist ein Agent je Gebot erforderlich.

Bei Einheitspreisen lässt sich die Frage „Erlös mindestens k" direkt als Subgraph-Frage stellen:

```python
from src.auctions import Bid, revenue_at_least_via_subgraph, auction_subgraph_instance

bids = [Bid(frozenset({0, 1}), 1), Bid(frozenset({2}), 1), Bid(frozenset({1, 2}), 1)]

print(revenue_at_least_via_subgraph(bids, 2))     # True
print(revenue_at_least_via_subgraph(bids, 3))     # False

json_text = auction_subgraph_instance(bids, 2)    # {"G": ..., "H": ...} für ein externes Programm
```

### Märkte: Frequenzzuteilung und Nierenaustausch

```python
from src.markets import Repacking, solve_repacking, solve_kidney
from src.backends import DpllBackend

# Zwei Stationen, je zwei Kanäle; gleiche Kanäle sind untereinander verboten
rep = Repacking(
    domains={"A": [1, 2], "B": [1, 2]},
    forbidden={("A", 1, "B", 1), ("A", 2, "B", 2)},
)
print(solve_repacking(rep, DpllBackend()))        # {'A': 2, 'B': 1}

# Austausch als Packung knotendisjunkter Zyklen der Länge höchstens 3
arcs = [(0, 1), (1, 0), (2, 3), (3, 2), (1, 2)]
kidney = solve_kidney(4, arcs, 3, DpllBackend())
print(kidney.value, kidney.cycles)                # 4 [(0, 1), (2, 3)]
```

### Produktion: Planung, Konfiguration, Standortwahl

```python
from src.cnf import Cnf
from src.production import Job, optimal_schedule, Configurator, solve_ufl
from src.backends import DpllBackend

backend = DpllBackend()

# Einmaschinenplanung; Job(Freigabe, Endtermin, Dauer, Gewicht)
jobs = [Job(0, 6, 2, 3), Job(0, 6, 3, 1), Job(1, 7, 2, 2)]
plan = optimal_schedule(jobs, backend)
print(plan.value, plan.starts)                    # 25 {0: 0, 1: 2, 2: 5}

# Produktkonfiguration: Dokumentation als CNF über Optionen
doc = Cnf.from_dimacs("p cnf 3 3\n-1 -2 0\n1 3 0\n-3 0\n")
configurator = Configurator(doc)
print(configurator.classify(backend))             # {1: 'mandatory', 2: 'never', 3: 'never'}
print(configurator.is_realizable([1, 2], backend))  # False

# Standortplanung: Eröffnungskosten je Fabrik, Zuordnungskosten Fabrik x Kunde
ufl = solve_ufl([3, 4], [[1, 5, 6], [6, 2, 1]], backend)
print(ufl.cost, ufl.open_facilities, ufl.assignment)  # 11 {0, 1} {0: 0, 1: 1, 2: 1}
```

### Entscheidungstheorie

```python
from src.foundation import Problem
from src.decision import lexicographic, pareto_front, cegar_robust
from src.backends import DpllBackend

backend = DpllBackend()

problem = Problem(3)
x, cb = problem.x, problem.cb
problem.cnf.add_clause(-x[0], -x[1])
u1 = cb.weighted_sum(x, [3, 2, 1])
u2 = cb.weighted_sum(x, [1, 2, 3])

lex = lexicographic(problem, [u1, u2], backend)   # u1 vor u2
print(lex.values, lex.x)                          # [4, 4] [True, False, True]

front = pareto_front(problem, [u1, u2], backend)
print(front.front)                                # [(3, 5), (4, 4)]

# Robuste Entscheidung "es gibt a, sodass für alle s gilt ok(a, s)" per CEGAR
def ok(cb, a, s):
    return cb.and_(cb.or_(a[0], s[0]), cb.or_(a[1], cb.neg(s[0])))

robust = cegar_robust(2, 1, ok, backend)
print(robust.robust, robust.a)                    # True [True, True]
```

### Spiele und kollektive Entscheidungen

```python
from fractions import Fraction
from src.games import (NormalFormGame, nash_equilibria_2p, eps_nash_from_exact,
                       is_eps_nash, solve_kemeny)
from src.backends import DpllBackend

# Gefangenendilemma als Bimatrixspiel
a = [[3, 0], [5, 1]]
b = [[3, 5], [0, 1]]
equilibria = nash_equilibria_2p(a, b)
print(equilibria)   # [([0, 1], [0, 1])] mit Fraction-Werten: beide spielen die zweite Aktion

game = NormalFormGame.bimatrix(a, b)
eps = Fraction(1, 100)
profile = eps_nash_from_exact(game, equilibria[0], eps)
print(is_eps_nash(game, profile, eps))            # True

# Kemeny-Konsensrangfolge aus drei Stimmzetteln über die Kandidaten 0, 1, 2
ballots = [[0, 1, 2], [0, 2, 1], [1, 0, 2]]
kemeny = solve_kemeny(3, ballots, DpllBackend())
print(kemeny.order, kemeny.cost)                  # [0, 1, 2] 2
```

### Kryptographie und Wohlfahrtsmodell

```python
from fractions import Fraction
from src.crypto import toy_mixer, evaluate, invert
from src.welfare import welfare_gain, communication_requirement
from src.backends import DpllBackend

# Urbildsuche für eine kleine nichtlineare Funktion (nur Demonstration)
bits = [True, False, True, True, False, False]
target = evaluate(toy_mixer, bits)
preimage = invert(toy_mixer, 6, target, DpllBackend())
print(evaluate(toy_mixer, preimage) == target)    # True

# Relativer Wohlfahrtszugewinn bei Anteil alpha = 10 % und mittlerer Lücke 5 %
print(welfare_gain(Fraction(1, 10), Fraction(1, 20)))   # 1/199
print(communication_requirement(10))              # 1023
```

Die Funktion `toy_mixer` ist ausdrücklich nicht kryptographisch. Das Modul `crypto` illustriert die konditionale Aussage der Arbeit an kleinen Eingabelängen und ist kein Angriff auf reale Verfahren.

### Kommandozeile: Subgraph-Orakel

Das Orakel kann als eigenständiges Programm gestartet werden. Es liest eine Instanz im [beschriebenen JSON-Format](#schnittstelle-zum-subgraph-programm) und schreibt das Ergebnis in eine Ausgabedatei:

```bash
python -m src.oracle input.json output.json
```

Ein Zeitlimit in Sekunden wird über die Umgebungsvariable `SUBGRAPH_ORACLE_TIME_LIMIT` gesetzt, zum Beispiel `SUBGRAPH_ORACLE_TIME_LIMIT=60 python -m src.oracle input.json output.json`.

| Exit-Code | Bedeutung |
|-----------|-----------|
| 0 | Instanz entschieden, Ergebnis in `output.json` |
| 2 | Ungültige Eingabe oder falsche Argumente |
| 3 | Zeitlimit überschritten |

## Schnittstelle zum Subgraph-Programm

Der C++-Solver ruft das Subgraph-Programm als eigenen Prozess auf:

```
<subgraph-binary> <input.json> <output.json>
```

Eingabe (`input.json`): ein JSON-Objekt mit zwei ungerichteten Graphen. `G` ist der Quellgraph (Clique-Graph), `H` der Zielgraph (vollständiger Graph K_k). Die Knoten heißen `v0`, `v1`, ... in der Reihenfolge ihrer Nummerierung.

```json
{
  "G": { "nodes": ["v0", "v1", "v2"], "edges": [["v0", "v1"], ["v1", "v2"]] },
  "H": { "nodes": ["v0", "v1"],       "edges": [["v0", "v1"]] }
}
```

Ausgabe (`output.json`): Das Programm beendet sich mit Exit-Code 0 und schreibt `{"is_subgraph": true, "mapping": [...]}` oder `{"is_subgraph": false}`. Die Schreibweise `"is_subgraph": true` mit Leerzeichen ist verbindlich, der Solver prüft auf genau diese Zeichenfolge. `mapping[i]` ist der Index (Position in `G.nodes`) des Quellknotens, auf den der i-te Knoten von `H` abgebildet wird. Aus dem Mapping leitet der Solver die Belegung ab. Ein Exit-Code ungleich 0 führt zum Status `SAT_ERROR`.

`oracle.py` erfüllt diese Schnittstelle. Gesucht wird eine injektive, kantenerhaltende Abbildung H → G (nicht notwendig induziert). Die Antworten sind exakt und nie heuristisch.

## Anbindung des C++-Solvers

Die Architektur, die CMake-Build-Anleitung und ein Python-Beispiel sind im Abschnitt [Kernfeature: C++-SAT-Solver](#kernfeature-c-sat-solver) beschrieben. Dort sind auch der aktuelle Stand des Shims und die Abgrenzung der vorhandenen C++-Integrationstests dokumentiert.

## Tests

```bash
pytest
```

Die Konfiguration in `pyproject.toml` setzt `tests` als Testverzeichnis, `.` und `src` als Importpfade und erzeugt einen Coverage-Bericht im Terminal sowie als HTML unter `doc/coverage/`.

Die Python-Tests verwenden `DpllBackend` und `ChainBackend` als Referenzentscheider. Die Integrationstests in `tests/test_native_integration.py` rufen zusätzlich die bereits gebauten C++-Testsuiten `sat-tests` und `subgraph-tests` sowie die `subgraph`-CLI auf. Standardmäßig werden die benachbarten Checkouts `../subgraph-sat-solver/build` und `../csubgraph/build` verwendet. Andere Build-Verzeichnisse können über `SUBGRAPH_SAT_SOLVER_BUILD_DIR` und `CSUBGRAPH_BUILD_DIR` angegeben werden. Fehlt ein Build-Artefakt, wird der jeweilige Integrationstest übersprungen.

## Wissenschaftlicher Hintergrund

Die Arbeit „Wirtschaftliche Konsequenzen eines effizienten SAT-Solvers" liegt als Quelltext und PDF unter `science/` bei. Sie ergänzt die Grundarbeit „SAT-Erfüllbarkeit von booleschen Schaltkreisen und die Konsequenzen", die hier veröffentlicht ist: https://github.com/naphets86/odd/tree/main/science/lsat/science

Die Arbeit unterscheidet drei Effizienzhypothesen: (E_T) einen deterministischen SAT-Entscheider mit Laufzeit T(N), (E_poly) dasselbe mit polynomiellem T und (S₃) einen exakten Subgraph-Entscheider mit Laufzeit c·|V(G)|³ auf Clique-Instanzen. Jede Aussage ist als unbedingt, konditional oder zitiert gekennzeichnet. Dieses Repository liefert Implementierungen der Konstruktionen und führt keinen eigenen Beweis.

Zuordnung der Kapitel zu den Modulen:

| Kapitel der Arbeit | Modul |
|--------------------|-------|
| 2 Formales Fundament | `cnf`, `circuits`, `foundation` |
| 3 Entscheidungstheorie | `decision` |
| 4 Kombinatorische Auktionen und Mechanismen | `auctions` |
| 5 Märkte mit Nebenbedingungen | `markets` |
| 6 Produktion, Logistik und Konfiguration | `production` |
| 7 Spiele, Gleichgewichte und kollektive Entscheidungen | `games` |
| 8 Kryptographie, Zahlungsverkehr und Sicherheit | `crypto` |
| 9 Wohlfahrtsmodell und Informationsgrenzen | `welfare` |
| 10 Grenzen, Messplan und Fazit | `backends`, `native`, `oracle` |

Die Reduktion von 3-SAT auf das Clique-Problem folgt der klassischen Konstruktion der Komplexitätstheorie (Karp, Cook).

## Erwerb

Der Preis für diese Software beträgt 4.945.000,00 EUR.

### Zahlungsinformationen

Name: Stephan Epp  
IBAN: DE24 5003 1900 0012 5603 20
BIC: BBVADEFFXXX
