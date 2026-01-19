import os
import uuid
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ChatMemberStatus


BOT_TOKEN = "token"
API_ID = 20477007
API_HASH = "022facd7601ec54f48c86f6d342a246e"

UPDATE_CHANNEL = "without@"  
ADMINS = [11111]  

START_PHOTO_URL = "https://i.ibb.co/xtVKjXM3/27b6a84d0e5cb57c7a4ccf79935b8174.jpg"
WELCOME_PHOTO_URL = START_PHOTO_URL


DC1_FILE = "dc1_users.txt"
DC3_FILE = "dc3_users.txt"
DC5_FILE = "dc5_users.txt"
ALL_USERS_FILE = "all_scraped_users.txt"
DATA_FILE = "bot_data.json"
SESSIONS_DIR = "sessions"
PREMIUM_FILE = "premium.json"  

BTN_CHAR = "×"

Telegram = Client("bot_session", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
user_clients: List[Client] = []
user_cooldowns = {}
user_states = {}
copy_storage = {}

def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, default=str, indent=2)

def ensure_files():
    for fn in (DC1_FILE, DC3_FILE, DC5_FILE, ALL_USERS_FILE):
        if not os.path.exists(fn):
            open(fn, "w").close()
    if not os.path.exists(DATA_FILE):
        save_json(DATA_FILE, {"scraped_groups": [], "total_scraped": 0})
    if not os.path.exists(PREMIUM_FILE):
        save_json(PREMIUM_FILE, {})

def load_data():
    return load_json(DATA_FILE, {"scraped_groups": [], "total_scraped": 0})

def save_data(data):
    save_json(DATA_FILE, data)

def load_premium():
    return load_json(PREMIUM_FILE, {})

def save_premium(p):
    save_json(PREMIUM_FILE, p)

def save_username_to_file(username: str, dc_id: int):
    filename = {1: DC1_FILE, 3: DC3_FILE, 5: DC5_FILE}.get(dc_id)
    if filename:
        with open(filename, "a") as f:
            f.write(f"{username}\n")
        with open(ALL_USERS_FILE, "a") as af:
            af.write(f"{username} (DC{dc_id})\n")

def get_usernames_from_file(dc_id: int, count: int = 20):
    filename = {1: DC1_FILE, 3: DC3_FILE, 5: DC5_FILE}.get(dc_id)
    if not filename or not os.path.exists(filename):
        return []
    try:
        with open(filename, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        take = lines[:count]
        remaining = lines[count:]
        with open(filename, "w") as f:
            for l in remaining:
                f.write(l + "\n")
        return take
    except:
        return []

def count_usernames_in_file(dc_id: int):
    filename = {1: DC1_FILE, 3: DC3_FILE, 5: DC5_FILE}.get(dc_id)
    if not filename or not os.path.exists(filename):
        return 0
    with open(filename, "r") as f:
        return len([l for l in f.readlines() if l.strip()])

def is_admin(user_id: int) -> bool:
    try:
        return int(user_id) in [int(x) for x in ADMINS]
    except:
        return False

def add_premium_admin(user_id: int, days: int):
    p = load_premium()
    uid = str(int(user_id))
    now = datetime.utcnow()
    
    if uid in p and p[uid]:
        try:
            cur = datetime.fromisoformat(p[uid])
            if cur < now:
                cur = now
        except:
            cur = now
    else:
        cur = now
    new_exp = cur + timedelta(days=days)
    p[uid] = new_exp.isoformat()
    save_premium(p)
    return new_exp

def remove_premium_admin(user_id: int):
    p = load_premium()
    uid = str(int(user_id))
    if uid in p:
        p.pop(uid, None)
        save_premium(p)
        return True
    return False

def get_premium_info(user_id: int):
    p = load_premium()
    uid = str(int(user_id))
    if uid in p and p[uid]:
        try:
            exp = datetime.fromisoformat(p[uid])
            return exp
        except:
            return None
    return None

def is_premium(user_id: int) -> bool:
    try:
        exp = get_premium_info(user_id)
        if exp and exp > datetime.utcnow():
            return True
    except:
        pass
    return False


async def is_user_subscribed(user_id: int):
    try:
        member = await Telegram.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]
    except Exception:
        return False

async def send_photo_or_text(obj, photo_url: str, caption: str, reply_markup=None):
    try:
        if hasattr(obj, "reply_photo"):
            return await obj.reply_photo(photo=photo_url, caption=caption, reply_markup=reply_markup) if photo_url else await obj.reply_text(caption, reply_markup=reply_markup)
        elif hasattr(obj, "message"):
            if photo_url:
                return await obj.message.reply_photo(photo=photo_url, caption=caption, reply_markup=reply_markup)
            else:
                return await obj.message.reply_text(caption, reply_markup=reply_markup)
    except Exception:
        return await obj.reply_text(caption, reply_markup=reply_markup) if hasattr(obj, "reply_text") else None

async def edit_message_with_photo(callback_query: CallbackQuery, photo_url: str, caption: str, reply_markup=None):
    try:
        if photo_url:
            await callback_query.message.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            await callback_query.message.edit_text(text=caption, reply_markup=reply_markup)
    except Exception as e:
        print("edit error:", e)


@Telegram.on_message(filters.private & filters.command(["start"]))
async def start_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not await is_user_subscribed(uid):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{BTN_CHAR} Join Channel", url=f"https://t.me/{UPDATE_CHANNEL}")],
            [InlineKeyboardButton(f"{BTN_CHAR} I've Joined", callback_data="check_sub")]
        ])
        await send_photo_or_text(message, WELCOME_PHOTO_URL,
                                 "** Subscription Required!**\nJoin our updates channel to use the bot.",
                                 buttons)
        return
    await show_main_menu(message, uid, is_new=True)

async def show_main_menu(obj, user_id: int, is_new: bool = False):
    from_user = getattr(obj, "from_user", None) or (getattr(obj, "message", None) and getattr(obj.message, "from_user", None))
    if not from_user:
        class U: pass
        from_user = U()
        from_user.id = user_id
        from_user.first_name = "User"
        from_user.username = None

    dc1 = count_usernames_in_file(1)
    dc3 = count_usernames_in_file(3)
    dc5 = count_usernames_in_file(5)

    buttons = [
        [InlineKeyboardButton(f"{BTN_CHAR} ", callback_data="my_dc")],
        [InlineKeyboardButton(f"{BTN_CHAR} Bulk Check DCs", callback_data="bulk_check")],
    ]
    if dc1 > 0:
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Get DC1 Users ({dc1})", callback_data="get_dc_choice_1")])
    if dc3 > 0:
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Get DC3 Users ({dc3})", callback_data="get_dc_choice_3")])
    if dc5 > 0:
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Get DC5 Users ({dc5})", callback_data="get_dc_choice_5")])

    # Scrape: show locked if not premium/admin
    if is_premium(user_id) or is_admin(user_id):
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Scrape Members", callback_data="scrape_members")])
    else:
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Scrape Members (Premium only)", callback_data="scrape_locked")])

    if is_admin(user_id):
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Admin Panel", callback_data="admin_panel")])

    buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Help", callback_data="help_user")])
    buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Updates Channel", url=f"https://t.me/{UPDATE_CHANNEL}")])
    buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Refresh", callback_data="refresh_menu")])

    paid = " Paid" if is_premium(user_id) else " Not Paid"
    caption = f"** DC Tracker Bot**\n\nWelcome To Flash\n\n**Premium:** {paid}\n\nChoose an option:"
    if is_new:
        await send_photo_or_text(obj, START_PHOTO_URL, caption, InlineKeyboardMarkup(buttons))
    else:
        try:
            await edit_message_with_photo(obj, START_PHOTO_URL, caption, InlineKeyboardMarkup(buttons))
        except:
            pass


@Telegram.on_callback_query(filters.regex("check_sub"))
async def check_sub_cb(client: Client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id
    if await is_user_subscribed(uid):
        try:
            await callback_query.message.delete()
        except:
            pass
        await show_main_menu(callback_query, uid, is_new=True)
        await callback_query.answer(" Subscription verified!")
    else:
        await callback_query.answer(" You haven't joined the channel yet!", show_alert=True)


@Telegram.on_callback_query(filters.regex(r"my_dc"))
async def my_dc_cb(client: Client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id

    
    dc = getattr(callback_query.from_user, "dc_id", None)

    
    if not dc:
        try:
            u = await Telegram.get_users(uid)
            dc = getattr(u, "dc_id", None)
        except:
            dc = None

    
    if not dc:
        await callback_query.answer(
            f"{BTN_CHAR} Unable to detect your DC.",
            show_alert=True
        )
        return

    
    try:
        await callback_query.message.edit_text(
            f"{BTN_CHAR} Your Data Center: **DC{dc}**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]
            ])
        )
    except:
        
        await callback_query.message.reply_text(
            f"{BTN_CHAR} Your Data Center: **DC{dc}**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]
            ])
        )

    await callback_query.answer()

async def check_cooldown(user_id: int, cooldown_seconds: int = 420):
    last = user_cooldowns.get(user_id)
    if not last:
        return True, 0
    elapsed = time.time() - last
    if elapsed >= cooldown_seconds:
        return True, 0
    return False, int(cooldown_seconds - elapsed)

@Telegram.on_callback_query(filters.regex("bulk_check"))
async def bulk_check_menu(client: Client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id
    can_check, rem = await check_cooldown(uid)
    if not can_check:
        mins = rem // 60
        secs = rem % 60
        await callback_query.answer(f" Cooldown! Wait {mins}m {secs}s", show_alert=True)
        return
    text = "** Bulk DC Checker**\n\nSend up to 20 usernames (one per line)."
    await edit_message_with_photo(callback_query, None, text, InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    user_states[uid] = "awaiting_usernames"
    await callback_query.answer()

@Telegram.on_message(filters.private & filters.text & ~filters.command(["start","cancel","admin","stats","add_premium","remove_premium","premium_info"]))
async def handle_text_messages(client: Client, message: Message):
    uid = message.from_user.id
    
    if user_states.get(uid) == "awaiting_usernames":
        await handle_bulk_check(message)
        return
    
    if user_states.get(f"scrape_{uid}") == "awaiting_group":
        await handle_scrape_members(message)
        return
    if f"custom_amount_{uid}" in user_states:
        await handle_custom_amount(message)
        return
    if user_states.get(f"scrape_limit_{uid}"):
        await handle_scrape_limit(message)
        return
    if user_states.get(f"broadcast_{uid}") == "awaiting_broadcast" and is_admin(uid):
        await handle_broadcast_message(message)
        return

async def handle_bulk_check(message: Message):
    uid = message.from_user.id
    user_states.pop(uid, None)
    if not await is_user_subscribed(uid):
        await message.reply_text(" Please subscribe to the channel first using /start")
        return
    can_check, rem = await check_cooldown(uid)
    if not can_check:
        mins = rem // 60
        secs = rem % 60
        await message.reply_text(f" Cooldown active! Wait {mins}m {secs}s")
        return
    usernames = [l.strip() for l in message.text.strip().split("\n") if l.strip()]
    if len(usernames) > 20:
        await message.reply_text(" Maximum 20 usernames allowed!")
        return
    processing_msg = await message.reply_text(" Processing...")
    dc1_users = []
    dc3_users = []
    dc5_users = []
    failed = []
    count = 0
    for uname in usernames:
        count += 1
        if count % 3 == 0:
            try:
                await processing_msg.edit_text(f" Processing... ({count}/{len(usernames)})")
            except:
                pass
        dc_id = await check_user_dc(uname)
        if dc_id == 1:
            handle = uname if uname.startswith("@") else "@" + uname.replace("@","")
            dc1_users.append(handle)
            save_username_to_file(handle, 1)
        elif dc_id == 3:
            handle = uname if uname.startswith("@") else "@" + uname.replace("@","")
            dc3_users.append(handle)
            save_username_to_file(handle, 3)
        elif dc_id == 5:
            handle = uname if uname.startswith("@") else "@" + uname.replace("@","")
            dc5_users.append(handle)
            save_username_to_file(handle, 5)
        elif dc_id:
            pass
        else:
            failed.append(uname)
        await asyncio.sleep(0.15)

    data = load_data()
    data["total_scraped"] = data.get("total_scraped", 0) + (len(dc1_users) + len(dc3_users) + len(dc5_users))
    save_data(data)
    user_cooldowns[uid] = time.time()

    res = "** DC Check Results**\n\n"
    if dc1_users:
        res += f"**DC1:** `+{len(dc1_users)}`\n" + "\n".join([f" `{u}`" for u in dc1_users[:10]]) + "\n\n"
    if dc3_users:
        res += f"**DC3:** `+{len(dc3_users)}`\n" + "\n".join([f" `{u}`" for u in dc3_users[:10]]) + "\n\n"
    if dc5_users:
        res += f"**DC5:** `+{len(dc5_users)}`\n" + "\n".join([f" `{u}`" for u in dc5_users[:10]]) + "\n\n"
    if failed:
        res += f"** Failed to check:** `{len(failed)}`\n\n"
    res += f"** Added to DB:** `{len(dc1_users)+len(dc3_users)+len(dc5_users)}` users\n**Total Processed:** {len(usernames)}\n**Next check:** 7 minutes\n**Checked at:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

    buttons = []
    if dc1_users:
        key = f"dc1_{uuid.uuid4().hex[:10]}"
        copy_storage[key] = "\n".join(dc1_users)
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Copy DC1 Users", callback_data=f"copy:{key}")])
    if dc3_users:
        key = f"dc3_{uuid.uuid4().hex[:10]}"
        copy_storage[key] = "\n".join(dc3_users)
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Copy DC3 Users", callback_data=f"copy:{key}")])
    if dc5_users:
        key = f"dc5_{uuid.uuid4().hex[:10]}"
        copy_storage[key] = "\n".join(dc5_users)
        buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Copy DC5 Users", callback_data=f"copy:{key}")])

    buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Check Again", callback_data="bulk_check")])
    buttons.append([InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")])

    try:
        await processing_msg.delete()
    except:
        pass
    await message.reply_text(res, reply_markup=InlineKeyboardMarkup(buttons))


@Telegram.on_callback_query(filters.regex(r"copy:(.+)"))
async def copy_users_callback(client: Client, callback_query: CallbackQuery):
    key = callback_query.data.split(":", 1)[1]
    if key not in copy_storage:
        await callback_query.answer(" Data expired or not found.", show_alert=True)
        return
    text = copy_storage.get(key)
    if len(text) > 3500:
        await callback_query.message.reply_document(
            document=("users.txt", text.encode()),
            caption=f"{BTN_CHAR} Here are your users (file)."
        )
    else:
        await callback_query.message.reply_text(f"{BTN_CHAR} **Copied Users:**\n```\n{text}\n```")
    await callback_query.answer("Sent!")


@Telegram.on_callback_query(filters.regex(r"get_dc_choice_(1|3|5)"))
async def get_dc_choice_cb(client: Client, callback_query: CallbackQuery):
    dc = int(callback_query.data.split("_")[-1])
    count = count_usernames_in_file(dc)
    text = f"{BTN_CHAR} DC{dc} Users available: `{count}`\n\nChoose how many to retrieve:"
    buttons = [
        [InlineKeyboardButton(f"{BTN_CHAR} Get All", callback_data=f"get_dc_all_{dc}")],
        [InlineKeyboardButton(f"{BTN_CHAR} Get Custom Amount", callback_data=f"get_dc_custom_{dc}")],
        [InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@Telegram.on_callback_query(filters.regex(r"get_dc_all_(1|3|5)"))
async def get_dc_all_cb(client: Client, callback_query: CallbackQuery):
    dc = int(callback_query.data.split("_")[-1])
    count = count_usernames_in_file(dc)
    if count == 0:
        await callback_query.answer(" No users available.", show_alert=True)
        return
    users = get_usernames_from_file(dc, count)
    text = "```\n" + "\n".join(users) + "\n```"
    await callback_query.message.reply_text(f"{BTN_CHAR} DC{dc} Users ({len(users)}):\n{text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    await callback_query.answer()

@Telegram.on_callback_query(filters.regex(r"get_dc_custom_(1|3|5)"))
async def get_dc_custom_cb(client: Client, callback_query: CallbackQuery):
    dc = int(callback_query.data.split("_")[-1])
    max_amount = count_usernames_in_file(dc)
    if max_amount == 0:
        await callback_query.answer(" No users available.", show_alert=True)
        return
    uid = callback_query.from_user.id
    user_states[f"custom_amount_{uid}"] = dc
    await callback_query.message.edit_text(f"{BTN_CHAR} Send a number (1-{max_amount}) to get that many DC{dc} users:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    await callback_query.answer()


async def setup_user_clients():
    global user_clients
    alive = [c for c in user_clients if getattr(c, "is_connected", False)]
    if alive:
        return True
    user_clients = []
    if not os.path.exists(SESSIONS_DIR):
        print(" sessions folder missing.")
        return False
    sess = [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")]
    if not sess:
        print(" no .session files found.")
        return False
    loaded = 0
    for f in sess:
        name = f.replace(".session", "")
        path = os.path.join(SESSIONS_DIR, name)
        try:
            client = Client(name=path, api_id=API_ID, api_hash=API_HASH, in_memory=False)
            await client.connect()
            user_clients.append(client)
            loaded += 1
            print(f"Loaded session: {name}")
        except Exception as e:
            print(f"Failed load session {name}: {e}")
            continue
    return loaded > 0

async def scrape_with_all_sessions(group_input: str, limit: int = 100):
    ok = await setup_user_clients()
    if not ok:
        return {"success": False, "error": "No user sessions loaded. Put .session files in sessions/"}
    total = 0
    dc_counts = {1:0,3:0,5:0}
    seen = set()
    async def scrape_client(client):
        try:
            chat = await client.get_chat(group_input)
        except Exception:
            return {"total": 0, "dc": {1:0,3:0,5:0}}
        local_total = 0
        local_dc = {1:0,3:0,5:0}
        try:
            async for member in client.get_chat_members(chat.id, limit=limit):
                u = getattr(member, "user", None)
                if not u:
                    continue
                username = getattr(u, "username", None)
                if not username:
                    continue
                uname = "@" + username
                if uname in seen:
                    continue
                seen.add(uname)
                dc_id = getattr(u, "dc_id", None) or getattr(u, "dc", None) or None
                try:
                    dc_id = int(dc_id) if dc_id is not None else None
                except:
                    dc_id = None
                if dc_id in (1,3,5):
                    save_username_to_file(uname, dc_id)
                    local_dc[dc_id] += 1
                local_total += 1
        except Exception:
            pass
        return {"total": local_total, "dc": local_dc}
    tasks = [scrape_client(c) for c in user_clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, dict):
            total += res.get("total", 0)
            d = res.get("dc", {})
            for k in (1,3,5):
                dc_counts[k] += d.get(k, 0)
    return {"success": True, "total": total, "dc1": dc_counts[1], "dc3": dc_counts[3], "dc5": dc_counts[5], "group_name": group_input}

@Telegram.on_callback_query(filters.regex("scrape_members"))
async def scrape_members_menu(client: Client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id
    if not (is_admin(uid) or is_premium(uid)):
        await callback_query.answer(f"{BTN_CHAR} Scraping is premium only. Ask admin to add premium.", show_alert=True)
        return
    await callback_query.message.edit_text(f"{BTN_CHAR} Send a public group/channel link or username to scrape from:")
    user_states[f"scrape_{uid}"] = "awaiting_group"
    await callback_query.answer()

@Telegram.on_callback_query(filters.regex("scrape_locked"))
async def scrape_locked_cb(client: Client, callback_query: CallbackQuery):
    await callback_query.answer(f"{BTN_CHAR} Scraping is premium only. Ask admin to add premium.", show_alert=True)

async def handle_scrape_members(message: Message):
    uid = message.from_user.id
    user_states.pop(f"scrape_{uid}", None)
    group_input = message.text.strip()
    if "t.me/" in group_input:
        if "joinchat/" in group_input:
            await message.reply_text(f"{BTN_CHAR} Private invite links not supported.")
            return
        group_input = group_input.split("t.me/")[-1].split("/")[0]
    group_input = group_input.replace("@", "")
    user_states[f"scrape_limit_{uid}"] = group_input
    await message.reply_text(f"{BTN_CHAR} How many members to scrape from `The Group`? Recommended 100-7000. Send a number:")

async def handle_scrape_limit(message: Message):
    uid = message.from_user.id
    group_input = user_states.get(f"scrape_limit_{uid}")
    if not group_input:
        return
    user_states.pop(f"scrape_limit_{uid}", None)
    try:
        limit = int(message.text.strip())
        if limit <= 0 or limit > 6000:
            await message.reply_text(f"{BTN_CHAR} Limit must be between 1 and 5000")
            return
    except:
        await message.reply_text(f"{BTN_CHAR} Send a valid number")
        return
    if not (is_admin(uid) or is_premium(uid)):
        await message.reply_text(f"{BTN_CHAR} Paid membership required to scrape. Ask admin to add premium.")
        return
    proc = await message.reply_text(f"{BTN_CHAR} Scraping with all sessions... please wait.")
    result = await scrape_with_all_sessions(group_input, limit=limit)
    if result.get("success"):
        data = load_data()
        data["scraped_groups"] = data.get("scraped_groups", [])
        if result["group_name"] not in data["scraped_groups"]:
            data["scraped_groups"].append(result["group_name"])
        data["total_scraped"] = data.get("total_scraped", 0) + (result["dc1"] + result["dc3"] + result["dc5"])
        save_data(data)
        txt = f"{BTN_CHAR} Scraping Complete!\nGroup: `{result['group_name']}`\nTotal processed: `{result['total']}`\nAdded:\n{BTN_CHAR} DC1: `{result['dc1']}`\n{BTN_CHAR} DC3: `{result['dc3']}`\n{BTN_CHAR} DC5: `{result['dc5']}`"
        try:
            await proc.edit_text(txt)
        except:
            await message.reply_text(txt)
        if result['dc1'] + result['dc3'] + result['dc5'] > 0:
            await message.reply_text(f"{BTN_CHAR} Database updated.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Admin Panel", callback_data="admin_panel"), InlineKeyboardButton(f"{BTN_CHAR} Main Menu", callback_data="back_to_menu")]]))
    else:
        try:
            await proc.edit_text(f"{BTN_CHAR} Error scraping: {result.get('error')}")
        except:
            await message.reply_text(f"{BTN_CHAR} Error scraping: {result.get('error')}")


@Telegram.on_callback_query(filters.regex("admin_panel"))
async def admin_panel_cb(client: Client, callback_query: CallbackQuery):
    uid = callback_query.from_user.id
    if not is_admin(uid):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    data = load_data()
    dc1 = count_usernames_in_file(1)
    dc3 = count_usernames_in_file(3)
    dc5 = count_usernames_in_file(5)
    text = f"**{BTN_CHAR} Admin Panel**\n\n{BTN_CHAR} DC1: `{dc1}`\n{BTN_CHAR} DC3: `{dc3}`\n{BTN_CHAR} DC5: `{dc5}`\n{BTN_CHAR} Total scraped: `{data.get('total_scraped',0)}`"
    buttons = [
        [InlineKeyboardButton(f"{BTN_CHAR} Scrape Members", callback_data="scrape_members")],
        [InlineKeyboardButton(f"{BTN_CHAR} Check Database", callback_data="check_database")],
        [InlineKeyboardButton(f"{BTN_CHAR} Clear Database", callback_data="clear_database_confirm")],
        [InlineKeyboardButton(f"{BTN_CHAR} Export Database", callback_data="export_database")],
        [InlineKeyboardButton(f"{BTN_CHAR} Broadcast", callback_data="broadcast_menu")],
        [InlineKeyboardButton(f"{BTN_CHAR} Main Menu", callback_data="back_to_menu")]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()

@Telegram.on_callback_query(filters.regex("back_to_menu|refresh_menu"))
async def back_to_menu_cb(client: Client, callback_query: CallbackQuery):
    await show_main_menu(callback_query, callback_query.from_user.id)
    await callback_query.answer()


@Telegram.on_callback_query(filters.regex("help_user"))
async def help_user_cb(client: Client, callback_query: CallbackQuery):
    text = (
        f"**{BTN_CHAR} How to use this bot (quick):**\n\n"
        f"{BTN_CHAR} /start - open menu (join updates channel first)\n\n"
        f"{BTN_CHAR} Check My DC - shows your Telegram data center (DC1/DC3/DC5)\n\n"
        f"{BTN_CHAR} Bulk Check DCs - send up to 20 usernames (one per line). Bot will detect DC Cooldown: 7 minutes.\n\n"
        f"{BTN_CHAR} Get DC Users - will be saved DC1/DC3/DC5 usernames from DB (Get All or custom amount).\n\n"
        f"{BTN_CHAR} Scrape Members - (Premium only) scrape public groups With Auto DC Check\n\n"
        f"{BTN_CHAR} if something wrong, contact an admin ya zbi."
    )
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    await callback_query.answer()

@Telegram.on_message(filters.private & filters.command(["cancel"]))
async def cancel_cmd(client: Client, message: Message):
    uid = message.from_user.id
    user_states.pop(uid, None)
    user_states.pop(f"scrape_{uid}", None)
    user_states.pop(f"scrape_limit_{uid}", None)
    user_states.pop(f"custom_amount_{uid}", None)
    await message.reply_text(f"{BTN_CHAR} Operation cancelled!")

@Telegram.on_message(filters.private & filters.command(["myid"]))
async def myid_cmd(client: Client, message: Message):
    uid = message.from_user.id
    await message.reply_text(f"Your ID: `{uid}`\nAdmin: {'' if is_admin(uid) else ''}\nYour DC: DC{getattr(message.from_user, 'dc_id', 'N/A')}")

@Telegram.on_message(filters.private & filters.command(["stats"]))
async def stats_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text(f"{BTN_CHAR} Admin access required!")
        return
    data = load_data()
    lines = [f"{BTN_CHAR} Total processed: `{data.get('total_scraped',0)}`"]
    lines.append(f"{BTN_CHAR} DC1: `{count_usernames_in_file(1)}`")
    lines.append(f"{BTN_CHAR} DC3: `{count_usernames_in_file(3)}`")
    lines.append(f"{BTN_CHAR} DC5: `{count_usernames_in_file(5)}`")
    await message.reply_text("\n".join(lines))


async def handle_custom_amount(message: Message):
    uid = message.from_user.id
    dc_id = user_states.get(f"custom_amount_{uid}")
    if not dc_id:
        return
    user_states.pop(f"custom_amount_{uid}", None)
    try:
        amount = int(message.text.strip())
        max_amount = count_usernames_in_file(dc_id)
        if amount <= 0:
            await message.reply_text(f"{BTN_CHAR} Amount must be > 0")
            return
        if amount > max_amount:
            await message.reply_text(f"{BTN_CHAR} Only {max_amount} users available.")
            return
        users = get_usernames_from_file(dc_id, amount)
        if not users:
            await message.reply_text(f"{BTN_CHAR} No users available.")
            return
        text = "```\n" + "\n".join(users) + "\n```"
        await message.reply_text(f"{BTN_CHAR} DC{dc_id} Users ({amount}):\n{text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    except:
        await message.reply_text(f"{BTN_CHAR} Send a valid number")


async def check_user_dc(username: str):
    try:
        uname = username.replace("@","").strip()
        u = await Telegram.get_users(uname)
        return getattr(u, "dc_id", None)
    except Exception:
        return None


@Telegram.on_message(filters.private & filters.command(["add_premium"]))
async def cmd_add_premium(client: Client, message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text(f"{BTN_CHAR} Admin access required!")
        return
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.reply_text(f"{BTN_CHAR} Usage: /add_premium <user_id|@username> <days>")
        return
    target_raw = parts[1]
    try:
        days = int(parts[2])
    except:
        await message.reply_text(f"{BTN_CHAR} Invalid days value.")
        return
    
    try:
        if str(target_raw).startswith("@"):
            usr = await Telegram.get_users(target_raw)
            target = getattr(usr, "id", None)
            if not target:
                await message.reply_text(f"{BTN_CHAR} Could not resolve username.")
                return
        else:
            target = int(target_raw)
    except Exception:
        await message.reply_text(f"{BTN_CHAR} Could not resolve user. Use numeric id or @username.")
        return
    new_exp = add_premium_admin(target, days)
    await message.reply_text(f"{BTN_CHAR} Added premium for `{target}` for {days} days. Expires at {new_exp.isoformat()} UTC.")

@Telegram.on_message(filters.private & filters.command(["remove_premium"]))
async def cmd_remove_premium(client: Client, message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text(f"{BTN_CHAR} Admin access required!")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply_text(f"{BTN_CHAR} Usage: /remove_premium <user_id|@username>")
        return
    target_raw = parts[1]
    try:
        if str(target_raw).startswith("@"):
            usr = await Telegram.get_users(target_raw)
            target = getattr(usr, "id", None)
            if not target:
                await message.reply_text(f"{BTN_CHAR} Could not resolve username.")
                return
        else:
            target = int(target_raw)
    except Exception:
        await message.reply_text(f"{BTN_CHAR} Could not resolve user.")
        return
    ok = remove_premium_admin(target)
    if ok:
        await message.reply_text(f"{BTN_CHAR} Removed premium for `{target}`.")
    else:
        await message.reply_text(f"{BTN_CHAR} User `{target}` had no premium record.")

@Telegram.on_message(filters.private & filters.command(["premium_info"]))
async def cmd_premium_info(client: Client, message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text(f"{BTN_CHAR} Admin access required!")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply_text(f"{BTN_CHAR} Usage: /premium_info <user_id|@username>")
        return
    target_raw = parts[1]
    try:
        if str(target_raw).startswith("@"):
            usr = await Telegram.get_users(target_raw)
            target = getattr(usr, "id", None)
            if not target:
                await message.reply_text(f"{BTN_CHAR} Could not resolve username.")
                return
        else:
            target = int(target_raw)
    except Exception:
        await message.reply_text(f"{BTN_CHAR} Could not resolve user.")
        return
    exp = get_premium_info(target)
    if exp:
        await message.reply_text(f"{BTN_CHAR} Premium for `{target}` expires at {exp.isoformat()} UTC.")
    else:
        await message.reply_text(f"{BTN_CHAR} User `{target}` has no active premium.")


@Telegram.on_callback_query(filters.regex("check_database"))
async def check_database_cb(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    data = load_data()
    text = f"{BTN_CHAR} DB summary\n{BTN_CHAR} Total scraped: `{data.get('total_scraped',0)}`\n{BTN_CHAR} DC1: `{count_usernames_in_file(1)}`\n{BTN_CHAR} DC3: `{count_usernames_in_file(3)}`\n{BTN_CHAR} DC5: `{count_usernames_in_file(5)}`"
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))
    await callback_query.answer()

@Telegram.on_callback_query(filters.regex("clear_database_confirm"))
async def clear_db_confirm_cb(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    buttons = [
        [InlineKeyboardButton(f"{BTN_CHAR} Yes, clear", callback_data="clear_database")],
        [InlineKeyboardButton(f"{BTN_CHAR} Cancel", callback_data="back_to_menu")]
    ]
    await callback_query.message.edit_text(f"{BTN_CHAR} Are you sure you want to clear DC files and reset stats?", reply_markup=InlineKeyboardMarkup(buttons))

@Telegram.on_callback_query(filters.regex("clear_database"))
async def clear_database_cb(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    for fn in (DC1_FILE, DC3_FILE, DC5_FILE, ALL_USERS_FILE):
        open(fn, "w").close()
    save_data({"scraped_groups": [], "total_scraped": 0})
    await callback_query.message.edit_text(f"{BTN_CHAR} Database cleared.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{BTN_CHAR} Back to Menu", callback_data="back_to_menu")]]))

@Telegram.on_callback_query(filters.regex("export_database"))
async def export_database_cb(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    files = []
    for fn in (DC1_FILE, DC3_FILE, DC5_FILE, ALL_USERS_FILE):
        if os.path.exists(fn):
            files.append(fn)
    if not files:
        await callback_query.answer(f"{BTN_CHAR} No files to export.", show_alert=True)
        return
    for f in files:
        try:
            await callback_query.message.reply_document(document=f)
        except Exception as e:
            print("export error", e)
    await callback_query.answer("Exported.")


@Telegram.on_callback_query(filters.regex("broadcast_menu"))
async def broadcast_menu_cb(client: Client, callback_query: CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer(f"{BTN_CHAR} Admin access required!", show_alert=True)
        return
    await callback_query.message.edit_text(f"{BTN_CHAR} Send the broadcast message now (text only).")
    user_states[f"broadcast_{callback_query.from_user.id}"] = "awaiting_broadcast"
    await callback_query.answer()

async def handle_broadcast_message(message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text(f"{BTN_CHAR} Admin access required!")
        return
    user_states.pop(f"broadcast_{uid}", None)
    text = message.text
    sent = 0
    failed = 0
    targets = set()
    if os.path.exists(ALL_USERS_FILE):
        with open(ALL_USERS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                uname = line.split()[0]
                targets.add(uname)
    for t in targets:
        try:
            await Telegram.send_message(t, text)
            sent += 1
            await asyncio.sleep(0.1)
        except:
            failed += 1
    await message.reply_text(f"{BTN_CHAR} Broadcast complete. Sent: {sent}, Failed: {failed}")


if __name__ == "__main__":
    print("Starting bot (fixed)...")
    ensure_files()
    if os.path.exists(SESSIONS_DIR):
        sess = [f for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")]
        print(f"Found {len(sess)} session(s) in {SESSIONS_DIR}")
    else:
        print(f"Sessions folder '{SESSIONS_DIR}' not found. Create it and add .session files.")
    Telegram.run()
    
    bot.enable_save_next_step_handlers(delay=2)

bot.load_next_step_handlers()

bot.infinity_polling()