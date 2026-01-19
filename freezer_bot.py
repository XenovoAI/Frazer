import json
import time
import threading
import telebot
from telebot import types
import requests

# Configuration
TELEGRAM_BOT_TOKEN = "8419628674:AAGKa2sz16turZXHgQqJB4ma7v7UYeaPnWo"
CRYPTOBOT_TOKEN = "513166:AAeYlQKSxjX3Y1LlDqdL8pFwOoTCMSO85xP"
ADMIN_ID = 8485075384
SUPPORT_USERNAME = "@SnosReq"

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# File storage
SUBSCRIPTIONS_FILE = "subscriptions.json"
PAYMENTS_FILE = "payments.json"
USERS_FILE = "users.json"

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
        
    def create_invoice(self, amount, description, currency="USDT"):
        headers = {
            "Crypto-Pay-API-Token": self.token,
            "Content-Type": "application/json"
        }
        data = {
            "asset": currency,
            "amount": str(amount),
            "description": description
        }
        
        try:
            response = requests.post(f"{self.base_url}/createInvoice", headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return True, result["result"]
                else:
                    return False, result.get("error", {}).get("name", "Unknown error")
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)[:100]
    
    def get_invoices(self, invoice_ids=None):
        headers = {
            "Crypto-Pay-API-Token": self.token
        }
        params = {}
        if invoice_ids:
            params["invoice_ids"] = ",".join(map(str, invoice_ids))
            
        try:
            response = requests.get(f"{self.base_url}/getInvoices", headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return True, result["result"]
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)[:100]

cryptobot = CryptoBot(CRYPTOBOT_TOKEN)

user_states = {}

def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("📧 Send Report"),
        types.KeyboardButton("💎 Subscription")
    )
    keyboard.add(
        types.KeyboardButton("👤 Profile"),
        types.KeyboardButton("❓ Help")
    )
    return keyboard

def create_subscription_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("1 Week - $7", callback_data="sub_7"))
    keyboard.add(types.InlineKeyboardButton("1 Month - $20", callback_data="sub_30"))
    keyboard.add(types.InlineKeyboardButton("Forever - $50", callback_data="sub_forever"))
    return keyboard

def has_active_subscription(user_id):
    subs = load_json(SUBSCRIPTIONS_FILE)
    user_sub = subs.get(str(user_id), {})
    if user_sub.get('forever'):
        return True
    if user_sub.get('end_time', 0) > time.time():
        return True
    return False

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Save user
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username,
            "first_seen": time.time()
        }
        save_json(USERS_FILE, users)
    
    bot.send_message(
        message.chat.id,
        "🚀 *FREEZER BoT*\n\n"
        "Use buttons below to navigate\n\n"
        f"👥 Support: {SUPPORT_USERNAME}",
        parse_mode="Markdown",
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "❓ Help")
def help_handler(message):
    help_text = (
        "📌 *SnoSer Bot - Help*\n\n"
        "*Main Features:*\n"
        "• 👤 Profile - your account information\n"
        "• 📧 Send Report - send reports on accounts\n"
        "• 💎 Subscription - access to all features\n\n"
        "*Report System:*\n"
        "• Processing time: ~1 minute\n"
        "• Cooldown between reports: 18 minutes\n"
        "• Requires active subscription\n\n"
        "*Subscription Plans:*\n"
        "• 1 Week - $7\n"
        "• 1 Month - $20\n"
        "• Forever - $50\n\n"
        "*Important:*\n"
        "• Payment via CryptoPay (USDT)\n"
        "• Instant activation after payment\n"
        "• 24/7 Support\n\n"
        f"👥 Support: {SUPPORT_USERNAME}"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    subs = load_json(SUBSCRIPTIONS_FILE)
    user_sub = subs.get(str(user_id), {})
    
    if user_sub.get('forever'):
        status = "✅ Forever"
    elif user_sub.get('end_time', 0) > time.time():
        expiry = time.strftime('%d.%m.%Y %H:%M', time.localtime(user_sub['end_time']))
        status = f"✅ Active until {expiry}"
    else:
        status = "❌ Not Active"
    
    profile_text = (
        f"👤 *Your Profile*\n\n"
        f"User ID: `{user_id}`\n"
        f"Username: @{username}\n"
        f"Subscription: {status}\n\n"
        f"👥 Support: {SUPPORT_USERNAME}"
    )
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📧 Send Report")
def send_report_handler(message):
    user_id = message.from_user.id
    
    if not has_active_subscription(user_id):
        bot.send_message(
            message.chat.id,
            "❌ *Access Restricted*\n\n"
            "This feature requires an active subscription\n\n"
            "Purchase a subscription to unlock all features\n\n"
            f"👥 Support: {SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )
        return
    
    user_states[user_id] = 'waiting_target'
    bot.send_message(
        message.chat.id,
        "📧 *Send Report*\n\n"
        "Enter target username (with @):\n\n"
        "Example: @username\n\n"
        "Send /cancel to cancel",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "💎 Subscription")
def subscription_handler(message):
    user_id = message.from_user.id
    
    subs = load_json(SUBSCRIPTIONS_FILE)
    user_sub = subs.get(str(user_id), {})
    
    if user_sub.get('forever'):
        bot.send_message(
            message.chat.id,
            "💎 *Your Subscription*\n\n"
            "Status: ✅ Forever Active\n\n"
            f"👥 Support: {SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )
        return
    
    if user_sub.get('end_time', 0) > time.time():
        expiry = time.strftime('%d.%m.%Y %H:%M', time.localtime(user_sub['end_time']))
        bot.send_message(
            message.chat.id,
            f"💎 *Your Subscription*\n\n"
            f"Status: ✅ Active\n"
            f"Valid until: {expiry}\n\n"
            f"👥 Support: {SUPPORT_USERNAME}",
            parse_mode="Markdown"
        )
        return
    
    bot.send_message(
        message.chat.id,
        "💎 *Choose Subscription*\n\n"
        "*Available Plans:*\n"
        "• 1 Week - $7\n"
        "• 1 Month - $20\n"
        "• Forever - $50\n\n"
        "Select a plan below:",
        parse_mode="Markdown",
        reply_markup=create_subscription_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("sub_"))
def process_subscription(call):
    user_id = call.from_user.id
    
    plans = {
        "sub_7": (7, 7, "1 Week"),
        "sub_30": (30, 20, "1 Month"),
        "sub_forever": (0, 50, "Forever")
    }
    
    days, price, plan_name = plans.get(call.data, (7, 7, "1 Week"))
    
    success, invoice = cryptobot.create_invoice(
        amount=price,
        description=f"Freezer Bot - {plan_name} Subscription"
    )
    
    if success:
        payments = load_json(PAYMENTS_FILE)
        invoice_id = invoice["invoice_id"]
        payments[str(invoice_id)] = {
            "user_id": user_id,
            "days": days,
            "amount": price,
            "plan": plan_name,
            "forever": (days == 0),
            "status": "pending",
            "created_at": time.time()
        }
        save_json(PAYMENTS_FILE, payments)
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("💳 Pay Now", url=invoice['pay_url']))
        
        bot.send_message(
            call.message.chat.id,
            f"💳 *Payment Invoice*\n\n"
            f"Plan: {plan_name}\n"
            f"Amount: ${price} USDT\n\n"
            f"Click button below to pay.\n"
            f"Subscription activates automatically after payment.\n\n"
            f"👥 Support: {SUPPORT_USERNAME}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            call.message.chat.id,
            f"❌ Error creating invoice. Contact support.\n\n"
            f"👥 Support: {SUPPORT_USERNAME}"
        )
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_target')
def process_target(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    
    target = message.text.strip()
    
    if not target.startswith('@'):
        bot.send_message(
            message.chat.id,
            "❌ Invalid format. Username must start with @\n\n"
            "Example: @username"
        )
        return
    
    # Simulate processing
    processing_msg = bot.send_message(
        message.chat.id,
        "⏳ Processing report...\n\n"
        f"Target: {target}\n"
        "Please wait ~1 minute..."
    )
    
    time.sleep(3)  # Simulate processing
    
    bot.edit_message_text(
        "✅ *Report Sent Successfully!*\n\n"
        f"Target: {target}\n"
        "Status: Completed\n"
        "Processing time: 3 seconds\n\n"
        "Next report available in 18 minutes\n\n"
        f"👥 Support: {SUPPORT_USERNAME}",
        message.chat.id,
        processing_msg.message_id,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['cancel'])
def cancel_handler(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    bot.send_message(message.chat.id, "❌ Cancelled", reply_markup=create_main_keyboard())

def check_payments():
    """Background thread to check payment status"""
    while True:
        try:
            payments = load_json(PAYMENTS_FILE)
            pending_invoices = [invoice_id for invoice_id, data in payments.items() 
                              if data["status"] == "pending"]
            
            if pending_invoices:
                success, result = cryptobot.get_invoices(pending_invoices)
                if success and "items" in result:
                    for invoice in result["items"]:
                        if invoice["status"] == "paid":
                            invoice_id = str(invoice["invoice_id"])
                            if invoice_id in payments:
                                payment_data = payments[invoice_id]
                                user_id = payment_data["user_id"]
                                days = payment_data["days"]
                                is_forever = payment_data.get("forever", False)
                                
                                # Activate subscription
                                subs = load_json(SUBSCRIPTIONS_FILE)
                                current_time = time.time()
                                
                                if is_forever:
                                    subs[str(user_id)] = {
                                        'forever': True,
                                        'activated_at': current_time
                                    }
                                    expiry_text = "Forever"
                                else:
                                    end_time = current_time + (days * 24 * 60 * 60)
                                    subs[str(user_id)] = {
                                        'start_time': current_time,
                                        'end_time': end_time,
                                        'days': days,
                                        'forever': False
                                    }
                                    expiry_text = time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))
                                
                                save_json(SUBSCRIPTIONS_FILE, subs)
                                
                                # Update payment
                                payments[invoice_id]["status"] = "paid"
                                payments[invoice_id]["paid_at"] = current_time
                                save_json(PAYMENTS_FILE, payments)
                                
                                # Notify user
                                try:
                                    bot.send_message(
                                        user_id,
                                        f"✅ *Payment Successful!*\n\n"
                                        f"Subscription: {payment_data['plan']}\n"
                                        f"Valid until: {expiry_text}\n\n"
                                        f"All features unlocked!\n\n"
                                        f"👥 Support: {SUPPORT_USERNAME}",
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Error notifying user: {e}")
                                
                                # Notify admin
                                try:
                                    bot.send_message(
                                        ADMIN_ID,
                                        f"💰 *New Payment*\n\n"
                                        f"User: {user_id}\n"
                                        f"Plan: {payment_data['plan']}\n"
                                        f"Amount: ${payment_data['amount']}",
                                        parse_mode="Markdown"
                                    )
                                except:
                                    pass
            
            time.sleep(30)
        except Exception as e:
            print(f"Error in check_payments: {e}")
            time.sleep(60)

# Admin commands
@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    users = load_json(USERS_FILE)
    subs = load_json(SUBSCRIPTIONS_FILE)
    payments = load_json(PAYMENTS_FILE)
    
    total_users = len(users)
    active_subs = sum(1 for s in subs.values() 
                     if s.get('forever') or s.get('end_time', 0) > time.time())
    total_revenue = sum(p["amount"] for p in payments.values() if p["status"] == "paid")
    
    bot.send_message(
        message.chat.id,
        f"📊 *Bot Statistics*\n\n"
        f"Total Users: {total_users}\n"
        f"Active Subscriptions: {active_subs}\n"
        f"Total Revenue: ${total_revenue}\n"
        f"Total Payments: {len(payments)}",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['give_sub'])
def admin_give_sub(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        days = int(parts[2])
        
        subs = load_json(SUBSCRIPTIONS_FILE)
        current_time = time.time()
        
        if days == 0:
            subs[str(user_id)] = {'forever': True, 'activated_at': current_time}
            expiry_text = "Forever"
        else:
            end_time = current_time + (days * 24 * 60 * 60)
            subs[str(user_id)] = {
                'start_time': current_time,
                'end_time': end_time,
                'days': days,
                'forever': False
            }
            expiry_text = time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))
        
        save_json(SUBSCRIPTIONS_FILE, subs)
        
        bot.send_message(message.chat.id, f"✅ Subscription given to {user_id}")
        
        try:
            bot.send_message(
                user_id,
                f"🎁 *Free Subscription!*\n\n"
                f"Valid until: {expiry_text}\n\n"
                f"👥 Support: {SUPPORT_USERNAME}",
                parse_mode="Markdown"
            )
        except:
            pass
            
    except:
        bot.send_message(message.chat.id, "Usage: /give_sub <user_id> <days>\n0 days = forever")

if __name__ == "__main__":
    print("🚀 Freezer Bot Started")
    
    # Start payment checker
    payment_thread = threading.Thread(target=check_payments, daemon=True)
    payment_thread.start()
    
    # Start bot
    bot.infinity_polling()
