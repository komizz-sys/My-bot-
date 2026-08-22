from telethon import TelegramClient

api_id = 37460790
api_hash = "4473d7e19ab42ced7ff0ff02e3817b8f"

# Skriptni iPhone 15 Pro Max kabi ko'rsatamiz
client = TelegramClient(
    'dealer_userbot_session', 
    api_id, 
    api_hash,
    device_model="iPhone 15 Pro Max",
    system_version="iOS 17.5",
    app_version="10.14.1"
)

async def main():
    await client.connect()
    phone = input("Telefon raqamingizni kiriting (+998...): ")
    await client.send_code_request(phone)
    code = input("Telegramdan kelgan kodni kiriting: ")
    await client.sign_in(phone, code)
    print("Sessiya muvaffaqiyatli yaratildi!")

with client:
    client.loop.run_until_complete(main())
