import base64
import json
import os
import secrets
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from Crypto.Cipher import AES
from PIL import Image, ImageTk


# ============================================================
# SECURE VIEW ONCE - SINGLE FILE LOCAL DEMO
# ============================================================
# This version intentionally does NOT use Flask, requests,
# server.py, sender.py, or receiver.py.
#
# Sender and Receiver are both on this one page.
# The encrypted package is kept in this program's memory so
# the complete demo can run locally without network delays.
#
# AES-256-GCM is used for authenticated encryption.
# ============================================================

KEY_SIZE = 32
NONCE_SIZE = 12

BG = "#0f0f10"
CARD = "#19191b"
INPUT_BG = "#242427"
TEXT = "#f4f4f5"
MUTED = "#96969e"
ACCENT = "#8b7cff"
ACCENT_HOVER = "#7668e8"
SUCCESS = "#72d6a0"
ERROR = "#ff7d7d"

# package_id -> {"encrypted": bytes, "viewed": bool}
PACKAGES = {}


def generate_key():
    return os.urandom(KEY_SIZE)


def key_to_text(key):
    return base64.urlsafe_b64encode(key).decode("ascii")


def key_from_text(text):
    try:
        key = base64.urlsafe_b64decode(text.encode("ascii"))
    except Exception as exc:
        raise ValueError("Invalid encryption key.") from exc

    if len(key) != KEY_SIZE:
        raise ValueError("The key must be a valid 256-bit AES key." )

    return key


def encrypt_image(image_path, key, view_seconds):
    if not 1 <= view_seconds <= 3600:
        raise ValueError("Viewing time must be between 1 and 3600 seconds.")

    with open(image_path, "rb") as f:
        image_data = f.read()

    filename = os.path.basename(image_path)

    metadata = json.dumps(
        {
            "filename": filename,
            "view_seconds": view_seconds,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    nonce = os.urandom(NONCE_SIZE)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

    # Authenticate the metadata as well as the image.
    cipher.update(metadata)
    ciphertext, tag = cipher.encrypt_and_digest(image_data)

    package = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "metadata": base64.b64encode(metadata).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }

    return json.dumps(package, separators=(",", ":")).encode("utf-8")


def decrypt_image(package_bytes, key):
    try:
        package = json.loads(package_bytes.decode("utf-8"))

        if package.get("algorithm") != "AES-256-GCM":
            raise ValueError("Unsupported encryption algorithm.")

        nonce = base64.b64decode(package["nonce"])
        tag = base64.b64decode(package["tag"])
        metadata = base64.b64decode(package["metadata"])
        ciphertext = base64.b64decode(package["ciphertext"])

        if len(nonce) != NONCE_SIZE:
            raise ValueError("Invalid nonce.")
        if len(tag) != 16:
            raise ValueError("Invalid authentication tag.")

    except Exception as exc:
        raise ValueError("The encrypted package is invalid or corrupted.") from exc

    try:
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(metadata)
        image_data = cipher.decrypt_and_verify(ciphertext, tag)
        info = json.loads(metadata.decode("utf-8"))

        seconds = int(info["view_seconds"])
        if not 1 <= seconds <= 3600:
            raise ValueError("Invalid viewing duration.")

    except Exception as exc:
        raise ValueError("Decryption failed. Check the Package ID and encryption key.") from exc

    return image_data, info


class SecureViewOnceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure View Once")
        self.root.geometry("920x720")
        self.root.minsize(820, 650)
        self.root.configure(bg=BG)

        self.image_path = None

        self.temp_path = None
        self.view_window = None
        self.view_image = None
        self.view_photo = None
        self.view_package_id = None
        self.expiring = False

        self.build_ui()

    # ---------------- UI helpers ----------------

    def label(self, parent, text, size=10, bold=False, color=TEXT):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=color,
            bg=parent.cget("bg"),
        )

    def entry(self, parent, show=None):
        e = tk.Entry(
            parent,
            font=("Segoe UI", 10),
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            show=show or "",
        )
        e.pack(fill="x", padx=25, ipady=10, pady=(5, 14))
        return e

    def button(self, parent, text, command, accent=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg=ACCENT if accent else "#2a2a2d",
            activebackground=ACCENT_HOVER if accent else "#38383c",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=14,
            pady=11,
            cursor="hand2",
        )

    def build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=30, pady=(25, 15))

        tk.Label(
            header,
            text="SECURE VIEW ONCE",
            font=("Segoe UI", 24, "bold"),
            fg=TEXT,
            bg=BG,
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Encrypted image • one-time viewing • local demo",
            font=("Segoe UI", 10),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(3, 0))

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=30, pady=10)

        sender = tk.Frame(content, bg=CARD)
        sender.pack(side="left", fill="both", expand=True, padx=(0, 10))

        receiver = tk.Frame(content, bg=CARD)
        receiver.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # ---------------- Sender ----------------

        tk.Label(
            sender,
            text="SENDER",
            font=("Segoe UI", 15, "bold"),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=25, pady=(25, 2))

        tk.Label(
            sender,
            text="Encrypt an image and create a View Once package.",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=25, pady=(0, 22))

        self.select_btn = self.button(
            sender, "SELECT IMAGE", self.select_image
        )
        self.select_btn.pack(fill="x", padx=25)

        self.file_label = tk.Label(
            sender,
            text="No image selected",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
            wraplength=330,
            justify="left",
        )
        self.file_label.pack(anchor="w", padx=25, pady=(8, 18))

        tk.Label(
            sender,
            text="VIEWING DURATION (SECONDS)",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=25)

        timer_row = tk.Frame(sender, bg=CARD)
        timer_row.pack(fill="x", padx=25, pady=(5, 20))

        self.seconds_var = tk.StringVar(value="10")
        self.seconds_entry = tk.Spinbox(
            timer_row,
            from_=1,
            to=3600,
            textvariable=self.seconds_var,
            font=("Segoe UI", 11),
            width=8,
            bg=INPUT_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            buttonbackground=INPUT_BG,
        )
        self.seconds_entry.pack(side="left", ipady=7)

        tk.Label(
            timer_row,
            text="seconds",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
        ).pack(side="left", padx=10)

        self.send_btn = self.button(
            sender, "ENCRYPT & SEND", self.encrypt_and_send, accent=True
        )
        self.send_btn.pack(fill="x", padx=25)

        self.sender_status = tk.Label(
            sender,
            text="Status: Ready",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
            wraplength=330,
            justify="left",
        )
        self.sender_status.pack(anchor="w", padx=25, pady=(18, 10))

        # ---------------- Receiver ----------------

        tk.Label(
            receiver,
            text="RECEIVER",
            font=("Segoe UI", 15, "bold"),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=25, pady=(25, 2))

        tk.Label(
            receiver,
            text="Enter the Package ID and encryption key to view it once.",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=25, pady=(0, 22))

        tk.Label(
            receiver,
            text="PACKAGE ID",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=25)

        self.package_entry = self.entry(receiver)

        tk.Label(
            receiver,
            text="ENCRYPTION KEY",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT,
            bg=CARD,
        ).pack(anchor="w", padx=25)

        self.key_entry = self.entry(receiver)

        self.view_btn = self.button(
            receiver, "VIEW ONCE", self.start_view, accent=True
        )
        self.view_btn.pack(fill="x", padx=25, pady=(3, 8))

        self.receiver_status = tk.Label(
            receiver,
            text="Status: Ready",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=CARD,
            wraplength=330,
            justify="left",
        )
        self.receiver_status.pack(anchor="w", padx=25, pady=(10, 10))

        # ---------------- Bottom explanation ----------------

        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="x", padx=30, pady=(5, 25))

        tk.Label(
            bottom,
            text="DEMO FLOW",
            font=("Segoe UI", 9, "bold"),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w")

        tk.Label(
            bottom,
            text="Select image → Encrypt → Package ID + Key → View Once → Countdown → Cleanup",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=BG,
        ).pack(anchor="w", pady=(3, 0))

    # ---------------- Sender ----------------

    def select_image(self):
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[
                (
                    "Image files",
                    "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff",
                ),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            with Image.open(path) as img:
                img.verify()
        except Exception:
            messagebox.showerror(
                "Invalid image",
                "The selected file could not be opened as an image.",
            )
            return

        self.image_path = path
        self.file_label.config(text=Path(path).name, fg=TEXT)
        self.sender_status.config(
            text="Status: Image selected.",
            fg=SUCCESS,
        )

    def encrypt_and_send(self):
        if not self.image_path:
            messagebox.showwarning(
                "Select image",
                "Please select an image first.",
            )
            return

        try:
            seconds = int(self.seconds_var.get())
        except ValueError:
            messagebox.showerror(
                "Invalid timer",
                "Enter a whole number between 1 and 3600 seconds.",
            )
            return

        if not 1 <= seconds <= 3600:
            messagebox.showerror(
                "Invalid timer",
                "Viewing time must be between 1 and 3600 seconds.",
            )
            return

        self.send_btn.config(state="disabled")
        self.select_btn.config(state="disabled")
        self.sender_status.config(
            text="Status: Encrypting...",
            fg=MUTED,
        )
        self.root.update_idletasks()

        try:
            key = generate_key()
            encrypted_package = encrypt_image(
                self.image_path,
                key,
                seconds,
            )

            package_id = secrets.token_urlsafe(9)

            PACKAGES[package_id] = {
                "encrypted": encrypted_package,
                "viewed": False,
            }

            key_text = key_to_text(key)

            # Auto-fill receiver for the local demo.
            self.package_entry.delete(0, tk.END)
            self.package_entry.insert(0, package_id)

            self.key_entry.delete(0, tk.END)
            self.key_entry.insert(0, key_text)

            self.sender_status.config(
                text=(
                    "Status: Encrypted successfully.\n\n"
                    f"Package ID: {package_id}\n"
                    f"Duration: {seconds} seconds"
                ),
                fg=SUCCESS,
            )

            self.receiver_status.config(
                text="Status: Package details auto-filled. Click VIEW ONCE.",
                fg=SUCCESS,
            )

        except Exception as exc:
            self.sender_status.config(
                text=f"Status: Encryption failed.\n{exc}",
                fg=ERROR,
            )
            messagebox.showerror("Encryption failed", str(exc))

        finally:
            self.send_btn.config(state="normal")
            self.select_btn.config(state="normal")

    # ---------------- Receiver ----------------

    def start_view(self):
        if self.view_window and self.view_window.winfo_exists():
            messagebox.showinfo(
                "Already viewing",
                "An image is already open in the View Once window.",
            )
            return

        package_id = self.package_entry.get().strip()
        key_text = self.key_entry.get().strip()

        if not package_id:
            messagebox.showwarning(
                "Missing Package ID",
                "Enter a Package ID.",
            )
            return

        if not key_text:
            messagebox.showwarning(
                "Missing encryption key",
                "Enter the encryption key.",
            )
            return

        try:
            key = key_from_text(key_text)
        except ValueError as exc:
            messagebox.showerror("Invalid key", str(exc))
            return

        record = PACKAGES.get(package_id)

        if record is None:
            self.receiver_status.config(
                text="Status: Package not found.",
                fg=ERROR,
            )
            messagebox.showerror(
                "Package not found",
                "That Package ID does not exist in this local demo.",
            )
            return

        if record["viewed"]:
            self.receiver_status.config(
                text="Status: This package has already been viewed.",
                fg=ERROR,
            )
            messagebox.showinfo(
                "Already viewed",
                "This View Once image has already been consumed.",
            )
            return

        self.view_btn.config(state="disabled")
        self.receiver_status.config(
            text="Status: Decrypting...",
            fg=MUTED,
        )
        self.root.update_idletasks()

        try:
            image_data, info = decrypt_image(
                record["encrypted"],
                key,
            )

            seconds = int(info["view_seconds"])
            filename = info.get("filename", "image")
            suffix = Path(filename).suffix or ".img"

            fd, path = tempfile.mkstemp(
                prefix="secure_view_once_",
                suffix=suffix,
            )
            os.close(fd)

            with open(path, "wb") as f:
                f.write(image_data)

            self.temp_path = path
            self.view_package_id = package_id
            self.expiring = False

            # Mark consumed before displaying it. This prevents a second
            # View Once attempt while the first viewer is still open.
            record["viewed"] = True

            self.receiver_status.config(
                text=f"Status: Viewing for {seconds} seconds...",
                fg=SUCCESS,
            )

            self.show_image(path, seconds)

        except Exception as exc:
            self.cleanup_temp()
            self.view_btn.config(state="normal")
            self.receiver_status.config(
                text=f"Status: Failed.\n{exc}",
                fg=ERROR,
            )
            messagebox.showerror("Unable to view", str(exc))

    def show_image(self, path, seconds):
        try:
            image = Image.open(path)
            image.load()

            # Keep the original image object alive while the window exists.
            self.view_image = image

            # Fit the image into a reasonable desktop window.
            max_w = max(500, self.root.winfo_screenwidth() - 160)
            max_h = max(400, self.root.winfo_screenheight() - 230)

            image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

            self.view_window = tk.Toplevel(self.root)
            self.view_window.title("View Once")
            self.view_window.configure(bg="#080808")
            self.view_window.protocol(
                "WM_DELETE_WINDOW",
                self.expire_view,
            )

            self.view_window.transient(self.root)
            self.view_window.grab_set()

            title = tk.Label(
                self.view_window,
                text="VIEW ONCE",
                font=("Segoe UI", 15, "bold"),
                fg=TEXT,
                bg="#080808",
            )
            title.pack(pady=(15, 2))

            timer_label = tk.Label(
                self.view_window,
                text=f"{seconds}s",
                font=("Segoe UI", 20, "bold"),
                fg=TEXT,
                bg="#080808",
            )
            timer_label.pack(pady=(0, 10))

            self.view_photo = ImageTk.PhotoImage(image)

            image_label = tk.Label(
                self.view_window,
                image=self.view_photo,
                bg="#080808",
            )
            image_label.pack(padx=20, pady=(0, 20))

            self.view_window.update_idletasks()

            # Center the viewer on screen.
            w = self.view_window.winfo_width()
            h = self.view_window.winfo_height()
            sw = self.view_window.winfo_screenwidth()
            sh = self.view_window.winfo_screenheight()

            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)

            self.view_window.geometry(f"{w}x{h}+{x}+{y}")

            self.countdown(seconds, timer_label)

        except Exception as exc:
            self.cleanup_temp()
            self.view_image = None
            self.view_photo = None
            self.view_window = None
            self.view_btn.config(state="normal")
            self.receiver_status.config(
                text=f"Status: Could not display image.\n{exc}",
                fg=ERROR,
            )
            messagebox.showerror("Display error", str(exc))

    def countdown(self, remaining, timer_label):
        if self.expiring:
            return

        if not self.view_window or not self.view_window.winfo_exists():
            self.expire_view()
            return

        timer_label.config(text=f"{remaining}s")

        if remaining <= 0:
            self.expire_view()
            return

        self.root.after(
            1000,
            lambda: self.countdown(remaining - 1, timer_label),
        )

    def expire_view(self):
        if self.expiring:
            return

        self.expiring = True

        if self.view_window and self.view_window.winfo_exists():
            try:
                self.view_window.grab_release()
            except tk.TclError:
                pass
            self.view_window.destroy()

        self.view_window = None
        self.view_photo = None
        self.view_image = None

        self.cleanup_temp()

        package_id = self.view_package_id
        self.view_package_id = None

        self.view_btn.config(state="normal")

        if package_id:
            self.receiver_status.config(
                text=(
                    "Status: View Once expired.\n"
                    "The decrypted temporary copy was deleted.\n"
                    "This package cannot be viewed again."
                ),
                fg=SUCCESS,
            )

        self.expiring = False

    def cleanup_temp(self):
        if self.temp_path:
            try:
                os.remove(self.temp_path)
            except OSError:
                pass
            self.temp_path = None

    # ---------------- Application close ----------------

    def close(self):
        self.expiring = True

        if self.view_window and self.view_window.winfo_exists():
            try:
                self.view_window.grab_release()
            except tk.TclError:
                pass
            self.view_window.destroy()

        self.view_window = None
        self.view_photo = None
        self.view_image = None

        self.cleanup_temp()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = SecureViewOnceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()