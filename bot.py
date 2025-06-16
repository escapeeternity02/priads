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
ADMIN_ID = 6249999953

os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)

start_time = time.time()

def log_event(text):
    with open(LOG_FILE, "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        print(Fore.RED + "Resetting corrupted data.json...")
        data = {
            "groups": [],
            "frequency": 5,
            "mode": "random",
            "last_sent_ad_index": 0,
            "welcome_message": "To buy anything DM @EscapeEternity! This is just a Bot.",
            "admins": [ADMIN_ID],
            "enabled": True
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

async def start_web_server():
    async def handle(request):
        return web.Response(text="✅ Bot is running on Render")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    print(Fore.YELLOW + "Web server running.")

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
                print(Fore.RED + "No saved messages found.")
                await asyncio.sleep(60)
                continue

            for gid in data["groups"]:
                try:
                    if data["mode"] == "random":
                        msg = random.choice(saved_messages)
                    else:
                        index = data["last_sent_ad_index"] % len(saved_messages)
                        msg = saved_messages[index]
                        data["last_sent_ad_index"] += 1
                        save_data(data)

                    fwd_msg = await client.forward_messages(gid, msg.id, "me")
                    link = f"https://t.me/c/{str(gid)[4:]}/{fwd_msg.id}" if str(gid).startswith("-100") else f"(no link)"
                    log_event(f"[FORWARD] To {gid} | Link: {link} | ID: {msg.id} | Text: {msg.message[:100] if msg.message else '[media]'}")
                    print(Fore.GREEN + f"Forwarded ad to {gid}")
                    await asyncio.sleep(random.uniform(10, 20))
                except Exception as e:
                    print(Fore.RED + f"Error sending to group {gid}: {e}")

            print(Fore.CYAN + f"Ad cycle done. Sleeping for {data['frequency']} minutes.")
            await asyncio.sleep(data["frequency"] * 60)
        except Exception as e:
            print(Fore.RED + f"Error in ad_sender: {e}")
            await asyncio.sleep(30)

async def command_handler(client):
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        sender_id = sender.id
        data = load_data()
        cmd = event.raw_text.strip()
        is_admin = sender_id in data.get("admins", [])

        if event.is_private and not is_admin:
            await event.reply(data.get("welcome_message", "To buy anything DM @EscapeEternity! This is just a Bot."))
            return

        if not is_admin:
            return

        if cmd == "!start":
            data["enabled"] = True
            save_data(data)
            await event.reply("▶️ Ad sending resumed.")

        elif cmd == "!stop":
            data["enabled"] = False
            save_data(data)
            await event.reply("⏸ Ad sending paused.")

        elif cmd == "!uptime":
            uptime_seconds = int(time.time() - start_time)
            hours, rem = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            await event.reply(f"⏱ Uptime: {hours}h {minutes}m {seconds}s")

        elif cmd.startswith("!log"):
            try:
                days = int(cmd.split()[1])
                cutoff = datetime.now() - timedelta(days=days)
                with open(LOG_FILE, 'r') as f:
                    lines = [line for line in f.readlines() if datetime.strptime(line[1:20], '%Y-%m-%d %H:%M:%S') > cutoff]
                    if not lines:
                        await event.reply("📄 No logs found for requested period.")
                        return
                    chunks = [''.join(lines[i:i+10]) for i in range(0, len(lines), 10)]
                    for chunk in chunks:
                        await client.send_message(sender_id, f"📋 Log chunk:\n{chunk}")
            except:
                await event.reply("❌ Usage: !log <days>")

        elif cmd.startswith("!addadmin"):
            try:
                uid = int(cmd.split()[1])
                if uid not in data["admins"]:
                    data["admins"].append(uid)
                    save_data(data)
                    await event.reply(f"✅ Added admin {uid}")
                else:
                    await event.reply("Already an admin.")
            except:
                await event.reply("❌ Usage: !addadmin <user_id>")

        elif cmd.startswith("!addgroup"):
            try:
                gid = int(cmd.split()[1])
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Added group {gid}")
                else:
                    await event.reply("Group already in list.")
            except:
                await event.reply("❌ Usage: !addgroup <group_id>")

        elif cmd == "!join":
            if event.is_group:
                gid = event.chat_id
                if gid not in data["groups"]:
                    data["groups"].append(gid)
                    save_data(data)
                    await event.reply(f"✅ Group {gid} added.")
                else:
                    await event.reply("Group already added.")
            else:
                await event.reply("❌ Use this command in a group.")

        elif cmd.startswith("!rmgroup"):
            try:
                gid = int(cmd.split()[1])
                data["groups"] = [g for g in data["groups"] if g != gid]
                save_data(data)
                await event.reply(f"✅ Removed group {gid}")
            except:
                await event.reply("❌ Usage: !rmgroup <group_id>")

        elif cmd.startswith("!setfreq"):
            try:
                freq = int(cmd.split()[1])
                data["frequency"] = freq
                save_data(data)
                await event.reply(f"✅ Frequency set to {freq} minutes")
            except:
                await event.reply("❌ Usage: !setfreq <minutes>")

        elif cmd.startswith("!setmode"):
            try:
                mode = cmd.split()[1].lower()
                if mode in ["random", "order"]:
                    data["mode"] = mode
                    save_data(data)
                    await event.reply(f"✅ Mode set to {mode}")
                else:
                    await event.reply("❌ Use: !setmode random | order")
            except:
                await event.reply("❌ Usage: !setmode <random/order>")

        elif cmd == "!status":
            uptime_seconds = int(time.time() - start_time)
            hours, rem = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            uptime = f"{hours}h {minutes}m {seconds}s"
            await event.reply(f"👥 Groups: {data['groups']}\n📤 Mode: {data['mode']}\n⏱ Frequency: {data['frequency']} min\n🕒 Uptime: {uptime}\n🚦 Active: {data.get('enabled', True)}")

        elif cmd == "!groups":
            await event.reply("📢 Added Groups:\n" + '\n'.join([str(g) for g in data["groups"]]) if data["groups"] else "No groups added.")

        elif cmd == "!test":
            try:
                ads = await client(GetHistoryRequest(peer="me", limit=20, offset_id=0,
                                                     offset_date=None, max_id=0, min_id=0,
                                                     add_offset=0, hash=0))
                valid_ads = [m for m in ads.messages if m.message or m.media]
                if not valid_ads:
                    await event.reply("❌ No saved messages to forward.")
                    return
                msg = valid_ads[0]
                for gid in data["groups"]:
                    await client.forward_messages(gid, msg.id, "me")
                    await asyncio.sleep(3)
                await event.reply("✅ Sent test ad to all selected groups.")
            except Exception as e:
                await event.reply(f"❌ Error: {e}")

        elif cmd.startswith("!dm"):
            parts = cmd.split(maxsplit=2)
            if len(parts) < 3:
                await event.reply("❌ Usage: !dm <user_id/@username> <message>")
                return
            target = parts[1]
            message = parts[2]
            try:
                entity = await client.get_entity(target)
                sent = await client.send_message(entity, message)
                link = f"https://t.me/c/{str(sent.chat_id)[4:]}/{sent.id}" if str(sent.chat_id).startswith("-100") else f"(no link)"
                log_event(f"[DM] To {target} | Link: {link} | Text: {message[:100]}")
                await event.reply(f"✅ Message sent to {target}")
            except Exception as e:
                await event.reply(f"❌ Failed to send message: {e}")

        elif cmd.startswith("!welcome"):
            welcome_msg = cmd[9:].strip()
            if welcome_msg:
                data["welcome_message"] = welcome_msg
                save_data(data)
                await event.reply("✅ Welcome message updated.")
            else:
                await event.reply("❌ Usage: !welcome <your_message>")

        elif cmd == "!preview":
            ads = await client(GetHistoryRequest(peer="me", limit=1, offset_id=0,
                                                 offset_date=None, max_id=0, min_id=0,
                                                 add_offset=0, hash=0))
            if not ads.messages:
                await event.reply("❌ No ads saved.")
                return
            msg = ads.messages[0]
            await event.reply("👀 Preview of next ad:")
            await client.send_message(event.chat_id, msg)

        elif cmd == "!help":
            await event.reply(
                "🛠 Available Commands:\n"
                "!start / !stop – Resume or pause ad delivery\n"
                "!uptime – Bot uptime\n"
                "!log <days> – Show ad logs\n"
                "!addgroup <id> – Add group ID\n"
                "!rmgroup <id> – Remove group ID\n"
                "!setfreq <minutes> – Set ad interval\n"
                "!setmode random/order – Set ad selection mode\n"
                "!status – View current settings\n"
                "!test – Send latest ad to groups\n"
                "!dm <user_id/@username> <msg> – DM a user\n"
                "!groups – List all groups\n"
                "!join – Add group from within\n"
                "!preview – Show next ad\n"
                "!welcome <msg> – Set auto-DM reply\n"
                "!addadmin <id> – Add more admins\n"
                "!help – Show this menu"
            )

async def main():
    session_name = "session1"
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")

    if not os.path.exists(path):
        print(Fore.RED + f"No credentials file at {path}")
        return

    with open(path, "r") as f:
        credentials = json.load(f)

    proxy_args = tuple(credentials.get("proxy")) if credentials.get("proxy") else None
    client = TelegramClient(
        os.path.join(CREDENTIALS_FOLDER, session_name),
        credentials["api_id"],
        credentials["api_hash"],
        proxy=proxy_args
    )

    await client.connect()
    if not await client.is_user_authorized():
        print(Fore.RED + "Not logged in.")
        return

    try:
        await client.send_message(ADMIN_ID, "✅ Bot started and running on Render.")
    except:
        print(Fore.RED + "Couldn't notify admin.")

    await asyncio.gather(
        start_web_server(),
        command_handler(client),
        ad_sender(client)
    )

if __name__ == "__main__":
    asyncio.run(main())
