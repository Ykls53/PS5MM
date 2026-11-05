// SPDX-License-Identifier: GPL-3.0-or-later
// PS5MM's media engine: FFmpeg as the plumbing under the picture engine.
//
// Not an AI engine, and it does not take a slot: the routes hang under the
// picture engine's port (see sd_server.cpp), because everything that produces
// video ends up needing frames in or a container out.
//
//   GET  /media/v1/info                          -> versions + what got compiled in
//   POST /media/v1/frames   {video: b64, count?} -> {frames: [b64 png...], w, h, fps}
//
// The blob is staged to a file first: FFmpeg reads from a path, not a buffer.

#pragma once

namespace ps5mm {
struct httplib_forward;  // unused; the real signature is below
}

namespace httplib {
class Server;
}

namespace ps5mm {

// Registers the media routes on an existing server (the picture engine's).
void media_register_routes(httplib::Server & server);

}  // namespace ps5mm
