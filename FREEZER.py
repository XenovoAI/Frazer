import json
import time
import asyncio
import threading
import os
import glob
from telethon.sync import TelegramClient
from telethon.tl import functions
from telethon.tl.types import Channel, Chat, User
import telebot
from telebot import types
import requests

API_ID = 21826549
API_HASH = "c1a19f792cfd9e397200d16c7e448160"
TELEGRAM_BOT_TOKEN = "8283819120:"
CRYPTOBOT_TOKEN = "455489:"
ADMIN_ID = 11111111

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

SUBSCRIPTIONS_FILE = "subscriptions.json"
COOLDOWNS_FILE = "cooldowns.json"
PAYMENTS_FILE = "payments.json"

def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class CryptoBot:
    def __init__(self, token):
        self.token = token
        self.base_url = "https://pay.crypt.bot/api"
        
    def create_invoice(self, amount, description):
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }
        data = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description
        }
        
        try:
            response = requests.post(f"{self.base_url}/createInvoice", headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return True, result["result"]
            return False, response.text
        except Exception as e:
            return False, str(e)
    
    def get_invoices(self, invoice_ids=None):
        headers = {
            "Crypto-Pay-API-Token": self.token
        }
        params = {}
        if invoice_ids:
            params["invoice_ids"] = invoice_ids
            
        try:
            response = requests.get(f"{self.base_url}/getInvoices", headers=headers, params=params)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return True, result["result"]
            return False, response.text
        except Exception as e:
            return False, str(e)

cryptobot = CryptoBot(CRYPTOBOT_TOKEN)

def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Send"), types.KeyboardButton("Subscription"))
    return keyboard

def create_subscription_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("1 day - 1$", callback_data="sub_1"))
    keyboard.add(types.InlineKeyboardButton("7 days - 7$", callback_data="sub_7"))
    return keyboard

async def resolve_user(client, raw: str):
    raw = raw.strip()

    if raw.lstrip("-").isdigit():
        try:
            return await client.get_entity(int(raw))
        except:
            return None

    username = raw

    if "t.me/" in username:
        username = username.split("t.me/", 1)[1]

    username = username.split("/", 1)[0]

    if username.startswith("@"):
        username = username[1:]

    if not username:
        return None

    try:
        result = await client(functions.contacts.SearchRequest(q=username, limit=10))
    except:
        return None

    if not getattr(result, "users", None):
        return None

    for user in result.users:
        if getattr(user, "username", None) and user.username.lower() == username.lower():
            return user

    return result.users[0] if result.users else None

ban_lock = threading.Lock()

def get_session_files():
    session_files = glob.glob("sessions/*.session")
    return session_files

def send_ban_requests(username, user_id):
    if not ban_lock.acquire(blocking=False):
        return False, "Someone else is sending requests right now, please try again later", None
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def runner():
            try:
                session_files = get_session_files()
                if not session_files:
                    return False, "No sessions found in the sessions folder", None

                BANNED_RIGHTS = {
                    "view_messages": False,
                    "send_messages": False,
                    "send_media": False,
                    "send_stickers": False,
                    "send_gifs": False,
                    "send_games": False,
                    "send_inline": False,
                    "send_polls": False,
                    "change_info": False,
                    "invite_users": False,
                }

                counter = 0
                errors = []

                for session_file in session_files:
                    try:
                        session_name = os.path.splitext(os.path.basename(session_file))[0]
                        async with TelegramClient(f"sessions/{session_name}", API_ID, API_HASH) as client:
                            target_user = await resolve_user(client, username)
                            if not target_user:
                                continue

                            chats = []
                            async for dialog in client.iter_dialogs():
                                entity = dialog.entity
                                if (
                                    isinstance(entity, (Chat, Channel)) and
                                    getattr(entity, "admin_rights", None) and
                                    getattr(entity.admin_rights, "ban_users", False)
                                ):
                                    chats.append(entity.id)

                            for chat_id in chats:
                                try:
                                    await client.edit_permissions(
                                        chat_id,
                                        target_user,
                                        until_date=None,
                                        **BANNED_RIGHTS
                                    )
                                    counter += 1
                                    await asyncio.sleep(0.2)
                                except Exception as e:
                                    err = str(e).lower()
                                    if "database is locked" in err:
                                        break
                                    errors.append(err)
                                    continue

                    except Exception as e:
                        err = str(e).lower()
                        if "database is locked" in err:
                            continue
                        print(f"Error connecting {session_file}: {e}")
                        continue

                target_info = f"{username}"
                return True, counter, target_info
            
            except Exception as e:
                err = str(e).lower()
                if "database is locked" in err:
                    return False, "Someone else is sending requests right now, please try again later", None
                return False, f"Error: {str(e)}", None

        result = loop.run_until_complete(runner())
        loop.close()
        return result

    except Exception as e:
        return False, f"Error: {str(e)}", None
    finally:
        ban_lock.release()

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "Welcome",
        reply_markup=create_main_keyboard()
    )

user_states = {}

@bot.message_handler(func=lambda message: message.text == "Send")
def send_handler(message):
    user_id = message.from_user.id
    
    subscriptions = load_json(SUBSCRIPTIONS_FILE)
    user_sub = subscriptions.get(str(user_id), {})
    if not user_sub or user_sub.get('end_time', 0) < time.time():
        bot.send_message(message.chat.id, "You don't have an active subscription")
        return
    
    cooldowns = load_json(COOLDOWNS_FILE)
    if str(user_id) in cooldowns:
        bot.send_message(message.chat.id, "You have an active cooldown")
        return
    
    user_states[user_id] = 'waiting_username'
    bot.send_message(message.chat.id, "Enter @username:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == 'waiting_username')
def process_username(message):
    user_id = message.from_user.id
    username = message.text.strip()
    
    if not username.startswith('@'):
        bot.send_message(message.chat.id, "Enter username in format @username")
        if user_id in user_states:
            del user_states[user_id]
        return

    if user_id in user_states:
        del user_states[user_id]

    processing_msg = bot.send_message(message.chat.id, "Sending requests... This may take a few minutes")
    
    try:
        success, result, target_info = send_ban_requests(username, user_id)
        
        if success:
            if isinstance(result, int) and result > 0:
                bot.edit_message_text(
                    f"Requests sent: {result}",
                    message.chat.id,
                    processing_msg.message_id
                )
                
                cooldowns = load_json(COOLDOWNS_FILE)
                cooldowns[str(user_id)] = True
                save_json(COOLDOWNS_FILE, cooldowns)

            else:
                bot.edit_message_text(
                    f"Telegram restricted the session for sending, please try again later",
                    message.chat.id,
                    processing_msg.message_id
                )
        else:
            bot.edit_message_text(
                f"{result}",
                message.chat.id,
                processing_msg.message_id
            )
        
    except Exception as e:
        print(f"Error in process_username: {e}")
        bot.edit_message_text(
            f"An error occurred, please try again.",
            message.chat.id,
            processing_msg.message_id
        )

@bot.message_handler(func=lambda message: message.text == "Subscription")
def subscription_handler(message):
    user_id = message.from_user.id
    
    subscriptions = load_json(SUBSCRIPTIONS_FILE)
    user_sub = subscriptions.get(str(user_id), {})
    
    if user_sub and user_sub.get('end_time', 0) > time.time():
        end_time = time.strftime('%d.%m.%Y %H:%M', time.localtime(user_sub['end_time']))
        bot.send_message(
            message.chat.id,
            f"You have an active subscription until {end_time}"
        )
    else:
        bot.send_message(
            message.chat.id,
            "Choose subscription period:",
            reply_markup=create_subscription_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("sub_"))
def process_subscription(call):
    user_id = call.from_user.id
    
    days = int(call.data.split("_")[1])
    price = days
    
    success, invoice = cryptobot.create_invoice(
        amount=price,
        description=f"Subscription for {days} days"
    )
    
    if success:
        payments = load_json(PAYMENTS_FILE)
        invoice_id = invoice["invoice_id"]
        payments[invoice_id] = {
            "user_id": user_id,
            "days": days,
            "amount": price,
            "status": "pending",
            "created_at": time.time()
        }
        save_json(PAYMENTS_FILE, payments)
        
        bot.send_message(
            call.message.chat.id,
            f"Pay {price}$ for {days} days\n"
            f"Payment link: {invoice['pay_url']}\n\n"
            "After payment, the subscription will be activated automatically within 1-2 minutes"
        )
    else:
        bot.send_message(
            call.message.chat.id,
            f"Error creating invoice: {invoice}"
        )
    bot.answer_callback_query(call.id)

def check_payments():
    while True:
        try:
            payments = load_json(PAYMENTS_FILE)
            pending_invoices = [invoice_id for invoice_id, data in payments.items() if data["status"] == "pending"]
            
            if pending_invoices:
                success, result = cryptobot.get_invoices(pending_invoices)
                if success:
                    for invoice in result["items"]:
                        if invoice["status"] == "paid":
                            invoice_id = str(invoice["invoice_id"])
                            if invoice_id in payments:
                                payment_data = payments[invoice_id]
                                user_id = payment_data["user_id"]
                                days = payment_data["days"]
                                
                                subscriptions = load_json(SUBSCRIPTIONS_FILE)
                                current_time = time.time()
                                end_time = current_time + (days * 24 * 60 * 60)
                                
                                subscriptions[str(user_id)] = {
                                    'start_time': current_time,
                                    'end_time': end_time,
                                    'days': days,
                                    'invoice_id': invoice_id
                                }
                                save_json(SUBSCRIPTIONS_FILE, subscriptions)
                                
                                payments[invoice_id]["status"] = "paid"
                                payments[invoice_id]["paid_at"] = current_time
                                save_json(PAYMENTS_FILE, payments)
                                
                                try:
                                    bot.send_message(
                                        user_id,
                                        f"Subscription activated for {days} days!\n"
                                        f"Valid until {time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))}"
                                    )
                                except Exception as e:
                                    print(f"Error sending to user: {e}")
            
            time.sleep(30)
        except Exception as e:
            print(f"Error in check_payments: {e}")
            time.sleep(60)

@bot.message_handler(commands=['cd'])
def admin_cd(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        cooldowns = load_json(COOLDOWNS_FILE)
        
        if str(user_id) in cooldowns:
            del cooldowns[str(user_id)]
            save_json(COOLDOWNS_FILE, cooldowns)
            bot.send_message(message.chat.id, f"Cooldown removed for user {user_id}")
        else:
            cooldowns[str(user_id)] = True
            save_json(COOLDOWNS_FILE, cooldowns)
            bot.send_message(message.chat.id, f"Cooldown set for user {user_id}")
    except:
        bot.send_message(message.chat.id, "Usage: /cd user_id")

@bot.message_handler(commands=['sub'])
def admin_sub(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        days = int(parts[2])
        
        subscriptions = load_json(SUBSCRIPTIONS_FILE)
        current_time = time.time()
        end_time = current_time + (days * 24 * 60 * 60)
        
        subscriptions[str(user_id)] = {
            'start_time': current_time,
            'end_time': end_time,
            'days': days,
            'admin_added': True
        }
        save_json(SUBSCRIPTIONS_FILE, subscriptions)
        
        bot.send_message(message.chat.id, f"Subscription for {days} days given to user {user_id}")
        
        try:
            bot.send_message(
                user_id,
                f"You have been given a subscription for {days} days!\n"
                f"Valid until {time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))}"
            )
        except:
            pass
            
    except:
        bot.send_message(message.chat.id, "Usage: /sub user_id days")

@bot.message_handler(commands=['unsub'])
def admin_unsub(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        user_id = int(message.text.split()[1])
        subscriptions = load_json(SUBSCRIPTIONS_FILE)
        if str(user_id) in subscriptions:
            del subscriptions[str(user_id)]
            save_json(SUBSCRIPTIONS_FILE, subscriptions)
        bot.send_message(message.chat.id, f"Subscription for user {user_id} removed")
    except:
        bot.send_message(message.chat.id, "Usage: /unsub user_id")

payment_thread = threading.Thread(target=check_payments, daemon=True)
payment_thread.start()

if __name__ == "__main__":
    print("Bot started")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot error: {e}")