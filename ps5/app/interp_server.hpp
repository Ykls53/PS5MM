// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's frame interpolation engine (RIFE on ncnn + Vulkan).
// Routes ride on the picture engine's port; see interp_server.cpp for why.

#pragma once

namespace httplib {
class Server;
}

namespace ps5mm {

// model_dir: where rife's ncnn params/bins live (e.g. /data/PS5MM/rife).
// Pass nullptr to keep the default and let the first request fill it.
void interp_register_routes(httplib::Server & server, const char * model_dir);

}  // namespace ps5mm
