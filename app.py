#!/usr/bin/env python3
"""Marktbericht GUI: pick a Word file, render it, open the HTML in an editor.

On Windows, start it without a console window with: pythonw app.py
"""
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog as fd
from tkinter import messagebox, ttk

from create_page_docx import create_page

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
SETTINGS = BASE_DIR / "data.json"  # remembers the last file

NOTEPAD_PLUS_PLUS = [
    Path(os.environ.get(var, "")) / "Notepad++" / "notepad++.exe"
    for var in ("ProgramFiles", "ProgramFiles(x86)")
]


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        SETTINGS.write_text(json.dumps(settings), encoding="utf-8")
    except OSError:
        pass  # not being able to remember the last file is harmless


def open_in_editor(path):
    # The default .html handler is the browser, so an editor is started directly.
    if sys.platform == "win32":
        editor = next((str(p) for p in NOTEPAD_PLUS_PLUS if p.is_file()), "notepad.exe")
        subprocess.Popen([editor, str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", str(path)])
    else:
        editor = next(filter(shutil.which, ("gnome-text-editor", "gedit", "kate",
                                            "mousepad", "xed")), "xdg-open")
        subprocess.Popen([editor, str(path)])


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Marktbericht")
        self.resizable(True, False)
        self.settings = load_settings()

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Word-Datei:").grid(row=0, column=0, sticky="w")
        self.file = tk.StringVar(value=self.settings.get("file", ""))
        ttk.Entry(frame, textvariable=self.file, width=60).grid(
            row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(frame, text="Durchsuchen…", command=self.select_file).grid(
            row=1, column=1)

        ttk.Button(frame, text="HTML erstellen und öffnen", command=self.process).grid(
            row=2, column=0, columnspan=2, pady=(12, 6))

        self.status = ttk.Label(frame, text="", foreground="gray")
        self.status.grid(row=3, column=0, columnspan=2, sticky="w")

    def select_file(self):
        current = Path(self.file.get())
        filename = fd.askopenfilename(
            title="Marktbericht auswählen",
            initialdir=current.parent if current.parent.is_dir() else Path.home(),
            filetypes=(("Word-Dokumente", "*.docx"), ("Alle Dateien", "*.*"))
        )
        if filename:
            self.file.set(filename)

    def process(self):
        docx = Path(self.file.get())
        if not docx.is_file():
            messagebox.showerror("Marktbericht", "Bitte zuerst eine Word-Datei auswählen.")
            return
        try:
            date, html = create_page(str(docx))
            OUTPUT_DIR.mkdir(exist_ok=True)
            out = OUTPUT_DIR / f"{date}.html"
            out.write_text(html, encoding="utf-8")
        except Exception as error:
            messagebox.showerror("Marktbericht", f"{docx.name} konnte nicht verarbeitet werden:\n\n{error}")
            return

        self.settings["file"] = str(docx)
        save_settings(self.settings)
        self.status.config(text=f"Gespeichert: {out}")
        try:
            open_in_editor(out)
        except OSError as error:
            messagebox.showerror("Marktbericht", f"Editor konnte nicht gestartet werden:\n\n{error}")


if __name__ == "__main__":
    if sys.platform == "win32":
        try:  # sharp text on scaled displays instead of a blurry bitmap
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().mainloop()
