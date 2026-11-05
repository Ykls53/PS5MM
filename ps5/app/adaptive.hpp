// SPDX-License-Identifier: GPL-3.0-or-later
// One place that answers "what can this console actually do".
//
// Why this exists: PS5MM shipped with per-engine constants copied from a
// standard PS5 (4 threads, 256px VAE tiles). On a PS5 Pro those are not wrong,
// they are just half-idle -- the LM engine scales ~50% and the picture engine
// only 5-15%, which is exactly the shape of a parameter that stopped matching
// the hardware. Every engine must take its numbers from here, so adding an
// engine cannot reintroduce the same mistake.
//
// Everything is measured, not assumed: core count from the OS, memory from the
// backend that will actually do the work, and the GPU class from a short
// compute benchmark on first use. Each value can be overridden by an env var
// for measuring from the outside (PS5MM_CPU_THREADS, PS5MM_SD_TILE, ...).

#pragma once

namespace ps5mm {

struct Caps {
    int    cpu_cores    = 0;    // what the OS reports
    int    threads      = 4;    // what engines should pass as n_threads
    double pool_gib     = 0.0;  // the title's memory pool, total
    double free_gib     = 0.0;  // free when this was measured
    int    vae_tile     = 512;  // sd.cpp VAE tile side
    int    ubatch       = 256;  // llama.cpp -ub
    int    max_frames   = 33;   // video frames that fit the pool
    double gpu_gflops   = 0.0;  // measured, 0 = not measured yet
    bool   pro          = false;
    const char * gpu    = "unknown";
    const char * why    = "";   // one line: how these numbers were chosen
};

// Detected once on first call and cached.
const Caps & caps();

// One line to stdout, so it lands in app.log next to the device lines.
void print_caps();

}  // namespace ps5mm
