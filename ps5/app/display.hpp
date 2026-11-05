// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

namespace hui::gfx {
class Renderer;
}

namespace ps5lm {

// The TV, through ps5-opengl: one OpenGL 4.6 context, presented at vsync.
class Display {
  public:
    bool open(int width, int height);
    void clear(float r, float g, float b);
    // Draws the renderer's frame into the TV's framebuffer.
    void present(hui::gfx::Renderer & renderer);
    bool swap();
    int  width() const { return width_; }
    int  height() const { return height_; }

  private:
    int width_  = 0;
    int height_ = 0;
};

// ---- 退出时把电视还回去 -----------------------------------------------------
// EGL 的 display/surface/context 是 display.cpp 里的文件级全局，而退出路径
// （exit_to_home）是全局函数，拿不到 main() 里那个 Display 对象 —— 所以这两个
// 口开在命名空间里，而不是类成员。
//
// 为什么必须还：LoadExec("exit") 卡死的现场就是系统在等这个 title 让出
// display plane。surface 还活着、主循环还在 swap，系统就不放行，主线程卡在
// LoadExec 里，最后 _exit(0) 硬杀 —— 进程没了，平面还挂着，画面冻在最后一帧，
// 手柄也被这个"幽灵前台"吃掉。
void display_shutdown();   // 销毁 context/surface 并 eglTerminate（幂等）

// 退出流程是否已经还了电视；主循环靠它决定还要不要再画。没有成员对象也能问。
bool display_released();

}  // namespace ps5lm
