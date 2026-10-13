/**
 * wsat_shim.cpp
 *
 * Implementierung des C-ABI-Shims um sat::SubgraphSATSolver (siehe wsat_shim.h).
 */

#include "wsat_shim.h"

#include "SubgraphSATSolver.h"

#include <cstring>
#include <exception>
#include <iostream>
#include <streambuf>
#include <string>

namespace {

// Verwirft jede Ausgabe: der Solver schreibt seine Reduktionsprotokolle auf std::cout.
class NullBuffer : public std::streambuf {
protected:
    int overflow(int c) override { return c; }
};

// Leitet std::cout während der Lebensdauer um und stellt es danach wieder her.
class CoutRedirect {
public:
    explicit CoutRedirect(bool active) : active_(active) {
        if (active_) {
            old_ = std::cout.rdbuf(&null_);
        }
    }
    ~CoutRedirect() {
        if (active_) {
            std::cout.rdbuf(old_);
        }
    }
    CoutRedirect(const CoutRedirect&) = delete;
    CoutRedirect& operator=(const CoutRedirect&) = delete;

private:
    bool active_;
    NullBuffer null_;
    std::streambuf* old_ = nullptr;
};

void write_error(char* out, size_t len, const std::string& message) {
    if (out == nullptr || len == 0) {
        return;
    }
    std::strncpy(out, message.c_str(), len - 1);
    out[len - 1] = '\0';
}

}  // namespace

extern "C" {

int wsat_abi_version(void) { return WSAT_ABI_VERSION; }

int wsat_solve(const int* clauses, size_t n_ints, int num_vars,
               const char* subgraph_binary, const char* temp_dir,
               int timeout_sec, int validate, int verbose,
               signed char* model_out, size_t model_len,
               wsat_stats* stats,
               char* error_out, size_t error_len) {
    write_error(error_out, error_len, "");
    if (stats != nullptr) {
        std::memset(stats, 0, sizeof(*stats));
    }
    if (num_vars < 0 || (n_ints > 0 && clauses == nullptr) || subgraph_binary == nullptr ||
        temp_dir == nullptr) {
        write_error(error_out, error_len, "invalid argument");
        return WSAT_ERROR;
    }
    if (model_out != nullptr && model_len < static_cast<size_t>(num_vars) + 1) {
        write_error(error_out, error_len, "model buffer too small");
        return WSAT_ERROR;
    }

    try {
        sat::CNFFormula formula;
        formula.set_num_variables(num_vars);
        sat::Clause current;
        bool open = false;
        for (size_t i = 0; i < n_ints; ++i) {
            if (clauses[i] == 0) {
                formula.add_clause(current);  // validiert die Literale gegen num_vars
                current.clear();
                open = false;
            } else {
                current.push_back(clauses[i]);
                open = true;
            }
        }
        if (open) {
            write_error(error_out, error_len, "last clause is not terminated by 0");
            return WSAT_ERROR;
        }

        sat::SATSolverConfig config;
        config.subgraph_binary_path = subgraph_binary;
        config.temp_dir = temp_dir;
        config.subgraph_timeout_sec = timeout_sec;
        config.verbose = verbose != 0;
        config.validate_result = validate != 0;

        CoutRedirect redirect(verbose == 0);
        sat::SubgraphSATSolver solver(config);
        sat::SATSolverResult result = solver.solve_formula(formula);

        if (stats != nullptr) {
            stats->reduction_ms = result.reduction_time_ms;
            stats->subgraph_ms = result.subgraph_solver_time_ms;
            stats->extraction_ms = result.extraction_time_ms;
            stats->total_ms = result.total_time_ms;
            stats->num_variables = result.num_variables;
            stats->num_clauses = result.num_clauses;
        }

        switch (result.status) {
            case sat::SATSolverResult::SATISFIABLE:
                if (model_out != nullptr) {
                    std::memset(model_out, 0, model_len);
                    if (result.assignment) {
                        for (int v = 1; v <= num_vars; ++v) {
                            if (result.assignment->is_assigned(v)) {
                                model_out[v] = result.assignment->value(v) ? 1 : 0;
                            }
                        }
                    }
                }
                return WSAT_SAT;
            case sat::SATSolverResult::UNSATISFIABLE:
                return WSAT_UNSAT;
            case sat::SATSolverResult::UNKNOWN:
                return WSAT_UNKNOWN;
            case sat::SATSolverResult::SAT_ERROR:
            default:
                write_error(error_out, error_len, result.error_message);
                return WSAT_ERROR;
        }
    } catch (const std::exception& e) {
        write_error(error_out, error_len, e.what());
        return WSAT_ERROR;
    } catch (...) {
        write_error(error_out, error_len, "unknown C++ exception");
        return WSAT_ERROR;
    }
}

}  // extern "C"
