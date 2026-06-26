"""
Graphical User Interface for the AI Code Reviewer.

A professional desktop front-end built with CustomTkinter. It reuses the
existing core modules (file reading, Groq client, report generation) without
modifying any business logic, running the analysis on a background thread so
the interface stays responsive.

Run with:
    python -m src.gui
"""
from __future__ import annotations

import os
import re
import sys
import threading
import subprocess
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional

import customtkinter as ctk

from src.utils.config import Config
from src.utils.logger import setup_logger
from src.analyzer.file_reader import LocalFileReader
from src.ai_engine.llm_client import GroqClient
from src.reports.generator import ReportGenerator

logger = setup_logger(__name__)

# ---------------------------------------------------------------------------
# Appearance / theme
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT = "#3B82F6"        # primary blue
ACCENT_HOVER = "#2563EB"
SUCCESS = "#22C55E"
DANGER = "#EF4444"
SURFACE = "#1B1D23"
SURFACE_2 = "#23262E"
TEXT_MUTED = "#9CA3AF"
CODE_BG = "#0F1117"


class CodeReviewerApp(ctk.CTk):
    """Main application window for the AI Code Reviewer GUI."""

    def __init__(self) -> None:
        super().__init__()

        self.title("AI Code Reviewer")
        self.geometry("1180x740")
        self.minsize(960, 600)

        # Application state
        self.selected_files: List[Path] = []
        self.reviews: Dict[str, str] = {}
        self.report_path: Optional[str] = None
        self.active_file: Optional[str] = None
        self._is_running: bool = False
        self._file_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_layout()
        self._refresh_api_status()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_sidebar()
        self._build_results_panel()
        self._build_statusbar()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, height=72, corner_radius=0, fg_color=SURFACE)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            header,
            text="  Code Reviewer",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=(14, 0), sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="      Clean Code · SOLID · Security · Performance — powered by Llama 3 (Groq)",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        self.api_badge = ctk.CTkLabel(
            header,
            text="● API key",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED,
        )
        self.api_badge.grid(row=0, column=2, rowspan=2, padx=(0, 12), sticky="e")

        settings_btn = ctk.CTkButton(
            header,
            text="API Key",
            width=110,
            fg_color=SURFACE_2,
            hover_color="#2E323C",
            command=self._open_api_dialog,
        )
        settings_btn.grid(row=0, column=3, rowspan=2, padx=(0, 20), sticky="e")

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color=SURFACE_2)
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.grid_rowconfigure(5, weight=1)
        sidebar.grid_propagate(False)

        section = ctk.CTkLabel(
            sidebar,
            text="SOURCE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        section.grid(row=0, column=0, padx=20, pady=(18, 6), sticky="ew")

        folder_btn = ctk.CTkButton(
            sidebar,
            text="Select Folder",
            height=40,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._choose_folder,
        )
        folder_btn.grid(row=1, column=0, padx=20, pady=4, sticky="ew")

        files_btn = ctk.CTkButton(
            sidebar,
            text="Select Files",
            height=40,
            fg_color=SURFACE,
            hover_color="#2E323C",
            command=self._choose_files,
        )
        files_btn.grid(row=2, column=0, padx=20, pady=4, sticky="ew")

        list_header = ctk.CTkLabel(
            sidebar,
            text="FILES TO ANALYZE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        list_header.grid(row=3, column=0, padx=20, pady=(16, 4), sticky="ew")

        self.file_list = ctk.CTkScrollableFrame(sidebar, fg_color=SURFACE)
        self.file_list.grid(row=5, column=0, padx=14, pady=(0, 10), sticky="nsew")
        self.file_list.grid_columnconfigure(0, weight=1)

        self.empty_hint = ctk.CTkLabel(
            self.file_list,
            text="No files selected yet.\nChoose a folder or files to begin.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            justify="center",
        )
        self.empty_hint.grid(row=0, column=0, pady=30)

        self.analyze_btn = ctk.CTkButton(
            sidebar,
            text="Run Analysis",
            height=46,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=SUCCESS,
            hover_color="#16A34A",
            command=self._start_analysis,
        )
        self.analyze_btn.grid(row=6, column=0, padx=20, pady=(4, 6), sticky="ew")

        self.clear_btn = ctk.CTkButton(
            sidebar,
            text="Clear",
            height=34,
            fg_color="transparent",
            hover_color=SURFACE,
            border_width=1,
            border_color="#3A3E48",
            text_color=TEXT_MUTED,
            command=self._clear_all,
        )
        self.clear_btn.grid(row=7, column=0, padx=20, pady=(0, 18), sticky="ew")

    def _build_results_panel(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        panel.grid(row=1, column=1, sticky="nsew", padx=(0, 0))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # Toolbar above the results view
        toolbar = ctk.CTkFrame(panel, height=48, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        toolbar.grid_columnconfigure(0, weight=1)

        self.result_title = ctk.CTkLabel(
            toolbar,
            text="Review",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        )
        self.result_title.grid(row=0, column=0, sticky="w")

        self.open_report_btn = ctk.CTkButton(
            toolbar,
            text="Open Report",
            width=130,
            state="disabled",
            fg_color=SURFACE_2,
            hover_color="#2E323C",
            command=self._open_report,
        )
        self.open_report_btn.grid(row=0, column=1, padx=(8, 0))

        self.open_folder_btn = ctk.CTkButton(
            toolbar,
            text="Output Folder",
            width=140,
            state="disabled",
            fg_color=SURFACE_2,
            hover_color="#2E323C",
            command=self._open_output_folder,
        )
        self.open_folder_btn.grid(row=0, column=2, padx=(8, 0))

        # Rendered review text
        self.result_box = ctk.CTkTextbox(
            panel,
            wrap="word",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=SURFACE,
            border_width=0,
        )
        self.result_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 8))
        self._configure_markdown_tags()
        self._show_welcome()

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=SURFACE)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            bar,
            text="Ready.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=18, pady=8, sticky="w")

        self.progress = ctk.CTkProgressBar(bar, width=260)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, padx=18, pady=8, sticky="e")

    # ------------------------------------------------------------------
    # Markdown rendering (into the underlying tkinter Text widget)
    # ------------------------------------------------------------------
    def _configure_markdown_tags(self) -> None:
        text = self.result_box._textbox  # underlying tk.Text
        text.tag_configure("h1", font=("Segoe UI", 20, "bold"), spacing1=12, spacing3=6)
        text.tag_configure("h2", font=("Segoe UI", 16, "bold"),
                            foreground=ACCENT, spacing1=12, spacing3=4)
        text.tag_configure("h3", font=("Segoe UI", 14, "bold"), spacing1=8, spacing3=2)
        text.tag_configure("bold", font=("Segoe UI", 13, "bold"))
        text.tag_configure("bullet", lmargin1=24, lmargin2=40, spacing3=2)
        text.tag_configure("code_inline", font=("Cascadia Code", 12),
                            background=CODE_BG, foreground="#E5C07B")
        text.tag_configure("code_block", font=("Cascadia Code", 12),
                            background=CODE_BG, foreground="#9CDCFE",
                            lmargin1=18, lmargin2=18, spacing1=2, spacing3=2)
        text.tag_configure("hr", foreground="#3A3E48")
        text.tag_configure("muted", foreground=TEXT_MUTED)

    def _render_markdown(self, md: str) -> None:
        """A lightweight Markdown renderer: headings, bullets, code, bold."""
        box = self.result_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        text = box._textbox

        in_code_block = False
        for raw_line in md.splitlines():
            line = raw_line.rstrip("\n")

            # Fenced code blocks ```
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                text.insert("end", line + "\n", "code_block")
                continue

            stripped = line.strip()
            if stripped.startswith("# "):
                text.insert("end", stripped[2:] + "\n", "h1")
            elif stripped.startswith("## "):
                text.insert("end", stripped[3:] + "\n", "h2")
            elif stripped.startswith("### "):
                text.insert("end", stripped[4:] + "\n", "h3")
            elif stripped in ("---", "***", "___"):
                text.insert("end", "─" * 60 + "\n", "hr")
            elif stripped.startswith(("- ", "* ", "+ ")):
                text.insert("end", "•  ", "bullet")
                self._insert_inline(text, stripped[2:], base_tag="bullet")
                text.insert("end", "\n")
            elif re.match(r"^\d+\.\s", stripped):
                text.insert("end", "   " + stripped + "\n")
            else:
                self._insert_inline(text, line)
                text.insert("end", "\n")

        box.configure(state="disabled")

    def _insert_inline(self, text, content: str, base_tag: str = "") -> None:
        """Handle inline `code` and **bold** within a line."""
        # Split on inline code first, then bold inside the plain segments.
        parts = re.split(r"(`[^`]+`)", content)
        for part in parts:
            if part.startswith("`") and part.endswith("`") and len(part) > 1:
                text.insert("end", part[1:-1], "code_inline")
            else:
                for seg in re.split(r"(\*\*[^*]+\*\*)", part):
                    if seg.startswith("**") and seg.endswith("**") and len(seg) > 2:
                        tags = ("bold",) + ((base_tag,) if base_tag else ())
                        text.insert("end", seg[2:-2], tags)
                    elif seg:
                        text.insert("end", seg, base_tag)

    def _show_welcome(self) -> None:
        welcome = (
            "# Code Reviewer\n\n"
            "Automated source code review for **Clean Code**, **SOLID** "
            "principles, **security** vulnerabilities and **performance** issues, "
            "powered by Llama 3 via Groq.\n\n"
            "## Getting started\n"
            "- Select a **folder** or individual **files** on the left.\n"
            "- Make sure your **Groq API key** is configured (top-right).\n"
            "- Click **Run Analysis** to review the results here.\n\n"
            "A full Markdown report is also saved to the `output/` directory.\n"
        )
        self._render_markdown(welcome)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------
    def _choose_folder(self) -> None:
        directory = filedialog.askdirectory(title="Select a folder to analyze")
        if not directory:
            return
        try:
            files_data = LocalFileReader.read_directory(directory)
        except FileNotFoundError as exc:
            messagebox.showerror("Invalid folder", str(exc))
            return

        if not files_data:
            messagebox.showwarning(
                "No supported files",
                "No supported source files were found in that folder.",
            )
            return

        self.selected_files = [Path(p) for p in files_data.keys()]
        self._refresh_file_list()
        self._set_status(f"{len(self.selected_files)} file(s) ready from folder.")

    def _choose_files(self) -> None:
        exts = LocalFileReader.SUPPORTED_EXTENSIONS
        patterns = " ".join(f"*{e}" for e in sorted(exts))
        paths = filedialog.askopenfilenames(
            title="Select source files",
            filetypes=[("Source files", patterns), ("All files", "*.*")],
        )
        if not paths:
            return
        chosen = [
            Path(p) for p in paths
            if Path(p).suffix in LocalFileReader.SUPPORTED_EXTENSIONS
        ]
        if not chosen:
            messagebox.showwarning(
                "Unsupported files",
                "None of the selected files have a supported extension.",
            )
            return
        # Merge without duplicates, preserving order
        existing = {str(p) for p in self.selected_files}
        for p in chosen:
            if str(p) not in existing:
                self.selected_files.append(p)
        self._refresh_file_list()
        self._set_status(f"{len(self.selected_files)} file(s) ready.")

    def _refresh_file_list(self) -> None:
        for widget in self.file_list.winfo_children():
            widget.destroy()
        self._file_buttons.clear()

        if not self.selected_files:
            self.empty_hint = ctk.CTkLabel(
                self.file_list,
                text="No files selected yet.\nChoose a folder or files to begin.",
                font=ctk.CTkFont(size=12),
                text_color=TEXT_MUTED,
                justify="center",
            )
            self.empty_hint.grid(row=0, column=0, pady=30)
            return

        for i, path in enumerate(self.selected_files):
            key = str(path)
            btn = ctk.CTkButton(
                self.file_list,
                text=f"   {path.name}",
                anchor="w",
                height=32,
                fg_color="transparent",
                hover_color=SURFACE_2,
                text_color="#D1D5DB",
                command=lambda k=key: self._show_review_for(k),
            )
            btn.grid(row=i, column=0, sticky="ew", pady=1)
            self._file_buttons[key] = btn

    # ------------------------------------------------------------------
    # Analysis (threaded)
    # ------------------------------------------------------------------
    def _start_analysis(self) -> None:
        if self._is_running:
            return
        if not self.selected_files:
            messagebox.showinfo("Nothing to analyze", "Please select files or a folder first.")
            return
        if not Config.GROQ_API_KEY and not os.getenv("GROQ_API_KEY"):
            messagebox.showwarning(
                "Missing API key",
                "Please set your Groq API key (top-right API Key button) first.",
            )
            self._open_api_dialog()
            return

        self._is_running = True
        self.reviews.clear()
        self.report_path = None
        self.analyze_btn.configure(state="disabled", text="Analyzing…")
        self.open_report_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress.set(0)

        thread = threading.Thread(target=self._run_analysis_worker, daemon=True)
        thread.start()

    def _run_analysis_worker(self) -> None:
        """Runs on a background thread. UI updates are marshalled via self.after."""
        try:
            client = GroqClient()
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._fail(f"Could not initialize AI client: {exc}"))
            return

        files = list(self.selected_files)
        total = len(files)
        reviews: Dict[str, str] = {}

        for idx, path in enumerate(files, start=1):
            key = str(path)
            self.after(0, lambda n=path.name, i=idx, t=total:
                       self._set_status(f"Analyzing {n}  ({i}/{t})…"))
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                reviews[key] = f"Error: could not read file. {exc}"
                self.after(0, lambda p=idx, t=total: self.progress.set(p / t))
                continue

            review = client.analyze_code(key, content)
            reviews[key] = review
            self.after(0, lambda p=idx, t=total: self.progress.set(p / t))

        # Generate the markdown report using the existing generator
        report_path = ReportGenerator.generate_markdown_report(reviews)
        self.after(0, lambda: self._finish(reviews, report_path))

    def _finish(self, reviews: Dict[str, str], report_path: str) -> None:
        self.reviews = reviews
        self.report_path = report_path or None
        self._is_running = False
        self.analyze_btn.configure(state="normal", text="Run Analysis")
        self.progress.set(1)

        if self.report_path:
            self.open_report_btn.configure(state="normal")
            self.open_folder_btn.configure(state="normal")
            self._set_status(f"Done — report saved to {self.report_path}", ok=True)
        else:
            self._set_status("Analysis finished, but report could not be saved.", warn=True)

        # Mark file buttons that produced errors, and show the first review
        for key, btn in self._file_buttons.items():
            review = reviews.get(key, "")
            if review.startswith("Error:"):
                btn.configure(text_color=DANGER)
            else:
                btn.configure(text_color=SUCCESS)

        if reviews:
            first_key = next(iter(reviews))
            self._show_review_for(first_key)

    def _fail(self, message: str) -> None:
        self._is_running = False
        self.analyze_btn.configure(state="normal", text="Run Analysis")
        self.progress.set(0)
        self._set_status(message, warn=True)
        messagebox.showerror("Analysis failed", message)

    def _show_review_for(self, key: str) -> None:
        review = self.reviews.get(key)
        if review is None:
            return
        self.active_file = key
        self.result_title.configure(text=Path(key).name)
        self._render_markdown(f"## File: `{key}`\n\n{review}")
        # Highlight active file button
        for k, btn in self._file_buttons.items():
            btn.configure(fg_color=SURFACE_2 if k == key else "transparent")

    # ------------------------------------------------------------------
    # API key dialog
    # ------------------------------------------------------------------
    def _open_api_dialog(self) -> None:
        dialog = ctk.CTkInputDialog(
            title="Groq API Key",
            text="Enter your Groq API key (starts with gsk_):",
        )
        value = dialog.get_input()
        if value:
            value = value.strip()
            os.environ["GROQ_API_KEY"] = value
            Config.GROQ_API_KEY = value
            self._refresh_api_status()
            self._set_status("API key updated for this session.", ok=True)

    def _refresh_api_status(self) -> None:
        has_key = bool(Config.GROQ_API_KEY or os.getenv("GROQ_API_KEY"))
        if has_key:
            self.api_badge.configure(text="● API key set", text_color=SUCCESS)
        else:
            self.api_badge.configure(text="● API key missing", text_color=DANGER)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _open_report(self) -> None:
        if self.report_path and os.path.exists(self.report_path):
            self._open_path(self.report_path)

    def _open_output_folder(self) -> None:
        if self.report_path:
            self._open_path(str(Path(self.report_path).parent))

    @staticmethod
    def _open_path(target: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", target], check=False)
            else:
                subprocess.run(["xdg-open", target], check=False)
        except Exception:  # noqa: BLE001
            webbrowser.open(Path(target).as_uri())

    def _clear_all(self) -> None:
        if self._is_running:
            return
        self.selected_files.clear()
        self.reviews.clear()
        self.report_path = None
        self.active_file = None
        self._refresh_file_list()
        self.result_title.configure(text="Review")
        self.open_report_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress.set(0)
        self._show_welcome()
        self._set_status("Ready.")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _set_status(self, message: str, ok: bool = False, warn: bool = False) -> None:
        color = SUCCESS if ok else (DANGER if warn else TEXT_MUTED)
        self.status_label.configure(text=message, text_color=color)


def main() -> None:
    app = CodeReviewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
