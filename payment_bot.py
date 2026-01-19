import json
import time
import threading
import telebot
from telebot import types
import requests

# Configuration
TELEGRAM_BOT_TOKEN = "8562600911:AAH2p50mCl1v3ea7N9RMR-yS3Ig2N81sXxE"
CRYPTOBOT_TOKEN = "518319:AAILdmIsPtzHhH4zMpAGU6wAhs5n7TOhbcT"
ADMIN_ID = 6369434417

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# File storage
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
    keyboard.add(types.KeyboardButton("💳 Buy Premium"))
    keyboard.add(types.KeyboardButton("👤 My Account"), types.KeyboardButton("ℹ️ Help"))
    return keyboard

def create_pricing_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("7 Days - $7", callback_data="buy_7"))
    keyboard.add(types.InlineKeyboardButton("30 Days - $20", callback_data="buy_30"))
    keyboard.add(types.InlineKeyboardButton("« Back", callback_data="back_main"))
    return keyboard

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Save user info
    users = load_json(USERS_FILE)
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username,
            "first_seen": time.time(),
            "premium": False,
            "premium_until": 0
        }
        save_json(USERS_FILE, users)
    
    bot.send_message(
        message.chat.id,
        f"👋 Welcome {message.from_user.first_name}!\n\n"
        "This is a payment gateway demo bot.\n"
        "You can purchase premium access using crypto payments.\n\n"
        "Choose an option below:",
        reply_markup=create_main_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "💳 Buy Premium")
def buy_premium_handler(message):
    bot.send_message(
        message.chat.id,
        "💎 Premium Plans\n\n"
        "Choose your subscription period:",
        reply_markup=create_pricing_keyboard()
    )

@bot.message_handler(func=lambda message: message.text == "👤 My Account")
def my_account_handler(message):
    user_id = message.from_user.id
    users = load_json(USERS_FILE)
    user_data = users.get(str(user_id), {})
    
    premium = user_data.get("premium", False)
    premium_until = user_data.get("premium_until", 0)
    
    if premium and premium_until > time.time():
        expiry = time.strftime('%d.%m.%Y %H:%M', time.localtime(premium_until))
        status = f"✅ Active until {expiry}"
    else:
        status = "❌ Not Active"
    
    bot.send_message(
        message.chat.id,
        f"👤 Your Account\n\n"
        f"User ID: `{user_id}`\n"
        f"Username: @{user_data.get('username', 'Unknown')}\n"
        f"Premium Status: {status}",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "ℹ️ Help")
def help_handler(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ Help\n\n"
        "💳 Buy Premium - Purchase premium access\n"
        "👤 My Account - View your account details\n"
        "ℹ️ Help - Show this message\n\n"
        "Payment is processed via CryptoBot (USDT)\n"
        "After payment, premium is activated automatically."
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_purchase(call):
    user_id = call.from_user.id
    
    days_map = {
        "buy_7": (7, 7),
        "buy_30": (30, 20)
    }
    
    days, price = days_map.get(call.data, (1, 1))
    
    success, invoice = cryptobot.create_invoice(
        amount=price,
        description=f"Premium Subscription - {days} days"
    )
    
    if success:
        payments = load_json(PAYMENTS_FILE)
        invoice_id = invoice["invoice_id"]
        payments[str(invoice_id)] = {
            "user_id": user_id,
            "days": days,
            "amount": price,
            "status": "pending",
            "created_at": time.time()
        }
        save_json(PAYMENTS_FILE, payments)
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("💳 Pay Now", url=invoice['pay_url']))
        keyboard.add(types.InlineKeyboardButton("« Back", callback_data="back_main"))
        
        bot.send_message(
            call.message.chat.id,
            f"💳 Payment Invoice\n\n"
            f"Plan: {days} days\n"
            f"Amount: ${price} USDT\n\n"
            f"Click the button below to complete payment.\n"
            f"Premium will be activated automatically after payment.",
            reply_markup=keyboard
        )
    else:
        error_msg = str(invoice)[:200]  # Limit error message length
        bot.send_message(
            call.message.chat.id,
            f"❌ Error creating invoice. Please contact admin."
        )
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_main(call):
    bot.edit_message_text(
        "Choose an option:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=create_pricing_keyboard()
    )
    bot.answer_callback_query(call.id)

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
                                
                                # Activate premium
                                users = load_json(USERS_FILE)
                                current_time = time.time()
                                end_time = current_time + (days * 24 * 60 * 60)
                                
                                if str(user_id) not in users:
                                    users[str(user_id)] = {}
                                
                                users[str(user_id)]["premium"] = True
                                users[str(user_id)]["premium_until"] = end_time
                                save_json(USERS_FILE, users)
                                
                                # Update payment status
                                payments[invoice_id]["status"] = "paid"
                                payments[invoice_id]["paid_at"] = current_time
                                save_json(PAYMENTS_FILE, payments)
                                
                                # Notify user
                                try:
                                    bot.send_message(
                                        user_id,
                                        f"✅ Payment Successful!\n\n"
                                        f"Premium activated for {days} days\n"
                                        f"Valid until: {time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))}"
                                    )
                                except Exception as e:
                                    print(f"Error notifying user: {e}")
                                
                                # Notify admin
                                try:
                                    bot.send_message(
                                        ADMIN_ID,
                                        f"💰 New Payment\n\n"
                                        f"User: {user_id}\n"
                                        f"Amount: ${payment_data['amount']}\n"
                                        f"Days: {days}"
                                    )
                                except:
                                    pass
            
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            print(f"Error in check_payments: {e}")
            time.sleep(60)

# Admin commands
@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    users = load_json(USERS_FILE)
    payments = load_json(PAYMENTS_FILE)
    
    total_users = len(users)
    premium_users = sum(1 for u in users.values() 
                       if u.get("premium") and u.get("premium_until", 0) > time.time())
    total_revenue = sum(p["amount"] for p in payments.values() if p["status"] == "paid")
    
    bot.send_message(
        message.chat.id,
        f"📊 Bot Statistics\n\n"
        f"Total Users: {total_users}\n"
        f"Premium Users: {premium_users}\n"
        f"Total Revenue: ${total_revenue}\n"
        f"Total Payments: {len(payments)}"
    )

@bot.message_handler(commands=['give_premium'])
def admin_give_premium(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        days = int(parts[2])
        
        users = load_json(USERS_FILE)
        current_time = time.time()
        end_time = current_time + (days * 24 * 60 * 60)
        
        if str(user_id) not in users:
            users[str(user_id)] = {}
        
        users[str(user_id)]["premium"] = True
        users[str(user_id)]["premium_until"] = end_time
        save_json(USERS_FILE, users)
        
        bot.send_message(message.chat.id, f"✅ Premium given to {user_id} for {days} days")
        
        try:
            bot.send_message(
                user_id,
                f"🎁 You've been given premium access for {days} days!\n"
                f"Valid until: {time.strftime('%d.%m.%Y %H:%M', time.localtime(end_time))}"
            )
        except:
            pass
            
    except:
        bot.send_message(message.chat.id, "Usage: /give_premium <user_id> <days>")

if __name__ == "__main__":
    print("🚀 Payment Bot Started")
    
    # Start payment checker thread
    payment_thread = threading.Thread(target=check_payments, daemon=True)
    payment_thread.start()
    
    # Start bot
    bot.infinity_polling()
