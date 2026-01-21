# Twitch Integration Setup Guide

## Quick Start (5 minutes!)

### Step 1: Get Twitch OAuth Token

1. Go to https://twitchtokengenerator.com/
2. Click **"Bot Chat Token"**
3. Log in with your Twitch account
4. Click **"Authorize"**
5. Copy the token (starts with `oauth:`)

### Step 2: Install Dependencies

```bash
cd backend
pip install twitchio
```

### Step 3: Configure .env

Open `backend/.env` and add:

```bash
TWITCH_ENABLED=true
TWITCH_BOT_TOKEN=oauth:your_token_here
TWITCH_CHANNEL=your_channel_name
TWITCH_BOT_PREFIX=!
```

**Example:**
```bash
TWITCH_ENABLED=true
TWITCH_BOT_TOKEN=oauth:abc123def456
TWITCH_CHANNEL=lumina_ai
TWITCH_BOT_PREFIX=!
```

### Step 4: Start the Backend

```bash
python backend/api_server.py
```

You should see:
```
[Startup] Twitch bot initialized for channel: your_channel_name
[TwitchBot] Logged in as your_bot_name
[TwitchBot] Bot is ready!
```

### Step 5: Test It!

1. Go to your Twitch channel
2. Type a message in chat
3. Watch the backend logs - you should see:
   ```
   [TwitchBot] YourUsername: Hello Lumina!
   [ChatAggregator] Queued message from YourUsername (priority: 1.50)
   ```

## Available Commands

Your viewers can use these commands:

- `!lumina` - Greet Lumina
- `!promo` - Ask about current promotions
- `!help` - Show available commands

## Troubleshooting

**Bot not connecting?**
- Make sure token starts with `oauth:`
- Check channel name is correct (lowercase, no spaces)
- Verify `TWITCH_ENABLED=true`

**Messages not appearing?**
- Check backend logs for `[TwitchBot]` messages
- Make sure chat aggregation is enabled
- Try sending a longer message (min 2 characters)

**Bot can't send messages?**
- Verify the bot account has chat privileges
- Check if the channel is in followers-only mode

## Next Steps

Once Twitch is working, you can:
1. Add frontend WebSocket client to see chat in UI
2. Customize bot commands in `twitch_bot.py`
3. Adjust aggregation settings for your stream

## Testing Without Going Live

You can test in your own channel without streaming:
1. Just open your Twitch channel page
2. Type in chat
3. The bot will respond even if you're offline!
