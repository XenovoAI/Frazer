import requests

CRYPTOBOT_TOKEN = "518319:AAILdmIsPtzHhH4zMpAGU6wAhs5n7TOhbcT"

# Test 1: Get app info
print("Testing CryptoBot API...")
headers = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
}

try:
    response = requests.get("https://pay.crypt.bot/api/getMe", headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("\n✅ Token is valid!")
            print(f"App Name: {result['result'].get('name', 'N/A')}")
        else:
            print("\n❌ Token invalid or error")
            print(f"Error: {result}")
    else:
        print(f"\n❌ HTTP Error: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Exception: {e}")

# Test 2: Try creating a test invoice
print("\n\nTesting invoice creation...")
headers = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}
data = {
    "asset": "USDT",
    "amount": "1",
    "description": "Test payment"
}

try:
    response = requests.post("https://pay.crypt.bot/api/createInvoice", headers=headers, json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("\n✅ Invoice created successfully!")
            print(f"Invoice ID: {result['result'].get('invoice_id')}")
            print(f"Pay URL: {result['result'].get('pay_url')}")
        else:
            print("\n❌ Error creating invoice")
            print(f"Error: {result}")
    else:
        print(f"\n❌ HTTP Error: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Exception: {e}")
