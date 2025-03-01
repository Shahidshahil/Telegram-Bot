import os
import asyncio
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import logging
import time
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot Configuration
API_ID = os.getenv("API_ID", "15614019")
API_HASH = os.getenv("API_HASH", "ec984c96669207f5b7bca307b3f836f2")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8019349052:AAGaV6JpQl3s8VReBtIyaJiFPARSmxe2g8M")
ADMIN_GROUP_ID = -1002407228775  # Group for before/after forwarding

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
    scale_factor = 4
    upscaled = cv2.resize(img, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_LANCZOS4)
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
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
    img = img.filter(ImageFilter.MedianFilter(size=3))
    edited_path = f"pro_{int(time.time())}.jpg"
    img.save(edited_path, quality=95, optimize=True)
    return edited_path

async def vivid_colors(image_path):
    img = Image.open(image_path).convert('RGB')
    img = ImageEnhance.Color(img).enhance(1.4)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    vivid_path = f"vivid_{int(time.time())}.jpg"
    img.save(vivid_path, quality=95)
    return vivid_path

async def artistic_filter(image_path, style="cartoon"):
    img = cv2.imread(image_path)
    if style == "cartoon":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                    cv2.THRESH_BINARY, 9, 9)
        color = cv2.bilateralFilter(img, 9, 300, 300)
        cartoon = cv2.bitwise_and(color, color, mask=edges)
        result_path = f"cartoon_{int(time.time())}.jpg"
        cv2.imwrite(result_path, cartoon)
    elif style == "sketch":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        inv = cv2.bitwise_not(gray)
        sketch = cv2.GaussianBlur(inv, (21, 21), 0)
        sketch = cv2.bitwise_not(sketch)
        sketch = cv2.divide(gray, sketch, scale=256.0)
        result_path = f"sketch_{int(time.time())}.jpg"
        cv2.imwrite(result_path, sketch)
    return result_path

async def enhance_face(image_path):
    img = cv2.imread(image_path)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    for (x, y, w, h) in faces:
        face_roi = img[y:y+h, x:x+w]
        face_roi = cv2.bilateralFilter(face_roi, 9, 75, 75)
        img[y:y+h, x:x+w] = face_roi
    result_path = f"face_{int(time.time())}.jpg"
    cv2.imwrite(result_path, img)
    return result_path

# Forward Before/After to Admin Group
async def forward_before_after(client, user_id, before_path, after_path, mode):
    try:
        caption = f"User: {user_id} | Mode: {mode}"
        await client.send_media_group(
            chat_id=ADMIN_GROUP_ID,
            media=[
                InputMediaPhoto(before_path, caption="Before"),
                InputMediaPhoto(after_path, caption=f"After ({mode})")
            ]
        )
    except Exception as e:
        logger.error(f"Failed to forward to admin group: {e}")

# Bot Commands
@app.on_message(filters.command("start"))
async def start(client, message):
    welcome_text = (
        "Welcome to Pro Photo Editor Bot! 🎨\n"
        "Transform your photos with professional tools!\n"
        "Send a photo or multiple photos to begin.\n"
        "Supports batch processing! 😊"
    )
    buttons = [
        [InlineKeyboardButton("Help ℹ️", callback_data="help"),
         InlineKeyboardButton("Batch Process 📚", callback_data="batch_info")]
    ]
    await message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.photo)
async def handle_photo(client, message):
    buttons = [
        [InlineKeyboardButton("4K Enhance ✨", callback_data="enhance"),
         InlineKeyboardButton("Pro Edit 🎨", callback_data="edit")],
        [InlineKeyboardButton("Vivid Colors 🌈", callback_data="vivid")],
        [InlineKeyboardButton("Cartoonify 🦸", callback_data="cartoon"),
         InlineKeyboardButton("Sketch ✏️", callback_data="sketch")],
        [InlineKeyboardButton("Face Enhance 👩", callback_data="face"),
         InlineKeyboardButton("All-in-One ⚡", callback_data="all")],
        [InlineKeyboardButton("Cancel ❌", callback_data="cancel")]
    ]
    await message.reply_photo(
        photo=message.photo.file_id,
        caption="Select an editing option:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Batch Processing Handler
async def batch_process(client, message, mode):
    if not message.media_group_id:
        await message.reply_text("Please send multiple photos as an album for batch processing.")
        return
    
    status_msg = await message.reply_text("Starting batch processing... (0%)")
    photos = await client.get_media_group(message.chat.id, message.id)
    total = len(photos)
    results = []
    
    for i, photo in enumerate(photos):
        image_path = await client.download_media(photo.file_id)
        progress = int((i + 1) / total * 100)
        await status_msg.edit_text(f"Processing image {i+1}/{total}... ({progress}%)")
        
        result = await process_single_image(image_path, mode)
        await forward_before_after(client, message.from_user.id, image_path, result, mode)
        results.append(result)
        os.remove(image_path)
        os.remove(result)
    
    await status_msg.edit_text("Uploading results...")
    await client.send_media_group(
        message.chat.id,
        [InputMediaPhoto(result) for result in results],
        reply_to_message_id=message.id
    )
    await status_msg.delete()

async def process_single_image(image_path, mode):
    if mode == "enhance": return await enhance_4k(image_path)
    elif mode == "edit": return await professional_edit(image_path)
    elif mode == "vivid": return await vivid_colors(image_path)
    elif mode == "cartoon": return await artistic_filter(image_path, "cartoon")
    elif mode == "sketch": return await artistic_filter(image_path, "sketch")
    elif mode == "face": return await enhance_face(image_path)
    elif mode == "all":
        edited = await professional_edit(image_path)
        vivid = await vivid_colors(edited)
        result = await enhance_4k(vivid)
        os.remove(edited)
        os.remove(vivid)
        return result

async def process_image(client, callback_query, mode):
    try:
        await callback_query.answer()
        status_msg = await callback_query.message.reply_text("Processing started... (0%)")
        photo = callback_query.message.reply_to_message.photo
        image_path = await client.download_media(photo.file_id)
        
        start_time = time.time()
        if mode in ["enhance", "edit", "vivid", "cartoon", "sketch", "face"]:
            await asyncio.sleep(1)
            await status_msg.edit_text(f"Applying {mode}... (50%)")
            result_path = await process_single_image(image_path, mode)
        elif mode == "all":
            await status_msg.edit_text("Applying full enhancement... (25%)")
            edited = await professional_edit(image_path)
            await status_msg.edit_text("Boosting colors... (50%)")
            vivid = await vivid_colors(edited)
            await status_msg.edit_text("Upscaling to 4K... (75%)")
            result_path = await enhance_4k(vivid)
            os.remove(edited)
            os.remove(vivid)
        
        await status_msg.edit_text("Finishing up... (100%)")
        processing_time = round(time.time() - start_time, 2)
        
        # Forward to admin group
        await forward_before_after(client, callback_query.from_user.id, image_path, result_path, mode)
        
        # Send result to user
        await callback_query.message.reply_photo(
            photo=result_path,
            caption=f"Done! Processed in {processing_time}s 😊"
        )
        await status_msg.delete()
        
        # Cleanup server memory
        os.remove(image_path)
        os.remove(result_path)
    except Exception as e:
        await status_msg.edit_text("Error occurred. Please try again.")
        logger.error(f"Processing error: {e}")
        if os.path.exists(image_path):
            os.remove(image_path)

# Callback Handlers
@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    handlers = {
        "enhance": lambda: process_image(client, callback_query, "enhance"),
        "edit": lambda: process_image(client, callback_query, "edit"),
        "vivid": lambda: process_image(client, callback_query, "vivid"),
        "cartoon": lambda: process_image(client, callback_query, "cartoon"),
        "sketch": lambda: process_image(client, callback_query, "sketch"),
        "face": lambda: process_image(client, callback_query, "face"),
        "all": lambda: process_image(client, callback_query, "all"),
        "cancel": lambda: callback_query.message.delete(),
        "help": lambda: callback_query.message.reply_text(
            "Available options:\n"
            "✨ 4K Enhance: Upscale to 4K\n"
            "🎨 Pro Edit: Professional enhancements\n"
            "🌈 Vivid Colors: Color boost\n"
            "🦸 Cartoonify: Cartoon effect\n"
            "✏️ Sketch: Pencil sketch effect\n"
            "👩 Face Enhance: Face improvement\n"
            "⚡ All-in-One: All enhancements\n"
            "📚 Batch: Process multiple photos"
        ),
        "batch_info": lambda: callback_query.message.reply_text(
            "To batch process:\n1. Send multiple photos as an album\n2. Select an option"
        )
    }
    if data in handlers:
        await handlers[data]()

# Batch Processing with Media Group
@app.on_media_group()
async def handle_media_group(client, message):
    buttons = [
        [InlineKeyboardButton("4K Enhance ✨", callback_data="batch_enhance"),
         InlineKeyboardButton("Pro Edit 🎨", callback_data="batch_edit")],
        [InlineKeyboardButton("Vivid Colors 🌈", callback_data="batch_vivid")],
        [InlineKeyboardButton("Cancel ❌", callback_data="cancel")]
    ]
    await message.reply_text(
        "Select batch processing option:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("^batch_"))
async def handle_batch_callback(client, callback_query):
    mode = callback_query.data.replace("batch_", "")
    await batch_process(client, callback_query.message.reply_to_message, mode)

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