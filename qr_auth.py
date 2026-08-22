import asyncio
from telethon import TelegramClient
import qrcode

API_ID = 37460790
API_HASH = "4473d7e19ab42ced7ff0ff02e3817b8f"
PASSWORD = "2010"  # 2FA parolingiz

async def main():
    client = TelegramClient("dealer_userbot_session", API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        qr = await client.qr_login()
        print("\n--- TELEGRAM QR KODI ---")
        
        qr_code = qrcode.QRCode()
        qr_code.add_data(qr.url)
        qr_code.print_ascii(invert=True)
        
        print("\nTelefoningizdagi Telegram orqali yuqoridagi QR-kodni skanerlang!")
        
        try:
            # QR kod skanerlanishini kutamiz
            await qr.wait(timeout=300)
        except Exception as e:
            print(f"\nXatolik: {e}")
            return

    # Agar 2FA parol talab qilinsa, kod orqali kiritamiz
    if not await client.is_user_authorized():
        try:
            await client.sign_in(password=PASSWORD)
        except Exception as e:
            print(f"Parolni kiritishda xatolik: {e}")
            return
        
    print("\nMuvaffaqiyatli ulandi va sessiya yaratildi!")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())