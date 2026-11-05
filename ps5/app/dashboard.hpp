// PS5MM's screen on the TV, five pages along a dock, switched with L1/R1:
//   - Overview: the five engine slots as channel strips, the memory bus,
//     and what the cluster is doing right now.
//   - Models: the five slots' configuration, the models on this console,
//     the suggested ones, a Hugging Face search, and the downloads.
//   - Endpoints: every port the engines answer, and how to call them.
//   - Monitor: charts, each engine's live task, and the logs.
//   - Settings: categories of rows; the logs moved to Monitor.
//
// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include "market.hpp"
#include "settings.hpp"
#include "stats.hpp"

#include "core/input.hpp"
#include "core/tween.hpp"
#include "gfx/backdrop_spec.hpp"
#include "gfx/draw_list.hpp"
#include "ui/components/input_prompt.hpp"
#include "ui/feedback.hpp"
#include "ui/fonts.hpp"
#include "ui/motion.hpp"

#include <string>
#include <vector>

namespace ps5lm {

struct DashboardFrame {
    hui::gfx::BackdropSpec backdrop;
    hui::gfx::DrawList     scene;
    hui::gfx::DrawList     overlay;
    bool                   glass         = false;
    std::uint32_t          glass_texture = 0;
};

class Dashboard {
  public:
    static constexpr int kPages = 5;
    static constexpr int kOverviewPage = 0, kModelsPage = 1, kEndpointsPage = 2, kMonitorPage = 3, kSettingsPage = 4;
    // 旧名留着兼容：Home = 总览，API = 端点，Console = 监控。
    static constexpr int kHomePage = kOverviewPage, kApiPage = kEndpointsPage, kConsolePage = kMonitorPage;
    // The Models page's sections: 槽位在前，资源库（本机/推荐/搜索/下载）在后。
    static constexpr int kSections = 5;
    static constexpr int kSlots = 0, kLocal = 1, kSuggested = 2, kSearch = 3, kDownloads = 4;

    explicit Dashboard(const hui::ui::Fonts & fonts);

    void set_live(const Live & live) { live_ = live; }
    // Slow work in progress: a spinner and these lines over everything, and
    // no input until it is cleared (empty title).
    void set_busy(std::string title, std::string text = {}) {
        busy_title_ = std::move(title);
        busy_text_ = std::move(text);
    }
    bool busy() const { return !busy_title_.empty(); }
    void open_library();  // the models on this console, cursor on the loaded one
    void show_downloads();
    void set_settings(const Settings & s) { settings_ = s; }
    const Settings & settings() const { return settings_; }
    void set_logs(std::vector<std::string> app, std::vector<std::string> llama);
    bool wants_logs() const;  // the logs are on screen: keep them fresh
    void set_market(MarketView view) { market_ = std::move(view); }
    int  page() const { return page_; }
    void update(const hui::InputFrame & input, float dt, hui::ui::Feedback & feedback);
    void draw(DashboardFrame & frame) const;

    // What the user asked for, once: load or unload a model, or the settings
    // changed (read them with settings()).
    struct Request {
        enum Kind { none, load, unload, settings, clear_scratch, market_search, market_open, market_plan, market_download,
                    market_download_unload, download_pause, download_resume, download_remove, suggested_download, ask,
                    sd_preload } kind = none;
        std::string path;   // a model, a market query, the folder a download goes to (empty: the setting), or what to ask
        int repo = -1, file = -1;  // a market file, a download's index (repo), or a suggestion's (repo)
    };
    Request take_request() {
        Request r = request_;
        request_ = {};
        return r;
    }

  private:
    void go_to(int page, hui::ui::Feedback * feedback);
    void update_home(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_models(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_slots(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_slot_picker(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_local(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_suggested(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_market(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_downloads(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_endpoints(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_monitor(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_settings(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_picker(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void update_logs(const hui::InputFrame & input, hui::ui::Feedback & feedback);
    void start_download(hui::ui::Feedback & feedback);
    void refilter_logs();
    const std::vector<std::string> & log_view() const { return log_llama_ ? llama_view_ : app_view_; }

    void draw_status(hui::gfx::DrawList & list) const;
    void draw_dock(hui::gfx::DrawList & list) const;
    void draw_home(hui::gfx::DrawList & list) const;
    void draw_overview(hui::gfx::DrawList & list) const;   // 视图 0：五席位通道条
    void draw_models(hui::gfx::DrawList & list) const;
    void draw_slots(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_slot_picker(hui::gfx::DrawList & list) const;
    void draw_local(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_suggested(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_market(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_downloads(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_endpoints(hui::gfx::DrawList & list) const;
    void draw_monitor(hui::gfx::DrawList & list) const;
    void draw_settings(hui::gfx::DrawList & list) const;
    void draw_picker(hui::gfx::DrawList & list) const;
    void draw_logs(hui::gfx::DrawList & list, const hui::gfx::Rect & area) const;
    void draw_dialogs(hui::gfx::DrawList & list) const;
    void draw_busy(hui::gfx::DrawList & list) const;
    void draw_hints(hui::gfx::DrawList & list) const;

    const hui::ui::Fonts & fonts_;
    Live        live_;
    Request     request_;

    float age_   = 0;  // seconds since start
    float clock_ = 0;  // idle motion
    std::string busy_title_, busy_text_;
    hui::ui::InputPrompt prompt_;          // a message typed on Home
    int   demo_ = 0;                       // the next demo to send
    float load_shown_ = 0;                 // the load's share as drawn, eased between samples
    bool  was_serving_ = false;              // for the sound when a model becomes ready
    std::vector<std::string> unfinished_;    // downloads not saved yet, for the sound when one is

    int   page_ = 0;
    int   home_view_ = 0;           // 总览两种视图：0 五席位通道条，1 对话详情（LT/RT 切）
    int   ov_cursor_ = 0;           // 通道条视图里聚焦的槽位
    int   page_from_ = 0;
    float page_age_ = 10;           // seconds since the page changed
    hui::tween::Spring dock_x_;     // the current tab's marker
    hui::tween::Spring rows_y_;     // the focused row's highlight, on the Models and Settings pages

    // Models.
    int   section_ = kSlots;
    bool  in_list_ = false;         // the focus is on the list, not the sections
    int   slot_cursor_ = 0;         // 槽位列表里聚焦的槽位
    bool  slot_pick_ = false;       // 给槽位指派模型的下拉开着
    int   slot_pick_cursor_ = 0;
    int   local_cursor_ = 0;
    int   suggested_cursor_ = 0;
    int   market_chip_ = 0;         // which search the chips select
    int   market_repo_ = 0;         // cursor in the repositories
    int   market_file_ = 0;         // cursor in the open repository's files
    bool  market_files_ = false;    // the cursor is in the files
    bool  market_searched_ = false;
    bool  market_confirm_ = false;  // asking whether to unload the model first
    bool  market_space_ = false;    // telling that the download does not fit where it would go
    std::string market_dir_;        // where this download goes instead of the setting, or empty
    int   dl_cursor_ = 0;
    int   dl_confirm_ = -1;         // the row Square was pressed on once (a second press deletes)
    MarketView market_;

    // Settings.
    Settings settings_;
    int   setting_category_ = 0;
    int   setting_row_ = 0;
    bool  in_rows_ = false;         // the focus is on the rows, not the categories
    bool  picker_ = false;          // a row's choices are open in a list under it
    bool  multi_  = false;          // that list is a checklist (启动加载): X ticks, not picks
    int   picker_cursor_ = 0;

    // Endpoints.
    int   ep_cursor_ = 0;           // the focused endpoint row
    float ep_scroll_ = 0;           // 列表滚下去的像素（分组头让行高不齐，按像素滚）

    // Monitor.
    bool  console_hour_ = false;    // the charts show the last hour, not the last two minutes

    // Diagnostics.
    std::vector<std::string> app_log_, llama_log_;    // as read
    std::vector<std::string> app_view_, llama_view_;  // after the filter
    bool  log_llama_ = false;
    bool  log_errors_ = false;
    int   log_scroll_ = 0;          // lines up from the newest
};

}  // namespace ps5lm
