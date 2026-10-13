# C++-Shim um die Bibliothek des Subgraph-SAT-Solvers.
#
# Der Solver (Cnf.cpp, Reduction.cpp, SubgraphSATSolver.cpp) wird nicht kopiert, sondern aus
# einem Checkout eingebunden, z. B. als Git-Submodul unter third_party/subgraph-sat-solver:
#
#   cmake -S src/native -B build -DSUBGRAPH_SAT_SOLVER_DIR=/pfad/zu/subgraph-sat-solver
#   cmake --build build
#
# Ergebnis: build/libwsat_shim.so (bzw. .dylib / .dll).
cmake_minimum_required(VERSION 3.16)
project(wirtschaft_shim CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

set(SUBGRAPH_SAT_SOLVER_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/subgraph-sat-solver"
    CACHE PATH "Verzeichnis mit Cnf.cpp, Reduction.cpp, SubgraphSATSolver.cpp")

foreach(f Cnf.cpp Reduction.cpp SubgraphSATSolver.cpp SubgraphSATSolver.h)
  if(NOT EXISTS "${SUBGRAPH_SAT_SOLVER_DIR}/${f}")
    message(FATAL_ERROR
      "Solver-Quelle nicht gefunden: ${SUBGRAPH_SAT_SOLVER_DIR}/${f}\n"
      "Setze -DSUBGRAPH_SAT_SOLVER_DIR=<Pfad> oder lege den Solver als Submodul unter "
      "third_party/subgraph-sat-solver ab.")
  endif()
endforeach()

# Der Solver als statische Bibliothek (satlib); bewusst ohne -march=native,
# damit die erzeugte Shim-Bibliothek übertragbar bleibt.
add_library(satlib STATIC
  "${SUBGRAPH_SAT_SOLVER_DIR}/Cnf.cpp"
  "${SUBGRAPH_SAT_SOLVER_DIR}/Reduction.cpp"
  "${SUBGRAPH_SAT_SOLVER_DIR}/SubgraphSATSolver.cpp")
target_include_directories(satlib PUBLIC "${SUBGRAPH_SAT_SOLVER_DIR}")
if(NOT MSVC)
  target_compile_options(satlib PRIVATE -O2 -Wno-unused-result)
endif()

add_library(wsat_shim SHARED wsat_shim.cpp)
target_include_directories(wsat_shim PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(wsat_shim PRIVATE satlib)
if(NOT MSVC)
  target_compile_options(wsat_shim PRIVATE -O2 -Wall -Wextra -pedantic)
endif()
set_target_properties(wsat_shim PROPERTIES
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
