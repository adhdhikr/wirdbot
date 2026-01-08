# Quran Wird Discord Bot

A Discord bot that sends daily Quran pages to your server with completion tracking, streak management, and prayer time integration.

## Features

- 📖 **Daily Page Distribution**: Automatically sends configurable pages from different mushaf types
- 🕌 **Prayer Time Integration**: Schedule page delivery at specific prayer times using mosque IDs
- ⏰ **Custom Scheduling**: Set multiple custom times throughout the day
- ✅ **Completion Tracking**: Users can mark pages as read with button interactions
- 🔥 **Streak System**: Track daily streaks and longest streaks
- 👥 **User Registration**: Optional registration system with role assignment
- 📊 **Progress Reports**: Configurable follow-up messages showing completion status
- 🎨 **Multiple Mushafs**: Support for different mushaf types (Madani, Uthmani, Indopak, etc.)

## Setup

### Prerequisites

1. Python 3.8+
2. Discord Bot Token ([Create one here](https://discord.com/developers/applications))
3. Your Quran API running (from the `api` folder)
4. Mosque ID from the prayer times API

### Installation

1. Install dependencies:
```bash
cd bot
pip install -r requirements.txt
```

2. Create `.env` file:
```bash
copy .env.example .env
```

3. Edit `.env` and add your bot token:
```env
DISCORD_TOKEN=your_discord_bot_token_here
API_BASE_URL=http://localhost:5000
PRAYER_API_BASE_URL=https://api.mrie.dev/prayertimes
```

4. Make sure your Quran API is running:
```bash
cd ../api
python main.py
```

5. Run the bot:
```bash
cd ../bot
python main.py
```

## Bot Commands

### Admin Commands

#### `/setup`
Initial configuration modal for the bot. Sets up:
- Mosque ID (for prayer times)
- Mushaf type (madani, uthmani, indopak, etc.)
- Pages per day (1-20)
- Channel ID where pages will be sent

#### `/config`
View current server configuration including all settings and scheduled times.

#### `/schedule <action> [prayer]`
Manage scheduled times for sending pages:
- `add_time`: Opens modal to add custom time (HH:MM UTC)
- `add_prayer`: Add prayer time (fajr, dhuhr, asr, maghrib, isha)
- `list`: Show all scheduled times with their IDs
- `clear`: Remove all scheduled times

**Examples:**
```
/schedule add_prayer prayer:fajr
/schedule add_prayer prayer:maghrib
/schedule add_time
```

#### `/update <setting> <value>`
Update individual configuration settings:
- `mushaf`: Change mushaf type
- `pages_per_day`: Change number of pages (1-20)
- `channel`: Change channel ID
- `mosque_id`: Change mosque ID
- `followup_channel`: Set separate channel for progress reports
- `followup_on_completion`: Enable/disable instant followup on completion (true/false)

**Examples:**
```
/update mushaf uthmani
/update pages_per_day 2
/update followup_on_completion true
```

#### `/set_role <role>`
Set the role that will be assigned to registered users.

#### `/send_now`
Manually trigger sending today's pages immediately.

### User Commands

#### `/register`
Register for daily Wird tracking. Enables:
- Marking pages as complete
- Streak tracking
- Automatic role assignment (if configured)
- Inclusion in progress reports

#### `/unregister`
Unregister from Wird tracking and remove the Wird role.

#### `/stats`
View your personal statistics:
- Current streak
- Longest streak
- Today's progress
- Last completion date

## How It Works

### 1. Initial Setup (Admin)
1. Admin runs `/setup` and fills in the configuration modal
2. Admin uses `/schedule` to add times (prayer times and/or custom times)
3. Optionally, admin sets a Wird role using `/set_role`

### 2. Scheduled Sending
- Bot checks every minute for scheduled times
- At scheduled time, sends pages (one message per page) to configured channel
- Each page has a "Mark as Read" button
- Optionally sends follow-up report after pages are sent

### 3. User Interaction
- First time user clicks "Mark as Read", they're prompted to register
- After registration, clicking button marks page complete
- Bot tracks individual page completions and updates streaks
- When all pages for the day are completed, bot congratulates user

### 4. Progress Tracking
- Follow-up messages show who completed and who hasn't
- Displays current streaks for completed users
- Can be sent:
  - After pages are sent (default)
  - When users complete (if configured)
  - To a different channel (if configured)

### 5. Streak System
- Streak increases when user completes pages on consecutive days
- Breaks if user misses a day
- Longest streak is preserved
- Displayed in stats and progress reports

## Configuration Examples

### Example 1: Send at Fajr and Maghrib
```
/setup (fill in configuration)
/schedule add_prayer prayer:fajr
/schedule add_prayer prayer:maghrib
```

### Example 2: Send at specific times
```
/setup (fill in configuration)
/schedule add_time → Enter "06:00" (6 AM UTC)
/schedule add_time → Enter "18:00" (6 PM UTC)
```

### Example 3: Multiple pages, separate follow-up channel
```
/setup (set pages_per_day to 3)
/update followup_channel 123456789
/update followup_on_completion true
```

## Prayer Times API

The bot uses the prayer times API: `https://api.mrie.dev/prayertimes/{mosqueId}/{day}/{month}`

- Times are returned in UTC
- Bot converts them to Discord timestamps
- You can omit day/month (defaults to current day)
- Mosque ID must be configured by server owner

## Database Structure

The bot uses SQLite with the following tables:
- `guilds`: Server configurations
- `scheduled_times`: Custom and prayer time schedules
- `users`: User registrations and streaks
- `completions`: Individual page completion records
- `daily_sessions`: Tracking of daily page batches

## Troubleshooting

**Bot not sending pages:**
- Check `/config` to verify configuration
- Verify scheduled times with `/schedule list`
- Ensure API is running
- Check bot has permissions in target channel

**Prayer times not working:**
- Verify mosque ID is correct
- Check prayer times API is accessible
- Times are checked every minute (some delay is normal)

**Images not loading:**
- Ensure Quran API is running on correct URL
- Verify mushaf folder contains page images
- Check image file naming (page1.png, page2.png, etc.)

**Users can't complete pages:**
- They must register first using `/register`
- Check they have permission to interact with messages

## Notes

- Bot automatically prevents duplicate page sends on same day
- Pages loop back to 1 after reaching 604
- All times in UTC for consistency
- Streak tracking is based on consecutive days with completions
- Follow-up messages show max 10 users per section
