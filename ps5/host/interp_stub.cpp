// SPDX-License-Identifier: GPL-3.0-or-later
// Stand-in for the RIFE routes when the host build has no ncnn yet. Keeps the
// picture engine's route table identical, and answers honestly instead of 404.

#include "httplib.h"
#include "nlohmann/json.hpp"

#include "interp_server.hpp"

namespace ps5mm {

void interp_register_routes(httplib::Server & server, const char * model_dir) {
    const std::string dir = model_dir != nullptr ? model_dir : "";
    server.Get("/media/v1/interp/info", [dir](const httplib::Request &, httplib::Response & res) {
        nlohmann::json out{ { "enabled", false },
                            { "loaded", false },
                            { "model_dir", dir },
                            { "reason", "this host build has no ncnn, so RIFE is not compiled in" } };
        res.set_content(out.dump(), "application/json");
    });
    server.Post("/media/v1/interpolate", [](const httplib::Request &, httplib::Response & res) {
        res.status = 503;
        res.set_content(nlohmann::json{ { "error", "interp not built in this host build" } }.dump(),
                        "application/json");
    });
}

}  // namespace ps5mm
