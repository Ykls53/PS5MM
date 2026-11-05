// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// PS5MM's 3D engine: TRELLIS.2's image->3D pipeline, on a fourth ggml, in the
// same process as the text, speech, picture and audio engines.
//
// trellis.cpp has no C API — its entry point is the C++ function
//
//     int trellis_run(const trellis::TrellisParams & cfg);
//
// defined in src/trellis_cli.cpp (not in any archive), so that source is
// compiled into this binary and the rest of trellis's libraries arrive with
// their own symbols TRX_-prefixed (scripts/prefix-trellis.sh). The trellis::
// namespace itself is left alone: nothing else in this binary defines it.
//
// Every run is the whole pipeline (background removal, three flow transformers,
// VAE decode, mesh extraction, GLB with a UV-baked texture), so one run at a
// time and a long timeout are both expected.

#include <string>

struct TrellisPaths {
    const char * models;      // the GGUF directory (trellis.gguf / naf.gguf / birefnet.gguf …)
    const char * output_dir;  // where the .glb files land
    const char * backend;     // "Vulkan", or nullptr to auto-select
};

// Registers the routes and starts the listener. 0 = serving, -1 = no listener.
int  trellis_server_start(const TrellisPaths & paths, int port);

void trellis_server_terminate(void);

bool trellis_server_listening(void);   // the port answers

// Milliseconds the last image->3D run took, or 0 when nothing has run yet.
long trellis_server_last_ms(void);
