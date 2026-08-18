"""
Prayer times, scraped straight from mawaqit.net.

Replaces the old api.mrie.dev/prayertimes round trip: same return shape, no
service to run. Logic ported from Mrie's Go backend (branch `rewrite`,
internal/api/routes/prayertimes).
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo

import aiohttp

logger = logging.getLogger(__name__)

MAWAQIT_URL = "https://mawaqit.net/en/m/{}"
CONF_DATA_RE = re.compile(r"var\s+confData\s*=\s*(\{.*?\});", re.DOTALL)

# One page holds the masjid's whole year, so we cache per masjid, not per day.
CACHE_TTL = 6 * 60 * 60

# Order of the six times in each calendar day entry.
PRAYERS = ("fajr", "shuruq", "dhuhr", "asr", "maghreb", "isha")

_cache: Dict[str, dict] = {}
_locks: Dict[str, asyncio.Lock] = {}


async def _fetch_calendar(mosque_id: str) -> Optional[dict]:
    """Scrape a masjid's year calendar and timezone from mawaqit."""
    url = MAWAQIT_URL.format(mosque_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    logger.error(f"Masjid {mosque_id} not found on mawaqit")
                    return None
                if response.status != 200:
                    logger.error(f"Mawaqit returned HTTP {response.status} for {mosque_id}")
                    return None
                html = await response.text()
    except Exception as e:
        logger.error(f"Error fetching prayer times for {mosque_id}: {e}")
        return None

    match = CONF_DATA_RE.search(html)
    if not match:
        logger.error(f"confData not found in mawaqit page for {mosque_id}")
        return None

    try:
        conf = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid confData JSON for {mosque_id}: {e}")
        return None

    tz_name = conf.get("timezone")
    calendar = conf.get("calendar")
    if not tz_name or not isinstance(calendar, list) or len(calendar) != 12:
        logger.error(f"Unexpected confData structure for {mosque_id}")
        return None

    try:
        tz = ZoneInfo(tz_name)
    except Exception as e:
        logger.error(f"Unknown timezone {tz_name} for {mosque_id}: {e}")
        return None

    return {
        "calendar": calendar,
        "tz": tz,
        "timezone": tz_name,
        "fetched": datetime.now(timezone.utc).timestamp(),
    }


async def _get_calendar(mosque_id: str) -> Optional[dict]:
    """Cached calendar for a masjid. Concurrent misses wait on one fetch."""
    cached = _cache.get(mosque_id)
    now = datetime.now(timezone.utc).timestamp()
    if cached and now - cached["fetched"] < CACHE_TTL:
        return cached

    lock = _locks.setdefault(mosque_id, asyncio.Lock())
    async with lock:
        # Another coroutine may have refreshed it while we waited.
        cached = _cache.get(mosque_id)
        if cached and datetime.now(timezone.utc).timestamp() - cached["fetched"] < CACHE_TTL:
            return cached

        fresh = await _fetch_calendar(mosque_id)
        if fresh:
            _cache[mosque_id] = fresh
            return fresh
        # Serve stale data rather than nothing if mawaqit is down.
        return cached


async def get_prayer_times(mosque_id: str, day: Optional[int] = None,
                           month: Optional[int] = None) -> Optional[dict]:
    """
    Prayer times for a masjid, as UTC ISO strings.

    Day and month default to today in the masjid's own timezone. Returns None
    if the masjid or day can't be resolved.
    """
    cal = await _get_calendar(mosque_id)
    if not cal:
        return None

    today = datetime.now(cal["tz"])
    day = day or today.day
    month = month or today.month

    if not 1 <= month <= 12:
        logger.error(f"Month {month} out of range")
        return None

    times = cal["calendar"][month - 1].get(str(day))
    if not times or len(times) < 6:
        logger.error(f"Day {day} not found in month {month} for {mosque_id}")
        return None

    result = {}
    for name, value in zip(PRAYERS, times):
        try:
            hour, minute = (int(part) for part in value.split(":"))
        except ValueError:
            logger.error(f"Bad time {value!r} for {mosque_id}")
            return None
        # Build the time in the masjid's timezone so the UTC conversion picks
        # up the right DST offset for that date.
        local = datetime(today.year, month, day, hour, minute, tzinfo=cal["tz"])
        result[name] = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # The old API spelled it "maghreb"; the schedule picker stores "maghrib".
    result["maghrib"] = result["maghreb"]
    result["timezone"] = cal["timezone"]
    return result


async def is_valid_mosque(mosque_id: str) -> bool:
    """Whether a mawaqit masjid id resolves to real prayer times."""
    return await get_prayer_times(mosque_id) is not None
