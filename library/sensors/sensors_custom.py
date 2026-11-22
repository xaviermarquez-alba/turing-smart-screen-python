# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file allows to add custom data source as sensors and display them in System Monitor themes
# There is no limitation on how much custom data source classes can be added to this file
# See CustomDataExample theme for the theme implementation part

import math
import platform
from abc import ABC, abstractmethod
from typing import List


# Custom data classes must be implemented in this file, inherit the CustomDataSource and implement its 2 methods
class CustomDataSource(ABC):
    @abstractmethod
    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # If there is no numeric value, keep this function empty
        pass

    @abstractmethod
    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        pass

    @abstractmethod
    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        # If you do not want to draw a line graph or if your custom data has no numeric values, keep this function empty
        pass


# Example for a custom data class that has numeric and text values
class ExampleCustomNumericData(CustomDataSource):
    # This list is used to store the last 10 values to display a line graph
    last_val = [math.nan] * 10  # By default, it is filed with math.nan values to indicate there is no data stored

    def as_numeric(self) -> float:
        # Numeric value will be used for graph and radial progress bars
        # Here a Python function from another module can be called to get data
        # Example: self.value = my_module.get_rgb_led_brightness() / audio.system_volume() ...
        self.value = 75.845

        # Store the value to the history list that will be used for line graph
        self.last_val.append(self.value)
        # Also remove the oldest value from history list
        self.last_val.pop(0)

        return self.value

    def as_string(self) -> str:
        # Text value will be used for text display and radial progress bar inner text.
        # Numeric value can be formatted here to be displayed as expected
        # It is also possible to return a text unrelated to the numeric value
        # If this function is empty, the numeric value will be used as string without formatting
        # Example here: format numeric value: add unit as a suffix, and keep 1 digit decimal precision
        return f'{self.value:>5.1f}%'
        # Important note! If your numeric value can vary in size, be sure to display it with a default size.
        # E.g. if your value can range from 0 to 9999, you need to display it with at least 4 characters every time.
        # --> return f'{self.as_numeric():>4}%'
        # Otherwise, part of the previous value can stay displayed ("ghosting") after a refresh

    def last_values(self) -> List[float]:
        # List of last numeric values will be used for plot graph
        return self.last_val


# Example for a custom data class that only has text values
class ExampleCustomTextOnlyData(CustomDataSource):
    def as_numeric(self) -> float:
        # If there is no numeric value, keep this function empty
        pass

    def as_string(self) -> str:
        # If a custom data class only has text values, it won't be possible to display graph or radial bars
        return "Python: " + platform.python_version()

    def last_values(self) -> List[float]:
        # If a custom data class only has text values, it won't be possible to display line graph
        pass


# --- Claude Code / Cursor usage and keyless weather sensors (used by the Cyberpunk-landscape theme) ---
import base64
import datetime
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from library.log import logger


def _format_count(value: float) -> str:
    # Fixed-width (7 chars) human-readable count, e.g. '  12.3K', '  1.25M'
    if value is None or math.isnan(value):
        text = "--"
    elif value < 1000:
        text = f"{value:.0f}"
    elif value < 1000000:
        text = f"{value / 1000:.1f}K"
    else:
        text = f"{value / 1000000:.2f}M"
    return f"{text:>7}"


def _format_percent(value: float) -> str:
    return " --%" if value is None or math.isnan(value) else f"{value:>3.0f}%"


def _format_countdown(timestamp: float) -> str:
    # Fixed-width (7 chars) time left before the given timestamp: days + hours, or hours + minutes if less than a day
    # e.g. ' 3d 4h', ' 2h 13m'
    if timestamp is None or math.isnan(timestamp):
        return "     --"
    minutes = max(0, int((timestamp - time.time()) / 60))
    if minutes >= 24 * 60:
        text = f"{minutes // 1440}d {minutes % 1440 // 60}h"
    else:
        text = f"{minutes // 60}h {minutes % 60}m"
    return f"{text:>7}"


def _format_countdown_short(timestamp: float) -> str:
    # Fixed-width (3 chars) time left before the given timestamp, largest unit only: days, hours or minutes
    # e.g. ' 5d', '23h', ' 7m'
    if timestamp is None or math.isnan(timestamp):
        return " --"
    minutes = max(0, int((timestamp - time.time()) / 60))
    if minutes >= 24 * 60:
        text = f"{minutes // 1440}d"
    elif minutes >= 60:
        text = f"{minutes // 60}h"
    else:
        text = f"{minutes}m"
    return f"{text:>3}"


def _claude_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def _http_get_json(url: str, headers: dict = None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class _ClaudeTokens:
    # Sums the tokens (input + output + cache creation, cache reads excluded) reported in Claude Code local
    # session transcripts (~/.claude/projects/**/*.jsonl). No credentials or network access needed.
    TTL = 10  # seconds between two scans
    _files = {}  # path -> (mtime, size, [(timestamp, message key, tokens)])
    _result = (0.0, math.nan, math.nan)  # (scan time, tokens today, tokens last 5h)

    @staticmethod
    def _parse(path):
        entries = []
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                if '"usage"' not in line:
                    continue
                try:
                    data = json.loads(line)
                    message = data["message"]
                    usage = message["usage"]
                    timestamp = datetime.datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")).timestamp()
                    tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0) + (
                            usage.get("cache_creation_input_tokens") or 0)
                    entries.append((timestamp, str(message.get("id")) + str(data.get("requestId")), tokens))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        return entries

    @classmethod
    def get(cls):
        now = time.time()
        if now - cls._result[0] < cls.TTL:
            return cls._result
        midnight = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        last_5h = now - 5 * 3600
        oldest = min(midnight, last_5h)
        today = recent = 0
        seen = set()
        try:
            for path in (_claude_dir() / "projects").rglob("*.jsonl"):
                try:
                    stat = path.stat()
                    if stat.st_mtime < oldest:
                        continue
                    cached = cls._files.get(path)
                    if cached is None or cached[0] != stat.st_mtime or cached[1] != stat.st_size:
                        cached = (stat.st_mtime, stat.st_size, cls._parse(path))
                        cls._files[path] = cached
                except OSError:
                    continue
                for timestamp, key, tokens in cached[2]:
                    if key in seen:  # A same message is written several times in transcripts
                        continue
                    seen.add(key)
                    if timestamp >= midnight:
                        today += tokens
                    if timestamp >= last_5h:
                        recent += tokens
            cls._result = (now, float(today), float(recent))
        except OSError:
            cls._result = (now, math.nan, math.nan)
        return cls._result


class _ClaudeApiCredit:
    # Sums this month's Anthropic API spend (USD) from the local delegation log
    # (~/.claude/delegation/log.jsonl): lines with kind "run", pool "anthropic-api" and a cost_usd whose timestamp
    # falls in the current calendar month (local time). Malformed lines are skipped. No credentials or network.
    # The monthly budget is 100 USD, or DLOG_API_BUDGET_USD when that variable parses as a float greater than 0.
    TTL = 60  # seconds between two reads
    _read = 0.0
    _spent = math.nan

    @staticmethod
    def _budget() -> float:
        try:
            budget = float(os.environ["DLOG_API_BUDGET_USD"])
        except (KeyError, TypeError, ValueError):
            return 100.0
        return budget if budget > 0 else 100.0

    @classmethod
    def get(cls):
        now = time.time()
        budget = cls._budget()
        if now - cls._read < cls.TTL:
            return cls._spent, budget
        cls._read = now
        try:
            month = datetime.datetime.now().astimezone()
            spent = 0.0
            with open(_claude_dir() / "delegation" / "log.jsonl", "r", encoding="utf-8", errors="ignore") as file:
                for line in file:
                    try:
                        data = json.loads(line)
                        if data.get("kind") != "run" or data.get("pool") != "anthropic-api":
                            continue
                        cost = data.get("cost_usd")
                        if cost is None:
                            continue
                        timestamp = datetime.datetime.fromisoformat(data["ts"]).astimezone()
                        if timestamp.year == month.year and timestamp.month == month.month:
                            spent += float(cost)
                    except (ValueError, KeyError, TypeError, AttributeError):
                        continue
            cls._spent = spent
        except OSError:
            cls._spent = math.nan
        return cls._spent, budget


class _ClaudePlan:
    # Reads the Claude subscription usage (5-hour session and 7-day limits) from Anthropic usage endpoint, using the
    # OAuth token stored by Claude Code on this computer. The token is only ever sent to api.anthropic.com.
    # This endpoint is not documented: values are shown as '--' if it is unavailable.
    URL = "https://api.anthropic.com/api/oauth/usage"
    TTL = 300  # seconds between two requests
    TTL_ERROR = 300  # seconds to wait after a failed request
    MAX_AGE = 3600  # seconds during which the last good values are kept if requests fail
    _next = 0.0
    _updated = 0.0
    _values = (math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)

    @staticmethod
    def _window(data: dict, name: str):
        window = data.get(name) or {}
        percent = window.get("utilization")
        reset = window.get("resets_at")
        percent = float(percent) if percent is not None else math.nan
        reset = datetime.datetime.fromisoformat(reset.replace("Z", "+00:00")).timestamp() if reset else math.nan
        return percent, reset

    @staticmethod
    def _fable_limit(data: dict):
        try:
            limits = data.get("limits")
            if not isinstance(limits, list):
                return math.nan, math.nan
            for entry in limits:
                if not isinstance(entry, dict) or entry.get("kind") != "weekly_scoped":
                    continue
                scope = entry.get("scope") or {}
                model = scope.get("model") if isinstance(scope, dict) else {}
                if not isinstance(model, dict):
                    continue
                name = model.get("display_name")
                if name is None or str(name).lower() != "fable":
                    continue
                percent = entry.get("percent")
                reset = entry.get("resets_at")
                percent = float(percent) if percent is not None else math.nan
                reset = (datetime.datetime.fromisoformat(reset.replace("Z", "+00:00")).timestamp()
                         if reset else math.nan)
                return percent, reset
        except (TypeError, ValueError, KeyError, AttributeError):
            pass
        return math.nan, math.nan

    @classmethod
    def get(cls):
        now = time.time()
        if now >= cls._next:
            try:
                with open(_claude_dir() / ".credentials.json", "r", encoding="utf-8") as file:
                    token = json.load(file)["claudeAiOauth"]["accessToken"]
                data = _http_get_json(cls.URL, {"Authorization": "Bearer " + token,
                                                "anthropic-beta": "oauth-2025-04-20"})
                cls._values = (cls._window(data, "five_hour") + cls._window(data, "seven_day")
                               + cls._fable_limit(data))
                cls._updated = now
                cls._next = now + cls.TTL
            except urllib.error.HTTPError as error:
                delay = cls.TTL_ERROR
                retry_after = error.headers.get("Retry-After") if error.headers else None
                if retry_after is not None:
                    try:
                        seconds = int(retry_after)
                        if seconds > 0:
                            delay = max(cls.TTL_ERROR, seconds)
                    except (ValueError, TypeError):
                        pass
                logger.warning("Claude usage refresh failed: HTTPError %s, retry in %s s", error.code, delay)
                cls._next = now + delay
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                logger.warning("Claude usage refresh failed: %s, retry in %s s", type(error).__name__, cls.TTL_ERROR)
                cls._next = now + cls.TTL_ERROR
        if now - cls._updated > cls.MAX_AGE:
            return math.nan, math.nan, math.nan, math.nan, math.nan, math.nan
        return cls._values


class _CursorPlan:
    # Reads the Cursor plan usage from the Cursor usage endpoint, using the access token stored by the Cursor editor
    # on this computer in its local state database. The first value (autoPercentUsed) is the bucket shared by Grok
    # and Composer and the second (apiPercentUsed) is the premium models bucket (both in % of the included usage).
    # The token is only ever sent to api2.cursor.sh.
    # This endpoint is not documented: values are shown as '--' if it is unavailable.
    URL = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
    TTL = 300  # seconds between two requests
    TTL_ERROR = 900  # seconds to wait after a failed request
    MAX_AGE = 3600  # seconds during which the last good values are kept if requests fail
    _next = 0.0
    _updated = 0.0
    _values = (math.nan, math.nan, math.nan)  # (Grok and Composer %, premium models %, billing cycle end time)

    @staticmethod
    def _database() -> Path:
        if platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif platform.system() == "Darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "Cursor" / "User" / "globalStorage" / "state.vscdb"

    @classmethod
    def get(cls):
        now = time.time()
        if now >= cls._next:
            try:
                connection = sqlite3.connect(cls._database().as_uri() + "?mode=ro", uri=True, timeout=1)
                try:
                    token = connection.execute(
                        "SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken'").fetchone()[0]
                finally:
                    connection.close()
                request = urllib.request.Request(cls.URL, data=b"{}", headers={
                    "Authorization": "Bearer " + token, "Content-Type": "application/json",
                    "Connect-Protocol-Version": "1"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                usage = data.get("planUsage") or {}
                cycle_end = data.get("billingCycleEnd")
                cls._values = (float(usage.get("autoPercentUsed", math.nan)),
                               float(usage.get("apiPercentUsed", math.nan)),
                               float(cycle_end) / 1000 if cycle_end else math.nan)
                cls._updated = now
                cls._next = now + cls.TTL
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError):
                cls._next = now + cls.TTL_ERROR
        if now - cls._updated > cls.MAX_AGE:
            return math.nan, math.nan, math.nan
        return cls._values


class _GooglePlan:
    # Reads the Google AI plan quotas of Antigravity (5-hour and weekly limits for Gemini models and other models,
    # plus the Gemini 4 Argon weekly quota, in % used) from Google Code Assist endpoint, using the token stored by
    # Antigravity in the system keyring (Linux, macOS). The token is only ever sent to cloudcode-pa.googleapis.com.
    # The token is not refreshed here: once it has expired the last values are kept until their window resets, as
    # Antigravity renews the token whenever it is used.
    # This endpoint is not documented: values are shown as '--' if it is unavailable.
    URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
    # Google only returns the Gemini group to the Antigravity CLI client name
    USER_AGENT = "antigravity/cli/1.5.14 (linux/amd64)"
    BUCKETS = ("gemini-5h", "gemini-weekly", "3p-5h", "3p-weekly", "gemini-argon-wtu-weekly")
    TTL = 120  # seconds between two requests
    TTL_ERROR = 900  # seconds to wait after a failed request
    TTL_EXPIRED = 30  # seconds before reading the keyring again while the token is expired (no request is sent)
    _next = 0.0
    _pools = ((math.nan, math.nan),) * 5  # (% used, reset time) for each of BUCKETS

    class _TokenExpired(Exception):
        pass

    @staticmethod
    def _token() -> str:
        if platform.system() == "Darwin":
            secret = _run(["security", "find-generic-password", "-s", "gemini", "-a", "antigravity", "-w"])
        else:
            secret = _run(["secret-tool", "lookup", "service", "gemini", "username", "antigravity"])
        secret = secret.strip()
        if secret.startswith("go-keyring-base64:"):
            secret = base64.b64decode(secret[len("go-keyring-base64:"):]).decode("utf-8")
        token = json.loads(secret)["token"]
        try:  # Expiry looks like 2026-11-21T16:30:33.57156249-03:00
            expiry = re.sub(r"\.\d+", "", token["expiry"]).replace("Z", "+00:00")
            expired = time.time() >= datetime.datetime.fromisoformat(expiry).timestamp()
        except (KeyError, TypeError, ValueError):
            expired = False  # Unknown expiry: let the request tell
        if expired:
            raise _GooglePlan._TokenExpired()
        return token["access_token"]

    @classmethod
    def get(cls):
        now = time.time()
        if now >= cls._next:
            try:
                request = urllib.request.Request(cls.URL, data=b"{}", headers={
                    "Authorization": "Bearer " + cls._token(), "Content-Type": "application/json",
                    "User-Agent": cls.USER_AGENT})
                with urllib.request.urlopen(request, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                found = {}
                for group in data["groups"]:
                    for bucket in group.get("buckets") or ():
                        bucket_id = bucket.get("bucketId")
                        if bucket_id in cls.BUCKETS:
                            remaining = bucket.get("remainingFraction")
                            reset = bucket.get("resetTime")
                            used = 100 * (1 - float(remaining)) if remaining is not None else math.nan
                            reset = (datetime.datetime.fromisoformat(reset.replace("Z", "+00:00")).timestamp()
                                     if reset else math.nan)
                            found[bucket_id] = (used, reset)
                cls._pools = tuple(found.get(bucket_id, (math.nan, math.nan)) for bucket_id in cls.BUCKETS)
                cls._next = now + cls.TTL
            except cls._TokenExpired:
                cls._next = now + cls.TTL_EXPIRED
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, AttributeError):
                cls._next = now + cls.TTL_ERROR
        # A window that has reset since the last successful request is back to 0 %
        return tuple((0.0, math.nan) if not math.isnan(used) and now >= reset else (used, reset)
                     for used, reset in cls._pools)


class _Weather:
    # Current weather from Open-Meteo (no API key needed), for WEATHER_LATITUDE / WEATHER_LONGITUDE of config.yaml
    TTL = 900  # seconds between two requests
    TTL_ERROR = 120
    CODES = {0: "CLEAR", 1: "MOSTLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST", 45: "FOG", 48: "FOG",
             51: "DRIZZLE", 53: "DRIZZLE", 55: "DRIZZLE", 56: "ICY DRIZZLE", 57: "ICY DRIZZLE",
             61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN", 66: "ICY RAIN", 67: "ICY RAIN",
             71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 77: "SNOW GRAINS",
             80: "SHOWERS", 81: "SHOWERS", 82: "HEAVY SHOWERS", 85: "SNOW SHOWERS", 86: "SNOW SHOWERS",
             95: "THUNDERSTORM", 96: "THUNDERSTORM", 99: "THUNDERSTORM"}
    _next = 0.0
    _values = (math.nan, math.nan, "", "°C")  # (temperature, humidity %, description, unit)

    @classmethod
    def get(cls):
        now = time.time()
        if now >= cls._next:
            try:
                import library.config as config
                settings = config.CONFIG_DATA["config"]
                imperial = settings.get("WEATHER_UNITS", "metric") == "imperial"
                query = urllib.parse.urlencode({
                    "latitude": settings["WEATHER_LATITUDE"], "longitude": settings["WEATHER_LONGITUDE"],
                    "current": "temperature_2m,relative_humidity_2m,weather_code",
                    "temperature_unit": "fahrenheit" if imperial else "celsius"})
                current = _http_get_json("https://api.open-meteo.com/v1/forecast?" + query)["current"]
                cls._values = (float(current["temperature_2m"]), float(current["relative_humidity_2m"]),
                               cls.CODES.get(current["weather_code"], ""), "°F" if imperial else "°C")
                cls._next = now + cls.TTL
            except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError):
                cls._next = now + cls.TTL_ERROR
        return cls._values


class _SimpleData(CustomDataSource):
    def as_numeric(self) -> float:
        pass

    def as_string(self) -> str:
        pass

    def last_values(self) -> List[float]:
        pass


class ClaudeSessionPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _ClaudePlan.get()[0]

    def as_string(self) -> str:
        return _format_percent(_ClaudePlan.get()[0])


class ClaudeSessionReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown(_ClaudePlan.get()[1])


class ClaudeWeekPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _ClaudePlan.get()[2]

    def as_string(self) -> str:
        return _format_percent(_ClaudePlan.get()[2])


class ClaudeWeekReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown(_ClaudePlan.get()[3])


class ClaudeFablePercent(_SimpleData):
    def as_numeric(self) -> float:
        return _ClaudePlan.get()[4]

    def as_string(self) -> str:
        return _format_percent(_ClaudePlan.get()[4])


class ClaudeFableReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown(_ClaudePlan.get()[5])


class ClaudeApiPercent(_SimpleData):
    def as_numeric(self) -> float:
        spent, budget = _ClaudeApiCredit.get()
        if math.isnan(spent):
            return math.nan
        return min(100.0, 100.0 * spent / budget)

    def as_string(self) -> str:
        return _format_percent(self.as_numeric())


class ClaudeApiSpent(_SimpleData):
    def as_string(self) -> str:
        spent = _ClaudeApiCredit.get()[0]
        if math.isnan(spent):
            text = "--"
        elif spent < 100:
            text = f"${spent:.2f}"
        else:
            text = f"${spent:.0f}"
        return f"{text:>7}"


class ClaudeTokensToday(_SimpleData):
    def as_string(self) -> str:
        return _format_count(_ClaudeTokens.get()[1])


class ClaudeTokensLast5h(_SimpleData):
    def as_string(self) -> str:
        return _format_count(_ClaudeTokens.get()[2])


class CursorModelsPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _CursorPlan.get()[0]

    def as_string(self) -> str:
        return _format_percent(_CursorPlan.get()[0])


class CursorOtherPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _CursorPlan.get()[1]

    def as_string(self) -> str:
        return _format_percent(_CursorPlan.get()[1])


class CursorReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown(_CursorPlan.get()[2])


class GoogleGeminiSessionPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _GooglePlan.get()[0][0]

    def as_string(self) -> str:
        return _format_percent(_GooglePlan.get()[0][0])


class GoogleGeminiSessionReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown_short(_GooglePlan.get()[0][1])


class GoogleGeminiWeekPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _GooglePlan.get()[1][0]

    def as_string(self) -> str:
        return _format_percent(_GooglePlan.get()[1][0])


class GoogleGeminiWeekReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown_short(_GooglePlan.get()[1][1])


class GoogleOtherSessionPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _GooglePlan.get()[2][0]

    def as_string(self) -> str:
        return _format_percent(_GooglePlan.get()[2][0])


class GoogleOtherSessionReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown_short(_GooglePlan.get()[2][1])


class GoogleOtherWeekPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _GooglePlan.get()[3][0]

    def as_string(self) -> str:
        return _format_percent(_GooglePlan.get()[3][0])


class GoogleOtherWeekReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown_short(_GooglePlan.get()[3][1])


class GoogleArgonWeekPercent(_SimpleData):
    def as_numeric(self) -> float:
        return _GooglePlan.get()[4][0]

    def as_string(self) -> str:
        return _format_percent(_GooglePlan.get()[4][0])


class GoogleArgonWeekReset(_SimpleData):
    def as_string(self) -> str:
        return _format_countdown_short(_GooglePlan.get()[4][1])


class WeatherTemperature(_SimpleData):
    def as_string(self) -> str:
        temperature, _, _, unit = _Weather.get()
        return "  --" + unit if math.isnan(temperature) else f"{temperature:>3.0f}{unit}"


class WeatherHumidity(_SimpleData):
    def as_string(self) -> str:
        humidity = _Weather.get()[1]
        return " --% RH" if math.isnan(humidity) else f"{humidity:>3.0f}% RH"


class WeatherDescription(_SimpleData):
    def as_string(self) -> str:
        return f"{_Weather.get()[2]:<14}"


class TopProcess(_SimpleData):
    # Name and CPU usage (in % of one core, like 'top') of the process using the most CPU
    def as_string(self) -> str:
        import psutil
        name, usage = "", 0.0
        for process in psutil.process_iter(["name"]):  # psutil keeps processes in cache between calls
            try:
                percent = process.cpu_percent(None)
            except psutil.Error:
                continue
            if percent > usage:
                name, usage = process.info["name"] or "", percent
        return f"{name[:11]:<11} {min(usage, 9999):>4.0f}%"


# --- Misc. system sensors: every value is a fixed-width (5 chars) text, '--' when not available on this computer ---
import shutil
import subprocess


def _format_value(value, unit: str = "") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return f"{'--':>5}"
    text = f"{value:.0f}{unit}" if isinstance(value, (int, float)) else f"{value}{unit}"
    return f"{text:>5}"


class _Cached:
    # Small cache to avoid reading the same slow data source (e.g. a command) at every refresh
    _store = {}

    @classmethod
    def get(cls, key: str, ttl: float, reader):
        cached = cls._store.get(key)
        if cached is None or time.time() - cached[0] >= ttl:
            try:
                value = reader()
            except Exception:
                value = None
            cached = (time.time(), value)
            cls._store[key] = cached
        return cached[1]


def _run(command: List[str]) -> str:
    if shutil.which(command[0]) is None:
        raise FileNotFoundError(command[0])
    return subprocess.run(command, capture_output=True, text=True, timeout=3, check=True).stdout


def _nvidia_gpu():
    # (power draw in W, fan speed in %) of the first Nvidia GPU
    fields = _run(["nvidia-smi", "--query-gpu=power.draw,fan.speed", "--format=csv,noheader,nounits"])
    power, fan = fields.splitlines()[0].split(",")
    return float(power), float(fan)


class UptimeShort(_SimpleData):
    # Time since boot: days + hours, or hours + minutes if less than a day
    def as_string(self) -> str:
        import psutil
        return _format_countdown(2 * time.time() - psutil.boot_time())


class VpnStatus(_SimpleData):
    # ON if a VPN / tunnel network interface is up
    def as_string(self) -> str:
        import psutil
        stats = psutil.net_if_stats()
        active = any(name.lower().startswith(("ppp", "tun", "tap", "wg")) and stat.isup for name, stat in stats.items())
        return _format_value("ON" if active else "OFF")


class SsdTemperature(_SimpleData):
    def as_string(self) -> str:
        import psutil
        sensors = getattr(psutil, "sensors_temperatures", lambda: {})().get("nvme") or []
        return _format_value(sensors[0].current if sensors else None, "°C")


class ProcessCount(_SimpleData):
    def as_string(self) -> str:
        import psutil
        return _format_value(len(psutil.pids()))


class GpuPower(_SimpleData):
    def as_string(self) -> str:
        gpu = _Cached.get("nvidia", 4, _nvidia_gpu)
        return _format_value(gpu[0] if gpu else None, "W")


class GpuFan(_SimpleData):
    def as_string(self) -> str:
        gpu = _Cached.get("nvidia", 4, _nvidia_gpu)
        return _format_value(gpu[1] if gpu else None, "%")


class DockerContainers(_SimpleData):
    # Number of running Docker containers
    def as_string(self) -> str:
        return _format_value(_Cached.get("docker", 30, lambda: len(_run(["docker", "ps", "-q"]).split())))


class SwapPercent(_SimpleData):
    def as_string(self) -> str:
        import psutil
        return _format_value(psutil.swap_memory().percent, "%")
