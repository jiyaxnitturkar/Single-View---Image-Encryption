# Secure View Once

A local desktop demonstration of encrypted, time-limited, one-time image viewing. The application lets a sender select an image, encrypt it, create a package ID and encryption key, and then open the image in a receiver window for a limited period.

> **Project type:** Single-file Python desktop demo
>
> **Current scope:** Local process only; no server, database, API, or network transport

## Features

- Select and validate an image file before encryption.
- Encrypt image bytes with AES-256-GCM.
- Authenticate the image metadata as additional authenticated data.
- Generate a cryptographically secure encryption key and package ID.
- Configure a viewing duration from 1 to 3,600 seconds.
- Mark a package as consumed before the image is displayed.
- Display the decrypted image in a modal Tkinter window with a countdown.
- Delete the temporary decrypted file when the timer expires, the viewer closes, or the application exits.
- Reject invalid keys, unknown package IDs, corrupted packages, unsupported algorithms, and repeated viewing attempts.

## Technology Stack

| Technology | Role | Why it is used |
| --- | --- | --- |
| **Python 3** | Application language | Provides a compact, readable implementation suitable for a security-focused prototype and desktop automation. |
| **Tkinter** | Desktop GUI | Included with standard Python installations, so the demo can provide a native cross-platform interface without a web server or frontend build system. |
| **PyCryptodome** | Cryptography | Provides the AES-GCM implementation used for authenticated encryption. It is used instead of implementing cryptographic primitives manually. |
| **AES-256-GCM** | Encryption algorithm | Provides confidentiality and integrity together. A modified image or metadata causes decryption verification to fail. |
| **Pillow** | Image validation and rendering | Verifies that the selected file is an image, loads image data, resizes it for display, and integrates with Tkinter through `ImageTk`. |
| **Python standard library** | Supporting services | `secrets` generates package IDs, `os.urandom` generates encryption keys and nonces, `tempfile` creates temporary files, `json` serializes the package, and `base64` makes binary values transportable as text. |

## Architecture

The application intentionally keeps the sender and receiver in one Python process. The encrypted package is stored in the in-memory `PACKAGES` dictionary.

```text
                    secure_view_once.py
                             |
        +--------------------+--------------------+
        |                                         |
   Sender UI                                 Receiver UI
        |                                         |
  Select image                              Package ID + key
        |                                         |
  Validate with Pillow                            |
        |                                         |
  Generate key + nonce                            |
        |                                         |
  AES-256-GCM encrypt                              |
        |                                         |
  Store encrypted package ----------------------->|
        |                               Verify key and package
        |                                         |
        |                               Decrypt and authenticate
        |                                         |
        |                               Mark package as viewed
        |                                         |
        |                               Temporary decrypted file
        |                                         |
        +----------------------> Timed viewer -> cleanup
```

### Main components

#### Cryptographic helpers

- `generate_key()` creates a 32-byte key.
- `key_to_text()` and `key_from_text()` convert the binary key to and from URL-safe Base64.
- `encrypt_image()` reads image bytes, creates metadata, encrypts the bytes, and returns a JSON package.
- `decrypt_image()` parses and validates the package, verifies the GCM authentication tag, and returns the original image bytes and metadata.

#### In-memory package store

```python
PACKAGES[package_id] = {
    "encrypted": encrypted_package,
    "viewed": False,
}
```

This keeps the demo simple and avoids introducing a database or network layer. It also means all packages disappear when the process exits.

#### `SecureViewOnceApp`

The application class owns the UI state and workflow:

- Builds the sender and receiver panels.
- Validates user input.
- Coordinates encryption and decryption.
- Controls the view-once state.
- Manages the countdown and temporary-file lifecycle.

## Encryption Package Format

The encrypted package is compact JSON containing Base64-encoded binary values:

```json
{
  "version": 1,
  "algorithm": "AES-256-GCM",
  "nonce": "...",
  "tag": "...",
  "metadata": "...",
  "ciphertext": "..."
}
```

The metadata contains the original filename and viewing duration. It is Base64-encoded in the package and supplied to GCM through `cipher.update(metadata)`, which authenticates it without encrypting it separately. This prevents an attacker from changing the filename or timer without causing verification to fail.

### Why AES-GCM?

AES-GCM is an authenticated-encryption mode:

1. AES encrypts the image data so the plaintext is not exposed in the package.
2. GCM produces an authentication tag.
3. Decryption verifies the tag before accepting the plaintext.
4. Tampering with the ciphertext, nonce, or authenticated metadata causes verification to fail.

The application uses a fresh random 12-byte nonce for every package. The encryption key is 32 bytes, which corresponds to AES-256.

## End-to-End Pipeline

### Sender pipeline

1. The user selects an image with the file picker.
2. Pillow opens and verifies the image.
3. The viewing duration is checked to be between 1 and 3,600 seconds.
4. A random 256-bit AES key and 96-bit GCM nonce are generated.
5. The image bytes are encrypted with AES-256-GCM.
6. Filename and viewing duration are authenticated as metadata.
7. The encrypted JSON package is stored in memory under a random package ID.
8. The package ID and key are shown in the receiver panel for this local demo.

### Receiver pipeline

1. The user submits a package ID and encryption key.
2. The key is decoded and checked for the expected 32-byte length.
3. The package is looked up in memory.
4. The application rejects missing or already-viewed packages.
5. AES-GCM verifies and decrypts the package.
6. The package is marked as viewed **before** display begins, preventing a second attempt during the active viewing session.
7. Plain image bytes are written to a uniquely named temporary file.
8. Pillow loads the temporary file and Tkinter displays it.
9. The countdown expires, the viewer closes, or the application exits.
10. The viewer is destroyed and the temporary decrypted file is deleted.

## Security Design

### Security properties demonstrated

- **Confidentiality:** The stored package contains encrypted image data.
- **Integrity:** AES-GCM authentication detects modified ciphertext and metadata.
- **Key separation from package:** The key is generated independently and is not embedded in the encrypted package.
- **One-time state transition:** The package is marked viewed before rendering.
- **Short-lived plaintext:** Decrypted data is written to a temporary path only when viewing starts.
- **Input validation:** Package fields, nonce length, tag length, key length, algorithm, and timer range are checked.

### Important limitations

This is a local educational demo, not a production secure-sharing service:

- The package store is process memory, so there is no persistence or multi-user delivery.
- There is no sender/receiver identity, login, authorization, or audit trail.
- The package ID and key are auto-filled into the same application, so the demo does not model secure key exchange.
- The decrypted image exists temporarily on the local filesystem. `os.remove()` requests deletion but cannot guarantee forensic erasure from storage, caches, backups, or operating-system artifacts.
- A user can still capture the image with a screenshot, camera, screen recorder, or another process with sufficient permissions.
- The package is Base64-encoded JSON, not a secure transport protocol or a substitute for TLS.
- The application does not securely wipe Python strings, image objects, Tkinter buffers, or operating-system memory after use.
- A production one-time-view service would need server-side atomic state updates, access control, encrypted storage, key delivery, rate limiting, logging, and a threat model for clients and screenshots.

## Project Structure

```text
secure_view_once_SINGLE_FILE/
├── secure_view_once.py   # GUI, encryption, package store, viewer, cleanup
├── requirements.txt      # Third-party Python dependencies
└── README.md             # Project documentation
```

## Setup

### Prerequisites

- Python 3.9 or newer recommended
- Tkinter available in the Python installation

### Install dependencies

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Windows Command Prompt:

```bat
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Run

```bash
python secure_view_once.py
```

### Demo steps

1. Select a supported image.
2. Choose a viewing duration.
3. Select **ENCRYPT & SEND**.
4. Review the generated Package ID and encryption key.
5. Select **VIEW ONCE**.
6. Observe the countdown and expiration cleanup.
7. Try viewing the same package again; it should be rejected.

## Interview Discussion Points

### Why was the package marked viewed before display?

Marking it viewed before rendering closes a race in the local workflow: while an image is open, another view attempt cannot consume the same package. In a networked implementation this transition should be an atomic server-side operation, such as a conditional update from `viewed = false` to `viewed = true`.

### Why authenticate metadata?

The filename and viewing duration influence application behavior. Authenticating them prevents an attacker from changing the timer or other control values without detection.

### Why use `secrets` for the package ID?

Package IDs are identifiers that may be exposed to users. `secrets.token_urlsafe()` is intended for security-sensitive random values and is preferable to predictable counters or general-purpose pseudo-random generation.

### What would change in production?

The next architecture would separate the desktop or web client from a backend service. The backend would persist encrypted packages, perform an atomic one-time claim, enforce authorization and expiration, deliver keys through a separately protected channel, and use TLS for transport. The client would still need to be treated as a trusted-enough display environment rather than a perfect copy-prevention boundary.

## Future Improvements

- Add automated unit tests for encryption, tampering, invalid keys, expiration, and repeated views.
- Add a persistent database-backed package store with atomic consume semantics.
- Add authenticated users and explicit access control.
- Separate package delivery from key delivery.
- Add structured logging without logging plaintext images or encryption keys.
- Add package expiration independent of the viewer window.
- Add a command-line or web client while preserving the cryptographic core.
- Add dependency pinning and security scanning in CI.

## License

No license has been specified yet. Add a license before publishing this repository for reuse by others.
