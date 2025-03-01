import os
import asyncio
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot Configuration
API_ID = os.getenv("API_ID", "15614019")
API_HASH = os.getenv("API_HASH", "ec984c96669207f5b7bca307b3f836f2")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8019349052:AAGaV6JpQl3s8VReBtIyaJiFPARSmxe2g8M")

# Initialize Client
try:
    app = Client("photo_edit_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=8)
except Exception as e:
    logger.error(f"Failed to initialize client: {e}")
    exit(1)

# Thread pool for CPU-intensive tasks
executor = ThreadPoolExecutor(max_workers=4)

# Image Processing Functions
async def enhance_4k(image_path):
    img = cv2.imread(image_path)
    upscaled = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    upscaled = cv2.filter2D(upscaled, -1, kernel)
    enhanced_path = f"enhanced_{int(time.time())}.jpg"
    cv2.imwrite(enhanced_path, upscaled, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return enhanced_path

async def professional_edit(image_path):
    img = Image.open(image_path).convert('RGB')
    img = ImageEnhance.Color(img).enhance(1.15)
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    edited_path = f"pro_{int(time.time())}.jpg"
    img.save(edited_path, quality=95, optimize=True)
    return edited_path

# Bot Commands
@app.on_message(filters.command("start"))
async def start(client, message):
    welcome_text = (
        "Welcome to Pro Photo Editor Bot! 🎨\n"
        "Send a photo and choose an edit option!"
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.photo)
async def handle_photo(client, message):
    buttons = [
        [InlineKeyboardButton("4K Enhance ✨", callback_data="enhance"),
         InlineKeyboardButton("Pro Edit 🎨", callback_data="edit")],
        [InlineKeyboardButton("Cancel ❌", callback_data="cancel")]
    ]
    await message.reply_photo(
        photo=message.photo.file_id,
        caption="Select an editing option:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def process_image(client, callback_query, mode):
    try:
        await callback_query.answer()
        status_msg = await callback_query.message.reply_text("Processing...")

        photo = callback_query.message.reply_to_message.photo
        image_path = await client.download_media(photo.file_id)

        if mode == "enhance":
            result_path = await enhance_4k(image_path)
        elif mode == "edit":
            result_path = await professional_edit(image_path)

        await callback_query.message.reply_photo(
            photo=result_path,
            caption="Done! 🎉"
        )
        await status_msg.delete()

        os.remove(image_path)
        os.remove(result_path)
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        await callback_query.message.reply_text("An error occurred.")

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    if data == "enhance":
        await process_image(client, callback_query, "enhance")
    elif data == "edit":
        await process_image(client, callback_query, "edit")
    elif data == "cancel":
        await callback_query.message.delete()

# Run Bot
async def main():
    try:
        await app.start()
        logger.info("Bot started successfully")
        await asyncio.Future()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await app.stop()
        executor.shutdown()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
