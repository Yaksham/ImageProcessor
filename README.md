- [Overview](https://github.com/Yaksham/ImageProcessor?tab=readme-ov-file#overview)
- [Installation](https://github.com/Yaksham/ImageProcessor?tab=readme-ov-file#installation)

## Overview

The project is a backend service built using FastAPI, SQL DB and FastAPI Background Tasks for async, non blocking processing. The application handles CSV uploads containing product and image URLs, processes images (including compression and transformation), and stores data in a SQLite database using SQLAlchemy with asynchronous support.

## Components

- **API Server**: FastAPI serves as the API backend.
- **Database**: SQLite with SQLAlchemy ORM.
- **Image Processing**: Image transformation using Python's Pillow library.
- **CSV Handling**: Validation and parsing of CSV files using Pandas.

## Modules and Responsibilities

### 1. Main API Module (`main.py`)

- **Endpoints**:
  - `POST /upload`: Accepts a CSV file (and optionally a webhook URL), validates it, stores the data in the database and instantly returns a request_id. It then triggers a background image processing task.
  - `GET /status/{request_id}`: Returns the status of a specific request based on the request ID.
  - `GET /export-csv/{request_id}`: Exports all processed images related to a specific request into a CSV file and serves it as a downloadable file.


### 2. Utility Module (`utils.py`)

- **Functions**:
  - `validate_csv`: Validates the structure and content of the uploaded CSV file.
  - `process_images`: Processes images asynchronously in background, compresses them, updates their status, and handles failures.
  - `trigger_webhook`: Sends a POST request to a specified webhook URL upon completion of all image processing tasks for a request.

- **Error Handling**:
  - Validates CSV content types and structure, handling various error scenarios with appropriate HTTP exceptions.
  - Handles image processing failures and updates the image status to error if processing fails.

### 3. Database Module (`db.py`)

- **Models**:
  - `Task`: Represents a task containing request details and processing progress.
  - `Product`: Represents a product associated with a task.
  - `Image`: Represents images tied to a product, including input and output URLs and status.

- **Key Functions**:
  - `create_request`: Creates and stores a task, product, and image data in the database.
  - `fetch_images_by_request_id`: Fetches all images associated with a specific request ID.
  - CRUD operations and utility methods for fetching, updating, and managing database records.
 
    
#### Database Schema

- **Tasks Table**:
  - `task_id`: Primary key.
  - `request_id`: Unique identifier for the request.
  - `total_images`: Total number of images to be processed.
  - `processed_images`: Count of processed images.
  - `webhook_url`: URL for webhook notifications on completion.

- **Products Table**:
  - `product_id`: Primary key.
  - `serial_num`: Serial number of the product.
  - `product_name`: Name of the product.
  - `request_id`: Foreign key linking to a task.

- **Images Table**:
  - `image_id`: Primary key.
  - `product_id`: Foreign key linking to a product.
  - `input_url`: Original URL of the input image.
  - `output_url`: URL of the processed image.
  - `status`: Enum indicating processing status.

## Data Flow and Interactions

### CSV Upload and Processing Workflow

- **CSV Validation**:
  - `validate_csv` checks the content type and expected columns.
  - Converts CSV content into a Pandas DataFrame for easier manipulation.

- **Task and Data Creation**:
  - A new task is created in the database with a unique request ID and associated webhook URL (if provided).
  - Products and images are extracted from the DataFrame and saved to the database.

- **Image Processing**:
  - Each image URL is fetched asynchronously using aiohttp, processed with Pillow (compressed to JPEG), and saved to the local file system.
  - Image records are updated in the database with output URLs and statuses.

- **Status Tracking**:
  - Each task tracks the number of total and processed images.
  - The `increment_processed_images` method updates the count of processed images.

- **Completion Notification**:
  - If a webhook URL is specified, `trigger_webhook` sends a POST request once all images are processed.

## Error Handling and Logging

- **CSV Validation**: Errors in file type, structure, or content are logged and returned as HTTP exceptions.
- **Image Processing**: Errors in downloading or processing images are logged. Image status is set to Error if failures occur.
- **Database Operations**: Errors during database transactions are logged, and transactions are rolled back to maintain data integrity.

## Concurrency and Performance

- Uses asynchronous SQLAlchemy sessions to handle database operations without blocking.
- Aiohttp is used for non-blocking I/O operations when fetching images.
- Aiofiles is used for asynchronus file writing.

## Installation

1. Clone this repository 
2. Install python 3.12 (other versions might work, but haven't been tested)
3. (Optional) Create a virtual python environment
    ``` 
    $ python -m venv .venv
    $ source .venv/bin/activate
    ```

4. Install dependencies:
    ```
      pip install -r requirements.txt
    ```
## Running the Server
    fastapi dev main.py

## Hitting Endpoints
You can visit http://localhost:8000/docs after running the fastapi server to hit the endpoints using a GUI.
