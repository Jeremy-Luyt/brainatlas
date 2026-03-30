// logger.hpp — Lightweight logging for STPS
#pragma once

#include <cstdio>
#include <cstdarg>
#include <string>
#include <fstream>
#include <chrono>
#include <ctime>
#include <mutex>

namespace stps {

enum class LogLevel { DEBUG = 0, INFO = 1, WARN = 2, ERR = 3 };

class Logger {
public:
    static Logger& instance() {
        static Logger inst;
        return inst;
    }

    void set_level(LogLevel lv) { level_ = lv; }

    bool open_file(const std::string& path) {
        std::lock_guard<std::mutex> lock(mu_);
        file_.open(path, std::ios::out | std::ios::trunc);
        return file_.is_open();
    }

    void log(LogLevel lv, const char* fmt, ...) {
        if (lv < level_) return;

        char buf[2048];
        va_list args;
        va_start(args, fmt);
        vsnprintf(buf, sizeof(buf), fmt, args);
        va_end(args);

        const char* tag = "INFO";
        FILE* dest = stdout;
        switch (lv) {
            case LogLevel::DEBUG: tag = "DEBUG"; break;
            case LogLevel::INFO:  tag = "INFO";  break;
            case LogLevel::WARN:  tag = "WARN";  dest = stderr; break;
            case LogLevel::ERR:   tag = "ERROR"; dest = stderr; break;
        }

        auto now = std::chrono::system_clock::now();
        auto t = std::chrono::system_clock::to_time_t(now);
        struct tm tm_buf;
#ifdef _WIN32
        localtime_s(&tm_buf, &t);
#else
        localtime_r(&t, &tm_buf);
#endif
        char ts[32];
        std::strftime(ts, sizeof(ts), "%H:%M:%S", &tm_buf);

        fprintf(dest, "[%s][%s] %s\n", ts, tag, buf);

        std::lock_guard<std::mutex> lock(mu_);
        if (file_.is_open()) {
            file_ << "[" << ts << "][" << tag << "] " << buf << "\n";
            file_.flush();
        }
    }

private:
    Logger() = default;
    LogLevel level_ = LogLevel::INFO;
    std::ofstream file_;
    std::mutex mu_;
};

#define LOG_DEBUG(fmt, ...) stps::Logger::instance().log(stps::LogLevel::DEBUG, fmt, ##__VA_ARGS__)
#define LOG_INFO(fmt, ...)  stps::Logger::instance().log(stps::LogLevel::INFO,  fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)  stps::Logger::instance().log(stps::LogLevel::WARN,  fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) stps::Logger::instance().log(stps::LogLevel::ERR,   fmt, ##__VA_ARGS__)

} // namespace stps
