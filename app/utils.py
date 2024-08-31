import asyncio
import logging

import aiofiles
import aiohttp
import pandas as pd
from PIL import Image as PilImage
from fastapi import HTTPException, UploadFile
from io import BytesIO

from app.db import fetch_images_by_request_id, Image, async_session, Task
from app.models import Status

import os

# Ensure the directory exists
output_dir = "./static"
os.makedirs(output_dir, exist_ok=True)

logger = logging.getLogger(__name__)

async def validate_csv(file: UploadFile):
    # File Sanitization
    if file.content_type not in ["text/csv", "application/vnd.ms-excel"]:
        msg = "Uploaded file is not a CSV"
        logger.warning(msg)
        raise HTTPException(status_code=400, detail=msg)

    if not file.filename.endswith(".csv"):
        msg = "File does not have a .csv extension"
        logger.warning(msg)
        raise HTTPException(status_code=400, detail=msg)

    try:
        # Read CSV using pandas
        content = await file.read()
        cols = pd.read_csv(BytesIO(content), nrows=1).columns
        df = pd.read_csv(BytesIO(content))

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV: {str(e)}")

    # Expected columns
    expected_columns = ['S. No.', 'Product Name', 'Input Image Urls']
    if list(df.columns) != expected_columns:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format. Expected columns: {expected_columns}")

    return df

async def process_images(request_id):
    images = await fetch_images_by_request_id(request_id)
    for image in images:
        image_record = await Image.fetch_by_id(image.image_id)

        try:
            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(image_record.input_url) as response:
                    img_bytes = await response.read()

            if not img_bytes:
                logger.error(f"Invalid url for {image.image_id}")
                return
            img = await asyncio.to_thread(PilImage.open, BytesIO(img_bytes))
            output_buffer = BytesIO()
            await asyncio.to_thread(img.save, output_buffer, format="JPEG", quality=50)  # Compress by 50%
            output_url = os.path.join(output_dir, f"{image_record.image_id}.jpg")

            # Save the image file
            async with aiofiles.open(output_url, "wb") as f:
                await f.write(output_buffer.getvalue())

            # Update image record with output URL
            image_record.output_url = output_url
            image_record.status = Status.Complete

            # Save the image file
            with open(output_url, "wb") as f:
                f.write(output_buffer.getvalue())

            # Update image record with output URL and increment task processed_image count
            try:
                async with async_session() as session:
                    await image_record.set_complete(session, output_url)
                    task = await Task.fetch_by_request_id(request_id)
                    task = await task.increment_processed_images(session)
                    await session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Error while updating image record {image_record.image_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing image {image.image_id}: {str(e)}")

        # Check if all images for the request are processed
        if task.webhook_url and task.processed_images == task.total_images:
            await trigger_webhook(task.webhook_url, task.request_id)

async def trigger_webhook(url: str, request_id: str):
    payload = {"request_id": request_id, "status": "completed"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to trigger webhook for request {request_id}: HTTP status {response.status}")
        except Exception as e:
            logger.error(f"Failed to trigger webhook for request {request_id}: {str(e)}")