import csv
import io
import logging
import traceback
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from db import Task, create_request, async_session, fetch_images_by_request_id, Product

from utils import validate_csv, process_images

logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/upload")
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...), webhook_url: str = None):
    # File Sanitization
    df = await validate_csv(file)
    print(df)
    # return
    request_id = str(uuid4())

    # Store validated data in DB
    try:
        async with async_session() as session:
            async with session.begin():
                # Create a task with a request id
                task = Task(
                    request_id=request_id,
                    webhook_url=webhook_url,
                )
                session.add(task)

            # for that task, add product and image information
            for index, row in df.iterrows():
                serial_num = row['S. No.']
                product_name = row['Product Name']
                input_image_urls = row['Input Image Urls']

                await create_request(
                    task,
                    session,
                    request_id=request_id,
                    serial_num=serial_num,
                    product_name=product_name,
                    input_image_urls=input_image_urls,
                    webhook_url=webhook_url
                )
        await session.commit()
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f"Upload API: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    try:
        background_tasks.add_task(process_images, request_id)
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f"Upload API: {e}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"request_id": request_id}

@app.get("/status/{request_id}")
async def get_status(request_id: str):
    # Fetch status from the database
    task = await Task.fetch_by_request_id(request_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    status = "complete" if task.processed_images == task.total_images else "processing"
    return {"request_id": request_id, "status": status, "progress": f"{task.processed_images}/{task.total_images}"}


@app.get("/export-csv/{request_id}")
async def export_to_csv(request_id: str):
    if not (await Task.is_complete(request_id)):
        return {"task is still processing"}

    products = await Product.fetch_all_data_by_request_id(request_id)

    # Prepare CSV data in memory
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=['Serial Number', 'Product Name', 'Input Image Urls', 'Output Image Urls']
    )
    writer.writeheader()

    for product in products:
        input_urls = [image.input_url for image in product.images]
        output_urls = [image.output_url for image in product.images]

        input_urls_str = ', '.join(input_urls)
        output_urls_str = ', '.join(output_urls)

        writer.writerow({
            'Serial Number': product.serial_num,
            'Product Name': product.product_name,
            'Input Image Urls': input_urls_str,
            'Output Image Urls': output_urls_str
        })

    output.seek(0)  # Move cursor to the beginning of the stream

    # Return CSV file as a streaming response
    return StreamingResponse(
        output,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="data.csv"'}
    )

