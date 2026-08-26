"""Searchable browser for the transcription history.

The arrow buttons in the main window step through history one entry at a time,
which is fine for "what did I just say" and useless for "what did I dictate
about the invoice on Tuesday". This dialog lists everything at once, filters as
you type, and can put any entry back into the main window.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta

from utils.app_logging import get_logger
from utils.i18n import _
from utils.theme import get_font, get_window_size, get_spacing

logger = get_logger(__name__)

# Filtering runs on every keystroke, so it is debounced rather than done
# inline - with a few thousand entries the difference is visible.
SEARCH_DEBOUNCE_MS = 120

# Preview text is a single line; anything longer is elided in the list.
PREVIEW_LENGTH = 120

# Populating a Treeview costs real time per row, and the history limit can be
# set as high as 10,000. Only this many rows are built; narrowing the search is
# how you reach the rest, and the count line always says what was left out.
MAX_ROWS = 300


class HistoryDialog:
    """A list of history entries with live search and a full-text preview."""

    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.withdraw()
        self.dialog.title(_("Transcription History"))

        width, height = get_window_size('history_dialog')
        self.dialog.geometry(f"{width}x{height}")
        self.dialog.minsize(560, 380)
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)

        # Tree row -> the history entry object it shows. Deliberately not the
        # position: a transcription finishing while this dialog is open can
        # trim the oldest entries and shift every index down.
        self._row_to_entry = {}
        self._rows = None
        self._indexed_length = 0
        self._search_after_id = None
        self._search_var = tk.StringVar()

        self._build()
        self._centre_on_parent(width, height)

        self.dialog.protocol("WM_DELETE_WINDOW", self.close)
        self.dialog.bind("<Escape>", lambda e: self.close())

        # The search box is a text field, so the global shortcuts have to stand
        # down while this dialog is in front - the same treatment the prompt
        # editor gets.
        if hasattr(self.parent, 'hotkey_manager'):
            self.parent.hotkey_manager.pause()

        self.refresh()
        self.dialog.deiconify()
        try:
            self.dialog.wait_visibility()
            self.dialog.grab_set()
        except tk.TclError as e:
            logger.debug("Could not grab the history dialog: %s", e)
        self.search_entry.focus_set()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _centre_on_parent(self, width, height):
        try:
            x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
            self.dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        except Exception as e:
            logger.debug("Could not centre the history dialog: %s", e)

    def _build(self):
        pad = get_spacing('md')
        container = ttk.Frame(self.dialog, padding=(pad, pad))
        container.pack(fill=tk.BOTH, expand=True)

        # ── Search ───────────────────────────────────────────────────────
        search_row = ttk.Frame(container)
        search_row.pack(fill=tk.X, pady=(0, get_spacing('sm')))

        ttk.Label(search_row, text=_("Search"), font=get_font('sm', 'bold')).pack(side=tk.LEFT)

        self.search_entry = ttk.Entry(search_row, textvariable=self._search_var, font=get_font('sm'))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(get_spacing('sm'), 0))
        self._search_var.trace_add("write", lambda *a: self._schedule_filter())
        # Down arrow from the search box moves into the results, so the whole
        # dialog can be driven from the keyboard.
        self.search_entry.bind("<Down>", self._focus_results)
        self.search_entry.bind("<Return>", self._focus_results)

        self.clear_search = ttk.Label(
            search_row, text="✕", cursor="hand2", font=get_font('sm'))
        self.clear_search.pack(side=tk.LEFT, padx=(get_spacing('sm'), 0))
        self.clear_search.bind("<Button-1>", lambda e: self._search_var.set(""))

        # ── Results ──────────────────────────────────────────────────────
        results_frame = ttk.Frame(container)
        results_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("when", "type", "prompt", "preview")
        self.tree = ttk.Treeview(
            results_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("when", text=_("When"))
        self.tree.heading("type", text=_("Type"))
        self.tree.heading("prompt", text=_("Prompt"))
        self.tree.heading("preview", text=_("Text"))
        self.tree.column("when", width=140, minwidth=110, stretch=False)
        self.tree.column("type", width=90, minwidth=70, stretch=False)
        self.tree.column("prompt", width=110, minwidth=80, stretch=False)
        self.tree.column("preview", width=380, minwidth=160, stretch=True)

        tree_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_selected())
        self.tree.bind("<Double-1>", lambda e: self.load_selected())
        self.tree.bind("<Return>", lambda e: self.load_selected())

        # ── Preview ──────────────────────────────────────────────────────
        self.status_label = ttk.Label(container, text="", font=get_font('xxs'), foreground="#888888")
        self.status_label.pack(anchor="w", pady=(get_spacing('sm'), 2))

        preview_frame = ttk.Frame(container)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        self.preview = tk.Text(
            preview_frame, height=6, wrap="word", font=get_font('sm'),
            relief="flat", borderwidth=0, highlightthickness=1,
            highlightbackground="#404040", padx=10, pady=8)
        preview_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview.yview)
        self.preview.configure(yscrollcommand=preview_scroll.set, state="disabled")
        self.preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._style_preview()

        # ── Buttons ──────────────────────────────────────────────────────
        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=(get_spacing('md'), 0))

        ttk.Button(button_row, text=_("Close"), command=self.close).pack(side=tk.RIGHT)
        self.load_button = ttk.Button(
            button_row, text=_("Show in Main Window"), command=self.load_selected)
        self.load_button.pack(side=tk.RIGHT, padx=(0, get_spacing('sm')))
        self.copy_button = ttk.Button(
            button_row, text=_("Copy"), command=self.copy_selected)
        self.copy_button.pack(side=tk.RIGHT, padx=(0, get_spacing('sm')))
        self._set_buttons_enabled(False)

    def _style_preview(self):
        """Match the preview box to the main transcription area."""
        try:
            from utils.config_manager import get_config
            if get_config().dark_mode:
                self.preview.configure(bg="#1c1c1c", fg="#ffffff", highlightbackground="#404040")
            else:
                self.preview.configure(bg="#ffffff", fg="#1c1c1c", highlightbackground="#d0d0d0")
        except Exception as e:
            logger.debug("Could not theme the history preview: %s", e)

    # ------------------------------------------------------------------
    # Filtering and display
    # ------------------------------------------------------------------

    def _schedule_filter(self):
        if self._search_after_id is not None:
            try:
                self.dialog.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.dialog.after(SEARCH_DEBOUNCE_MS, self.refresh)

    def refresh(self):
        """Rebuild the list from the current search text."""
        self._search_after_id = None
        if not self.dialog.winfo_exists():
            return

        query = (self._search_var.get() or "").strip().lower()
        words = query.split()
        self.tree.delete(*self.tree.get_children())
        self._row_to_entry.clear()

        rows = self._index_rows()
        total = len(rows)
        matched = 0
        truncated = False
        # Newest first: the entry you want is nearly always a recent one.
        for entry, haystack, values in rows:
            if words and not all(word in haystack for word in words):
                continue
            matched += 1
            if matched > MAX_ROWS:
                truncated = True
                continue
            self._row_to_entry[self.tree.insert("", tk.END, values=values)] = entry

        if query:
            text = _("{shown} of {total} entries match '{query}'").format(
                shown=matched, total=total, query=self._search_var.get().strip())
        else:
            text = _("{total} entries").format(total=total)
        if truncated:
            text += "  —  " + _("showing the newest {count}; narrow the search to see more").format(
                count=MAX_ROWS)
        self.status_label.configure(text=text)

        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self._show_selected()
        else:
            self._set_preview_text("")
            self._set_buttons_enabled(False)

    def _index_rows(self):
        """Rows to display, newest first, as (entry, searchable text, columns).

        Built once rather than on every keystroke: the column formatting and
        the lowercased search text do not change while the dialog is up, and
        rebuilding them per keystroke is what makes a large history sluggish to
        search. Rebuilt if the history itself changed underneath us - a
        recording started before this dialog opened can still finish while it
        is up.
        """
        if self._rows is not None and self._indexed_length == len(self.parent.history):
            return self._rows

        rows = []
        for index in range(len(self.parent.history) - 1, -1, -1):
            entry = self.parent.history_entry(index)
            if entry is None:
                continue
            when = self._format_when(entry.get("timestamp"))
            mode = self._format_mode(entry.get("mode"))
            prompt = entry.get("prompt") or "—"
            text = entry.get("text", "")
            haystack = " ".join((text, prompt, mode, when)).lower()
            rows.append((entry, haystack, (when, mode, prompt, self._format_preview(text))))

        self._rows = rows
        self._indexed_length = len(self.parent.history)
        return rows

    def _matches(self, entry, query):
        """Whether one entry matches a search query.

        Kept as the single definition of "matches" - :meth:`_index_rows` builds
        the same haystack up front for the list itself.
        """
        query = (query or "").strip().lower()
        if not query:
            return True
        haystack = " ".join(filter(None, (
            entry.get("text", ""),
            entry.get("prompt") or "",
            self._format_mode(entry.get("mode")),
            self._format_when(entry.get("timestamp")),
        ))).lower()
        # Every word has to appear somewhere, so "email tuesday" narrows down
        # rather than matching either term.
        return all(word in haystack for word in query.split())

    def _format_mode(self, mode):
        if mode == self.parent.HISTORY_MODE_EDIT:
            return _("AI edit")
        if mode == self.parent.HISTORY_MODE_TRANSCRIPT:
            return _("Transcript")
        return "—"

    @staticmethod
    def _format_when(timestamp):
        """Render a timestamp as something scannable in a list."""
        if not timestamp:
            return "—"
        try:
            moment = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            return str(timestamp)
        today = date.today()
        if moment.date() == today:
            return _("Today {time}").format(time=moment.strftime("%H:%M"))
        if moment.date() == today - timedelta(days=1):
            return _("Yesterday {time}").format(time=moment.strftime("%H:%M"))
        return moment.strftime("%d %b %H:%M")

    @staticmethod
    def _format_preview(text):
        single_line = " ".join((text or "").split())
        if len(single_line) <= PREVIEW_LENGTH:
            return single_line
        return single_line[:PREVIEW_LENGTH - 1] + "…"

    def _focus_results(self, _event=None):
        children = self.tree.get_children()
        if children:
            self.tree.focus_set()
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
        return "break"

    def _selected_entry(self):
        """The history entry for the selected row, or None."""
        selection = self.tree.selection()
        if not selection:
            return None
        return self._row_to_entry.get(selection[0])

    def _selected_index(self):
        """Where the selected entry currently sits in the history.

        Resolved by identity at the moment it is needed, so trimming that
        happened after the list was drawn cannot make this point at the wrong
        entry.
        """
        entry = self._selected_entry()
        if entry is None:
            return None
        for index, candidate in enumerate(self.parent.history):
            if candidate is entry:
                return index
        return None

    def _show_selected(self):
        entry = self._selected_entry()
        if entry is None:
            self._set_preview_text("")
            self._set_buttons_enabled(False)
            return
        self._set_preview_text(entry.get("text", ""))
        self._set_buttons_enabled(True)

    def _set_preview_text(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", tk.END)
        if text:
            self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for button in (self.load_button, self.copy_button):
            try:
                button.configure(state=state)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load_selected(self):
        """Put the selected entry back into the main window and close."""
        index = self._selected_index()
        if index is None:
            # The entry was trimmed out of the history while this was open.
            self.refresh()
            return
        self.parent.load_history_entry(index)
        self.close()

    def copy_selected(self):
        entry = self._selected_entry()
        text = (entry or {}).get("text", "")
        if not text:
            return
        self.parent.copy_to_clipboard(text)

    def close(self):
        try:
            if self._search_after_id is not None:
                self.dialog.after_cancel(self._search_after_id)
        except Exception:
            pass
        self._search_after_id = None
        try:
            self.dialog.destroy()
        finally:
            if hasattr(self.parent, 'hotkey_manager'):
                self.parent.hotkey_manager.resume()
