/**
 * wsat_shim.h
 *
 * C-ABI-Shim um die C++-Bibliothek des Subgraph-SAT-Solvers (satlib).
 * Der Shim übersetzt zwischen der C++-API (sat::SubgraphSATSolver) und einer stabilen,
 * von Python (ctypes) aufrufbaren C-Schnittstelle. Es werden keine C++-Ausnahmen und
 * keine C++-Typen über die Grenze gereicht.
 */
#ifndef WSAT_SHIM_H
#define WSAT_SHIM_H

#include <stddef.h>

#if defined(_WIN32)
#  define WSAT_API __declspec(dllexport)
#else
#  define WSAT_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define WSAT_ABI_VERSION 1

/* Statuscodes von wsat_solve */
#define WSAT_UNSAT    0
#define WSAT_SAT      1
#define WSAT_UNKNOWN (-1)
#define WSAT_ERROR   (-2)

/* Laufzeiten der einzelnen Phasen in Millisekunden */
typedef struct wsat_stats {
    double reduction_ms;
    double subgraph_ms;
    double extraction_ms;
    double total_ms;
    int num_variables;
    int num_clauses;
} wsat_stats;

/** ABI-Version des Shims (Vergleich mit WSAT_ABI_VERSION). */
WSAT_API int wsat_abi_version(void);

/**
 * Löst eine CNF mit dem Subgraph-SAT-Solver.
 *
 * @param clauses        Klauseln im DIMACS-Stil als flaches Array: Literale, jede Klausel
 *                       mit 0 abgeschlossen (die leere Klausel ist eine einzelne 0).
 * @param n_ints         Länge von `clauses` (Anzahl der ints, inklusive Nullen).
 * @param num_vars       Anzahl der Variablen (>= 0).
 * @param subgraph_binary Pfad zum Subgraph-Programm (<programm> <input.json> <output.json>).
 * @param temp_dir       Verzeichnis für temporäre Dateien.
 * @param timeout_sec    Zeitlimit (vom Solver nur an die Konfiguration übergeben).
 * @param validate       != 0: Belegung vom Solver gegen die Formel prüfen lassen.
 * @param verbose        != 0: Diagnoseausgaben des Solvers zulassen (sonst unterdrückt).
 * @param model_out      Puffer mit model_len >= num_vars + 1 Einträgen; bei WSAT_SAT enthält
 *                       model_out[v] (1 <= v <= num_vars) 1 (wahr) oder 0 (falsch).
 * @param stats          Optional (darf NULL sein): Laufzeiten und Größen.
 * @param error_out      Optionaler Puffer für eine Fehlermeldung (darf NULL sein).
 * @return WSAT_SAT, WSAT_UNSAT, WSAT_UNKNOWN oder WSAT_ERROR.
 */
WSAT_API int wsat_solve(const int* clauses, size_t n_ints, int num_vars,
                        const char* subgraph_binary, const char* temp_dir,
                        int timeout_sec, int validate, int verbose,
                        signed char* model_out, size_t model_len,
                        wsat_stats* stats,
                        char* error_out, size_t error_len);

#ifdef __cplusplus
}
#endif

#endif /* WSAT_SHIM_H */
