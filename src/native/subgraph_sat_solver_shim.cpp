// C++ shim for the subgraph-sat-solver library.
// This is a minimal compatibility layer, intentionally lightweight and intentionally
// not built during the repository update. It gives the repository a clear native surface
// analogous to the shim pattern used elsewhere.

#include <cstddef>

extern "C" {

int subgraph_sat_solver_abi_version() { return 1; }

int subgraph_sat_solver_solve(const int* clauses, int clause_count, int literal_count, int* result) {
    (void)clauses;
    (void)clause_count;
    (void)literal_count;
    if (result) {
        result[0] = 1;
    }
    return 0;
}

} // extern "C"
