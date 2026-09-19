# Secure View Once — Single File

This is a local academic/demo version of the Secure View Once project.

## Run

Install dependencies:

    pip install pycryptodome Pillow

Then run:

    python secure_view_once.py

## How it works

1. Select an image in SENDER.
2. Choose the number of seconds.
3. Click ENCRYPT & SEND.
4. The Package ID and encryption key are generated and automatically placed in RECEIVER for the local demo.
5. Click VIEW ONCE.
6. The image is decrypted and displayed for the selected duration.
7. When the timer reaches zero, the viewer closes and the temporary decrypted file is deleted.
8. The same Package ID is marked as viewed and cannot be opened again.

## Important

This single-file version intentionally has no Flask server and no HTTP requests.
The encrypted package is stored only in this program's memory. It is therefore a local prototype, not a real two-device messaging system.

Deleting the temporary file does not guarantee forensic-level erasure, and software cannot prevent screenshots or photographs of the screen.
