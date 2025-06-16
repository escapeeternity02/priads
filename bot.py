import os
import json
import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from aiohttp import web
from colorama import Fore, init

init(autoreset=True)

CREDENTIALS_FOLDER = "sessions"
DATA_FILE = "data.json"
LOG_FILE = "ad_log.txt"
BACKUP_FILE = "backup.json"
ADMIN_ID = 6249999953

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

start_time = time.time()

# Logging

def log_event(text):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")

# Data functions

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        data = {
            "groups": {},
            "frequency": 5,
            "mode": "random",
            "last_sent_ad_index": 0,
            "welcome_message": "To buy anything DM @EscapeEternity! This is just a Bot.",
            "admins": [ADMIN_ID],
            "enabled": True,
            "allgroup": False
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def backup_data():
    with open(BACKUP_FILE, 'w') as f:
        json.dump(load_data(), f)

def restore_data():
    with open(BACKUP_FILE, 'r') as f:
        data = json.load(f)
    save_data(data)

# Web server

async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

# Ad sender

async def ad_sender(client):
    while True:
        try:
            data = load_data()
            if not data.get("enabled", True):
                await asyncio.sleep(10)
                continue

            ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            saved_messages = [m for m in ads.messages if getattr(m, 'message', None) or getattr(m, 'media', None)]

            if not saved_messages:
                await asyncio.sleep(60)
                continue

            target_groups = data["groups"].keys() if not data.get("allgroup") else [d.entity.id for d in await client.get_dialogs() if d.is_group]
            for gid in target_groups:
                try:
                    gid = int(gid) if isinstance(gid, str) else gid
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    fwd_msg = await client.forward_messages(gid, msg.id, "me")
                    log_event(f"[FORWARD] {gid} -> Ad ID {msg.id}")
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    log_event(f"[ERROR] Sending to {gid}: {e}")

            await asyncio.sleep(data.get("frequency", 5) * 60)
        except Exception as e:
            log_event(f"[SENDER ERROR] {e}")
            await asyncio.sleep(30)

# Command handler

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        sender_id = sender.id
        data = load_data()
        cmd = event.raw_text.strip()
        is_admin = sender_id in data.get("admins", [])

        # DM welcome message
        if event.is_private and not is_admin:
            await event.reply(data.get("welcome_message", "To buy anything DM @EscapeEternity! This is just a Bot."))
            return

        if not is_admin:
            return

        # Admin commands
        if cmd == "!start":
            data["enabled"] = True
            save_data(data)
            await event.reply("▶️ Ad sending resumed.")

        elif cmd == "!stop":
            data["enabled"] = False
            save_data(data)
            await event.reply("⏸ Ad sending paused.")

        elif cmd == "!uptime":
            uptime = int(time.time() - start_time)
            h, m = divmod(uptime, 3600)
            m, s = divmod(m, 60)
            await event.reply(f"⏱ Uptime: {h}h {m}m {s}s")

        elif cmd.startswith("!log"):
            try:
                days = int(cmd.split()[1])
                cutoff = datetime.now() - timedelta(days=days)
                with open(LOG_FILE, 'r') as f:
                    lines = [line for line in f.readlines() if datetime.strptime(line[1:20], '%Y-%m-%d %H:%M:%S') > cutoff]
                for chunk in [lines[i:i+20] for i in range(0, len(lines), 20)]:
                    await event.reply("\n".join(chunk))
            except:
                await event.reply("❌ Usage: !log <days>")

        elif cmd.startswith("!addadmin"):
            try:
                uid = int(cmd.split()[1])
                if uid not in data["admins"]:
                    data["admins"].append(uid)
                    save_data(data)
                    await event.reply(f"✅ Admin {uid} added")
            except:
                await event.reply("❌ Usage: !addadmin <user_id>")

        elif cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if str(gid) not in data["groups"]:
                    data["groups"][str(gid)] = {"freq": data["frequency"]}
                    save_data(data)
                    await event.reply(f"✅ Group {gid} added")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd == "!groups":
            await event.reply("\n".join([f"{g} - {v['freq']}m" for g, v in data["groups"].items()]) or "No groups added")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = cmd.split()[1]
                data["groups"].pop(gid, None)
                save_data(data)
                await event.reply(f"✅ Removed {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            parts = cmd.split()
            try:
                if len(parts) == 2:
                    data["frequency"] = int(parts[1])
                elif len(parts) == 3:
                    gid = parts[1]
                    freq = int(parts[2])
                    if gid in data["groups"]:
                        data["groups"][gid]["freq"] = freq
                save_data(data)
                await event.reply("✅ Frequency updated")
            except:
                await event.reply("❌ Usage: !setfreq [group_id] <minutes>")

        elif cmd.startswith("!setmode"):
            mode = cmd.split()[1]
            if mode in ["random", "order"]:
                data["mode"] = mode
                save_data(data)
                await event.reply(f"✅ Mode set to {mode}")

        elif cmd == "!status":
            await event.reply(json.dumps(data, indent=2))

        elif cmd == "!preview":
            ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            if ads.messages:
                await client.send_message(event.chat_id, ads.messages[0])

        elif cmd == "!backup":
            backup_data()
            await client.send_file(sender_id, BACKUP_FILE)

        elif cmd == "!restore":
            restore_data()
            await event.reply("✅ Restored backup")

        elif cmd == "!allgroup on":
            data["allgroup"] = True
            save_data(data)
            await event.reply("✅ Now using all joined groups")

        elif cmd == "!allgroup off":
            data["allgroup"] = False
            save_data(data)
            await event.reply("✅ Back to selected groups only")

        elif cmd.startswith("!dm"):
            try:
                parts = cmd.split(maxsplit=2)
                user = parts[1]
                msg = parts[2]
                sent = await client.send_message(user, msg)
                log_event(f"[DM] {user}: {msg}")
                await event.reply("✅ Message sent")
            except:
                await event.reply("❌ Usage: !dm <user_id/@username> <message>")

        elif cmd == "!help":
            await event.reply(
                "🛠 Commands:\n"
                "!start / !stop – Toggle bot\n"
                "!uptime – Show uptime\n"
                "!log <days> – Show logs\n"
                "!addgroup <id> – Add group\n"
                "!rmgroup <id> – Remove group\n"
                ""
                "!setmode random/order\n"
                "!status – Show status\n"
                "!preview – Preview next ad\n"
                "!dm <user> <msg> – DM user\n"
                "!backup / !restore – Settings\n"
                "!allgroup on|off – Toggle all groups")

    @client.on(events.MessageReply())
    async def log_group_replies(event):
        try:
            if event.is_group and not event.sender.bot:
                sender = await event.get_sender()
                group = await event.get_chat()
                msg_text = event.message.message or "[non-text]"
                log = f"\ud83d\udd01 Someone replied to ad in {group.title} ({group.id})\nFrom: {sender.id} - {sender.first_name}\nMessage: {msg_text}"
                log_event(f"[REPLY] {group.id} {sender.id}: {msg_text}")
                await client.send_message(ADMIN_ID, log)
        except Exception as e:
            log_event(f"[REPLY LOG ERROR] {e}")

# Main function

async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    client = TelegramClient(
        os.path.join(CREDENTIALS_FOLDER, session_name),
        credentials["api_id"],
        credentials["api_hash"]
    )

    await client.connect()
    if not await client.is_user_authorized():
        return

    try:
        await client.send_message(ADMIN_ID, "✅ AdBot is now online.")
    except Exception as e:
        log_event(f"[ERROR] Failed to notify admin: {e}")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
