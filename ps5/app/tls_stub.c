/* SPDX-License-Identifier: GPL-3.0-or-later
 *
 * The console's emutls has no __tls_init, so clang leaves _ZTH… (the TLS init
 * wrappers of stable-diffusion.cpp's thread_local executor) as weak undefined,
 * and the title converter refuses a binary that still names such a symbol.
 * They are never meant to run for these two: give them an empty body.
 *
 * Only the two names sd.cpp's thread pool makes exist here; a link that grows a
 * third one fails loudly instead of calling through NULL.
 */
void _ZTHN2sd15parallel_detail8executorE(void) {}
void _ZTHN2sd15parallel_detail6activeE(void) {}
