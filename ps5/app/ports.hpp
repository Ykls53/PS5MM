// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

// 端口跟「槽位」走，不跟「引擎类型」走。
//   槽位 1..5  →  8001..8005
//   文字 / 图像 / 语音 各占哪个槽位，由设置里的 text_slot / picture_slot /
//   speech_slot 决定（默认 1 / 2 / 3，跟以前一样）。
//
// 为什么改成这样：早先端口写死在引擎类型上（文字永远 8001），于是用户想把
// 图像放第一个槽、或者想让文字让开 8001，都做不到。现在槽位是自由的，
// 客户端该填哪个端口，设置页上看得见。
//
// 注意：同类引擎在一个进程里仍然只有一份（llama.cpp 的 server 是三处进程级
// 单例），所以两个槽位放同类模型时，后一个起不来 —— 多实例要另行改造。

namespace ps5mm {

constexpr int kSlotFirst = 1;
constexpr int kSlotCount = 5;
constexpr int kPortFirst = 8001;

// 槽位号（1..5）→ 端口号（8001..8005）。越界的钳住，不抛。
inline int port_of_slot(int slot) {
    if (slot < kSlotFirst) {
        slot = kSlotFirst;
    }
    if (slot > kSlotCount) {
        slot = kSlotCount;
    }
    return kPortFirst + slot - 1;
}

}  // namespace ps5mm
