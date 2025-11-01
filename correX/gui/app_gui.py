"""Optimized GUI for CorreX with proper asset usage and modern design."""
from __future__ import annotations

import os
import queue
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, TYPE_CHECKING, Callable

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None  # type: ignore

from ..autocorrect_service import AutoCorrectService
from ..gemini_corrector import GeminiCorrector
from ..loading_overlay import LoadingOverlay
from ..asset_manager import get_asset_manager

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from ..history_manager import HistoryManager
else:
    try:
        from ..config_manager import ConfigManager
        from ..history_manager import HistoryManager
    except ImportError:
        ConfigManager = HistoryManager = None

_ACTIVE_ROOT: Optional[tk.Tk] = None
_UI_COMMANDS: "queue.Queue[Callable[[], None]]" = queue.Queue(maxsize=128)
_UI_READY = threading.Event()

# Modern color palette
COLORS = {
    'bg_primary': '#FFFFFF',
    'bg_secondary': '#F8F9FA',
    'bg_dark': '#1A1F2E',
    'accent_primary': '#6366F1',  # Indigo
    'accent_hover': '#4F46E5',
    'text_primary': '#1F2937',
    'text_secondary': '#6B7280',
    'text_light': '#9CA3AF',
    'border': '#E5E7EB',
    'success': '#10B981',
    'warning': '#F59E0B',
    'error': '#EF4444',
    'card_shadow': '#00000010',
    'header_bg': '#EEF2FF',
    'chip_bg': '#E0E7FF',
    'chip_text': '#3730A3',
}

MAX_CANDIDATES = getattr(GeminiCorrector, "MAX_CANDIDATES", 5)

if hasattr(GeminiCorrector, "get_tone_options"):
    _TONE_OPTIONS_RAW = GeminiCorrector.get_tone_options()
else:
    _TONE_OPTIONS_RAW = [
        {
            "key": "original",
            "label": "Original (Minimal change)",
            "description": "Fixes grammar and punctuation without altering the author's voice.",
        },
        {
            "key": "professional",
            "label": "Professional",
            "description": "Concise, confident tone suitable for workplace communication.",
        },
        {
            "key": "formal",
            "label": "Formal",
            "description": "Polished, precise tone for official or academic writing.",
        },
        {
            "key": "informal",
            "label": "Informal",
            "description": "Relaxed, conversational voice for casual updates.",
        },
        {
            "key": "detailed",
            "label": "Detailed",
            "description": "Enhance clarity with moderate elaboration and sensible formatting.",
        },
        {
            "key": "creative",
            "label": "Creative",
            "description": "Expressive tone with varied rhythm and vivid wording.",
        },
    ]

TONE_OPTIONS = _TONE_OPTIONS_RAW
TONE_LABEL_MAP = {opt["key"]: opt.get("label", opt["key"].title()) for opt in TONE_OPTIONS}
TONE_DESCRIPTION_MAP = {opt["key"]: opt.get("description", "") for opt in TONE_OPTIONS}
TONE_LABEL_TO_KEY = {opt.get("label", opt["key"].title()): opt["key"] for opt in TONE_OPTIONS}
VALID_TONE_KEYS = {opt["key"].lower() for opt in TONE_OPTIONS}


def focus_existing_window() -> bool:
    """Bring the existing GUI window to front if it is already open."""
    global _ACTIVE_ROOT

    if not (_ACTIVE_ROOT and _UI_READY.is_set()):
        return False

    def _focus():
        try:
            if _ACTIVE_ROOT and _ACTIVE_ROOT.winfo_exists():
                _ACTIVE_ROOT.deiconify()
                try:
                    _ACTIVE_ROOT.state('normal')
                except tk.TclError:
                    pass
                _ACTIVE_ROOT.lift()
                _ACTIVE_ROOT.focus_force()
        except tk.TclError:
            pass

    try:
        _UI_COMMANDS.put_nowait(_focus)
        return True
    except queue.Full:
        print("[WARNING] UI task queue full; cannot focus window right now")
        return False


def _drain_ui_queue(window: tk.Tk) -> None:
    """Process queued UI callbacks on the GUI thread."""
    while True:
        try:
            task = _UI_COMMANDS.get_nowait()
        except queue.Empty:
            break
        try:
            task()
        except Exception as task_error:
            print(f"[WARNING] UI task failed: {task_error}")
    try:
        window.after(40, lambda: _drain_ui_queue(window))
    except tk.TclError:
        _reset_ui_channel()


def _reset_ui_channel() -> None:
    """Reset coordination primitives used for cross-thread UI scheduling."""
    _UI_READY.clear()
    while True:
        try:
            _UI_COMMANDS.get_nowait()
        except queue.Empty:
            break


def _load_assets(asset_manager, header_size: int = 52):
    """Load GUI and system assets separately using asset manager."""
    header_image = None
    header_candidates = [
        (asset_manager.load_image, "CorreX_GUI_logo.png"),
        (asset_manager.load_icon, "CorreX_GUI_logo.png"),
        (asset_manager.load_icon, "CorreX_GUI_logo.ico"),
        (asset_manager.load_icon, "CorreX_logo.png"),
        (asset_manager.load_icon, "CorreX_logo.ico"),
    ]

    for loader, asset_name in header_candidates:
        cache_key = f"gui_header_{asset_name}_{header_size}"
        try:
            header_image = loader(asset_name, size=(header_size, header_size), cache_key=cache_key)  # type: ignore[arg-type]
        except TypeError:
            # load_image signature differs slightly; retry without cache override
            header_image = loader(asset_name, size=(header_size, header_size))  # type: ignore[arg-type]
        if header_image:
            break

    icon_sizes = (256, 128, 64, 48, 32, 16)
    icon_variants: list[tk.PhotoImage] = []
    icon_sources = ["CorreX_logo.png", "CorreX_logo.ico", "CorreX_GUI_logo.ico"]

    for size in icon_sizes:
        loaded_variant = None
        for name in icon_sources:
            loaded_variant = asset_manager.load_icon(name, size=(size, size), cache_key=f"sys_icon_{name}_{size}")
            if loaded_variant:
                icon_variants.append(loaded_variant)
                break
        if not loaded_variant:
            continue

    ico_path = asset_manager.create_ico_from_png("CorreX_logo.png", "CorreX_icon.ico")
    if not ico_path:
        ico_path = asset_manager.get_icon_path("CorreX_logo.ico")

    return header_image, icon_variants, ico_path


class ModernCard(tk.Frame):
    """A modern card component with enhanced shadow effect."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_primary'], **kwargs)
        # Enhanced border for better depth
        self.configure(
            highlightthickness=1, 
            highlightbackground=COLORS['border'],
            relief='flat'
        )
        
        # Add subtle shadow effect using additional border
        self._shadow_frame = tk.Frame(parent, bg='#E0E0E0', height=2)
    
    def pack(self, **kwargs):
        """Override pack to add shadow."""
        super().pack(**kwargs)
        # Pack shadow below card
        pady = kwargs.get('pady', (0, 0))
        if isinstance(pady, int):
            pady = (pady, pady)
        self._shadow_frame.pack(fill='x', padx=32, pady=(0, pady[1]-1) if pady[1] > 0 else (0, 0))


class ModernButton(tk.Button):
    """A modern styled button with hover effects."""
    def __init__(self, parent, text="", command=None, style="primary", **kwargs):
        if style == "primary":
            bg = COLORS['accent_primary']
            fg = '#FFFFFF'
            hover_bg = COLORS['accent_hover']
        elif style == "secondary":
            bg = COLORS['bg_secondary']
            fg = COLORS['text_primary']
            hover_bg = COLORS['border']
        elif style == "success":
            bg = COLORS['success']
            fg = '#FFFFFF'
            hover_bg = '#059669'
        elif style == "danger":
            bg = COLORS['error']
            fg = '#FFFFFF'
            hover_bg = '#DC2626'
        else:
            bg = COLORS['bg_secondary']
            fg = COLORS['text_primary']
            hover_bg = COLORS['border']
        
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            font=('Segoe UI', 10, 'normal'),
            relief='flat',
            padx=20,
            pady=10,
            cursor='hand2',
            borderwidth=0,
            **kwargs
        )
        
        self.default_bg = bg
        self.hover_bg = hover_bg
        
        self.bind('<Enter>', lambda e: self.configure(bg=self.hover_bg))
        self.bind('<Leave>', lambda e: self.configure(bg=self.default_bg))


class StatusBadge(tk.Label):
    """A status badge component."""
    def __init__(self, parent, text="", status="inactive", **kwargs):
        if status == "active":
            bg = COLORS['success']
            fg = '#FFFFFF'
        elif status == "warning":
            bg = COLORS['warning']
            fg = '#FFFFFF'
        else:
            bg = COLORS['error']
            fg = '#FFFFFF'
        
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=('Segoe UI', 9, 'bold'),
            padx=12,
            pady=4,
            **kwargs
        )


def launch_app(
    *,
    service: AutoCorrectService,
    corrector: Optional[GeminiCorrector] = None,
    config: Optional["ConfigManager"] = None,
    history: Optional["HistoryManager"] = None,
    keep_service_running: bool = False,
    on_close: Optional[Callable[[], None]] = None,
) -> None:
    """Launch the modern, professional configuration GUI."""
    global _ACTIVE_ROOT

    if keep_service_running and focus_existing_window():
        return

    _reset_ui_channel()

    base_root = tk.Tk()
    base_root.withdraw()

    window = tk.Toplevel(base_root)
    _ACTIVE_ROOT = window
    window.title("CorreX - AI Text Correction")
    
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate responsive window size (70% of screen or default)
    window_width = max(980, min(int(screen_width * 0.7), 1400))
    window_height = max(760, min(int(screen_height * 0.8), 1000))
    
    # Proper resizing constraints
    window.minsize(900, 720)
    window.maxsize(screen_width, screen_height)
    window.resizable(True, True)
    window.configure(bg=COLORS['bg_secondary'])
    
    # Configure grid weight for proper resizing
    window.grid_rowconfigure(0, weight=1)
    window.grid_columnconfigure(0, weight=1)
    
    # Set initial geometry (will be centered after layout)
    window.geometry(f"{window_width}x{window_height}")
    
    # Load assets using asset manager
    asset_manager = get_asset_manager()
    asset_manager.clear_cache()
    header_logo, icon_variants, icon_path = _load_assets(asset_manager)
    
    # Set taskbar icon first (Windows specific)
    if os.name == "nt":
        # Try to set icon from multiple sources
        icon_set_successfully = False
        
        # Try the generated/loaded icon path first
        if icon_path:
            try:
                window.iconbitmap(str(icon_path))
                base_root.iconbitmap(str(icon_path))
                icon_set_successfully = True
                print(f"[INFO] Icon set successfully from: {icon_path}")
            except Exception as icon_error:
                print(f"[WARNING] Failed to apply ICO icon from {icon_path}: {icon_error}")
        
        # Fallback: Try direct path to CorreX_logo.ico
        if not icon_set_successfully:
            try:
                direct_icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "CorreX_logo.ico"
                if direct_icon_path.exists():
                    window.iconbitmap(str(direct_icon_path))
                    base_root.iconbitmap(str(direct_icon_path))
                    icon_set_successfully = True
                    print(f"[INFO] Icon set successfully from direct path: {direct_icon_path}")
            except Exception as icon_error:
                print(f"[WARNING] Failed to apply ICO icon from direct path: {icon_error}")
    
    if icon_variants:
        try:
            base_root.iconphoto(True, *icon_variants)
            window.iconphoto(False, *icon_variants)
            window._icon_variants = icon_variants  # type: ignore[attr-defined]
            base_root._icon_variants = icon_variants  # type: ignore[attr-defined]
        except Exception as icon_error:
            print(f"[WARNING] Failed to apply window icons: {icon_error}")
    if header_logo:
        window._logo_image = header_logo  # type: ignore[attr-defined]

    if os.name == "nt":
        try:
            import ctypes

            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CorreX.App")
            except Exception:
                pass

            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            window.update_idletasks()
            hwnd = window.winfo_id()
            original_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (original_style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                None,
                0,
                0,
                0,
                0,
                0x0001 | 0x0002 | 0x0040,
            )
        except Exception as style_error:
            print(f"[WARNING] Failed to adjust window style: {style_error}")
    
    workspace_root = Path(__file__).resolve().parents[2]
    quick_start_path = workspace_root / "QUICK_START.md"
    readme_path = workspace_root / "README.md"

    trigger_key_initial = AutoCorrectService.normalize_trigger_key(
        (config.get("trigger_key", service.get_trigger_key()) if config else service.get_trigger_key())
    ) or service.get_trigger_key()

    dictation_key_initial = AutoCorrectService.normalize_trigger_key(
        (config.get("dictation_trigger_key", service.get_dictation_trigger_key()) if config else service.get_dictation_trigger_key())
    ) or service.get_dictation_trigger_key()

    raw_clear_initial = None
    if config:
        raw_clear_initial = config.get("clear_buffer_trigger_key", service.get_clear_buffer_trigger_key())
    else:
        raw_clear_initial = service.get_clear_buffer_trigger_key()
    clear_trigger_initial = AutoCorrectService.normalize_trigger_key(raw_clear_initial) if raw_clear_initial else ""

    paragraph_initial = (config.get("paragraph_enabled", service.paragraph_enabled) if config else service.paragraph_enabled)
    model_name_initial = config.get("model_name", "gemini-2.0-flash-exp") if config else "gemini-2.0-flash-exp"

    if hasattr(service, "get_versions_per_correction"):
        versions_initial = service.get_versions_per_correction()
    elif config:
        versions_initial = config.get("versions_per_correction", 3)
    else:
        versions_initial = 3
    versions_initial = max(1, min(versions_initial, MAX_CANDIDATES))

    raw_candidate_settings = None
    if hasattr(service, "get_candidate_settings"):
        try:
            raw_candidate_settings = service.get_candidate_settings()
        except Exception as candidate_error:
            print(f"[WARNING] Failed to fetch candidate settings from service: {candidate_error}")
    elif config:
        raw_candidate_settings = config.get("candidate_settings")

    fallback_defaults = (
        GeminiCorrector.default_candidate_settings()
        if hasattr(GeminiCorrector, "default_candidate_settings")
        else [
            {"temperature": 0.30, "tone": "original"},
            {"temperature": 0.55, "tone": "professional"},
            {"temperature": 0.60, "tone": "formal"},
            {"temperature": 0.65, "tone": "informal"},
            {"temperature": 0.80, "tone": "creative"},
        ]
    )

    if hasattr(GeminiCorrector, "normalize_candidate_settings"):
        candidate_settings_initial = GeminiCorrector.normalize_candidate_settings(raw_candidate_settings)
    else:
        if isinstance(raw_candidate_settings, list) and raw_candidate_settings:
            candidate_settings_initial = [dict(item) for item in raw_candidate_settings[:MAX_CANDIDATES]]
        else:
            candidate_settings_initial = [dict(item) for item in fallback_defaults]

    candidate_settings_initial = [dict(item) for item in candidate_settings_initial]
    if len(candidate_settings_initial) < MAX_CANDIDATES:
        fill_index = 0
        while len(candidate_settings_initial) < MAX_CANDIDATES:
            candidate_settings_initial.append(dict(fallback_defaults[fill_index % len(fallback_defaults)]))
            fill_index += 1
    elif len(candidate_settings_initial) > MAX_CANDIDATES:
        candidate_settings_initial = candidate_settings_initial[:MAX_CANDIDATES]

    is_configured = hasattr(corrector, 'is_configured') and corrector.is_configured

    trigger_chip_var = tk.StringVar(value=f"Correction Trigger: {trigger_key_initial.upper()}")
    dictation_chip_var = tk.StringVar(value=f"Dictation Trigger: {dictation_key_initial.upper()}")
    paragraph_chip_var = tk.StringVar(value="Paragraph Mode: On" if paragraph_initial else "Paragraph Mode: Off")
    candidate_chip_var = tk.StringVar(value=f"Candidates: {versions_initial}")
    model_summary_var = tk.StringVar(value=f"Model: {model_name_initial}")
    api_status_message = "Gemini connected" if is_configured else "API key not configured"
    if is_configured and model_name_initial:
        api_status_message = f"Gemini connected ({model_name_initial})"
    api_status_var = tk.StringVar(value=api_status_message)
    dictation_status_var = tk.StringVar()
    
    # Create main container with scrollable canvas and proper grid layout
    main_canvas = tk.Canvas(window, bg=COLORS['bg_secondary'], highlightthickness=0)
    scrollbar = tk.Scrollbar(window, orient="vertical", command=main_canvas.yview)
    scrollable_frame = tk.Frame(main_canvas, bg=COLORS['bg_secondary'])

    resize_job = {'id': None}

    def _schedule_canvas_width_sync():
        if resize_job['id'] is not None:
            try:
                window.after_cancel(resize_job['id'])
            except tk.TclError:
                pass
        resize_job['id'] = window.after(90, _sync_canvas_width)

    def _sync_canvas_width() -> None:
        try:
            new_width = max(main_canvas.winfo_width(), 400)
            main_canvas.itemconfig(canvas_window, width=new_width)
        except tk.TclError:
            pass

    def _configure_scroll_region(_event=None):
        try:
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        except tk.TclError:
            return
        _schedule_canvas_width_sync()

    canvas_window = main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    main_canvas.configure(yscrollcommand=scrollbar.set)

    scrollable_frame.bind("<Configure>", _configure_scroll_region)
    main_canvas.bind("<Configure>", lambda _event: _schedule_canvas_width_sync())
    window.bind("<Configure>", lambda _event: _schedule_canvas_width_sync())

    window.update_idletasks()
    _sync_canvas_width()

    # Grid layout for proper resizing
    main_canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    
    # Smooth mouse wheel scrolling
    def _on_mousewheel(event):
        main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _bind_mousewheel(event):
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def _unbind_mousewheel(event):
        main_canvas.unbind_all("<MouseWheel>")
    
    main_canvas.bind("<Enter>", _bind_mousewheel)
    main_canvas.bind("<Leave>", _unbind_mousewheel)
    
    scrollable_frame.grid_columnconfigure(0, weight=1)
    scrollable_frame.grid_rowconfigure(0, weight=1)

    # Main content area with padding
    content_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_secondary'])
    content_frame.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
    content_frame.grid_columnconfigure(0, weight=1)
    
    # ====================== HEADER ======================
    def open_quick_start():
        """Open Quick Start guide in a popup window."""
        target = None
        if quick_start_path.exists():
            target = quick_start_path
        elif readme_path.exists():
            target = readme_path
        
        if target is None:
            messagebox.showinfo("Documentation", "Quick start guide not found in workspace.")
            return
        
        # Create popup window
        popup = tk.Toplevel(window)
        popup.title("CorreX Quick Start Guide")
        popup.configure(bg=COLORS['bg_primary'])
        popup.transient(window)
        popup.grab_set()
        
        # Set window size and position
        popup_width = 800
        popup_height = 600
        popup.geometry(f"{popup_width}x{popup_height}")
        
        # Center the popup
        popup.update_idletasks()
        x = window.winfo_x() + (window.winfo_width() - popup_width) // 2
        y = window.winfo_y() + (window.winfo_height() - popup_height) // 2
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # Create scrollable text widget
        text_frame = tk.Frame(popup, bg=COLORS['bg_primary'])
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        text_scroll = tk.Scrollbar(text_frame)
        text_scroll.pack(side='right', fill='y')
        
        text_widget = tk.Text(
            text_frame,
            wrap='word',
            font=('Segoe UI', 10),
            bg=COLORS['bg_primary'],
            fg=COLORS['text_primary'],
            padx=15,
            pady=15,
            yscrollcommand=text_scroll.set,
            relief='flat',
            borderwidth=0
        )
        text_widget.pack(side='left', fill='both', expand=True)
        text_scroll.config(command=text_widget.yview)
        
        # Read and display content
        try:
            with open(target, 'r', encoding='utf-8') as f:
                content = f.read()
            text_widget.insert('1.0', content)
            text_widget.config(state='disabled')
            
            # Configure text tags for better formatting
            text_widget.tag_configure('heading', font=('Segoe UI', 14, 'bold'), foreground=COLORS['accent_primary'])
            text_widget.tag_configure('subheading', font=('Segoe UI', 12, 'bold'))
            text_widget.tag_configure('code', font=('Consolas', 9), background=COLORS['bg_secondary'])
            
        except Exception as e:
            text_widget.insert('1.0', f"Error reading guide: {e}")
            text_widget.config(state='disabled')
        
        # Close button
        close_btn = ModernButton(popup, text="Close", command=popup.destroy, style="secondary")
        close_btn.pack(pady=(0, 20))

    header_card = ModernCard(content_frame)
    header_card.pack(fill="x", pady=(0, 20))

    header_shell = tk.Frame(header_card, bg=COLORS['header_bg'])
    header_shell.pack(fill="both", expand=True)

    accent_bar = tk.Frame(header_shell, bg=COLORS['accent_primary'], height=3)
    accent_bar.pack(fill="x", side="top")

    header_content = tk.Frame(header_shell, bg=COLORS['header_bg'])
    header_content.pack(fill="both", padx=28, pady=24)

    top_row = tk.Frame(header_content, bg=COLORS['header_bg'])
    top_row.pack(fill="x")

    hero_column = tk.Frame(top_row, bg=COLORS['header_bg'])
    hero_column.pack(side="left", fill="both", expand=True, padx=(0, 14))

    if header_logo:
        logo_wrapper = tk.Frame(hero_column, bg=COLORS['header_bg'])
        logo_wrapper.pack(anchor="w", pady=(0, 12))
        logo_label = tk.Label(logo_wrapper, image=header_logo, bg=COLORS['header_bg'], cursor='hand2')
        logo_label.image = header_logo
        logo_label.pack(side="left")

        def _logo_enter(_event):
            logo_label.config(bg='#E5E7FF')

        def _logo_leave(_event):
            logo_label.config(bg=COLORS['header_bg'])

        logo_label.bind('<Enter>', _logo_enter)
        logo_label.bind('<Leave>', _logo_leave)
        logo_label.bind('<Button-1>', lambda _e: open_quick_start())

    app_title = tk.Label(
        hero_column,
        text="CorreX Control Center",
        font=('Segoe UI', 26, 'bold'),
        fg=COLORS['accent_primary'],
        bg=COLORS['header_bg']
    )
    app_title.pack(anchor="w")

    app_subtitle = tk.Label(
        hero_column,
        text="Configure AI corrections, keyboard triggers, and voice dictation from a single streamlined dashboard.",
        font=('Segoe UI', 10),
        fg=COLORS['text_primary'],
        bg=COLORS['header_bg'],
        justify='left'
    )
    app_subtitle.pack(anchor="w", pady=(6, 0), fill='x')

    hero_hint = tk.Label(
        hero_column,
        text="Powered by Google Gemini with realtime microphone dictation",
        font=('Segoe UI', 9, 'bold'),
        fg=COLORS['chip_text'],
        bg=COLORS['header_bg']
    )
    hero_hint.pack(anchor="w", pady=(10, 0))

    hero_actions = tk.Frame(hero_column, bg=COLORS['header_bg'])
    hero_actions.pack(anchor="w", pady=(18, 0))

    docs_btn = ModernButton(hero_actions, text="Open Quick Start Guide", command=open_quick_start, style="primary")
    docs_btn.pack(side="left")

    status_column = tk.Frame(top_row, bg=COLORS['header_bg'])
    status_column.pack(side="right", anchor="n")

    status_panel = tk.Frame(status_column, bg=COLORS['bg_primary'], highlightthickness=1, highlightbackground=COLORS['border'])
    status_panel.pack(anchor="e", pady=(0, 6))

    status_inner = tk.Frame(status_panel, bg=COLORS['bg_primary'])
    status_inner.pack(fill="both", padx=18, pady=16)

    status_title = tk.Label(
        status_inner,
        text="Service Status",
        font=('Segoe UI', 11, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    status_title.pack(anchor="w")

    status_badge = StatusBadge(
        status_inner,
        text="● Active" if is_configured else "● Inactive",
        status="active" if is_configured else "inactive"
    )
    status_badge.pack(anchor="w", pady=(10, 8))

    api_state_label = tk.Label(
        status_inner,
        textvariable=api_status_var,
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary']
    )
    api_state_label.pack(anchor="w")

    dictation_state_label = tk.Label(
        status_inner,
        textvariable=dictation_status_var,
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary']
    )
    dictation_state_label.pack(anchor="w", pady=(4, 0))

    chip_row = tk.Frame(header_content, bg=COLORS['header_bg'])
    chip_row.pack(fill="x", pady=(22, 0))

    chip_vars = [trigger_chip_var, dictation_chip_var, paragraph_chip_var, candidate_chip_var, model_summary_var]
    for idx, var in enumerate(chip_vars):
        chip_label = tk.Label(
            chip_row,
            textvariable=var,
            font=('Segoe UI', 9, 'bold'),
            fg=COLORS['chip_text'],
            bg=COLORS['chip_bg'],
            padx=14,
            pady=6
        )
        chip_label.pack(side="left", padx=(0, 12 if idx < len(chip_vars) - 1 else 0))
    
    # Create floating loading overlay
    overlay_position = (50, 50)
    if config:
        saved_pos = config.config.get('overlay_position')
        if saved_pos and len(saved_pos) == 2:
            overlay_position = tuple(saved_pos)
    
    loading_overlay = LoadingOverlay(position=overlay_position)
    loading_overlay.create_window(base_root)
    
    if hasattr(service, 'attach_overlay_root'):
        service.attach_overlay_root(base_root)

    _UI_READY.set()
    window.after(40, lambda: _drain_ui_queue(window))
    
    # Center window after initial layout
    def _center_window():
        window.update_idletasks()
        actual_width = window.winfo_width()
        actual_height = window.winfo_height()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = (screen_w - actual_width) // 2
        y = (screen_h - actual_height) // 2
        window.geometry(f"+{x}+{y}")
    
    window.after(100, _center_window)

    # Connect overlay to service
    if hasattr(service, '_gui_callbacks'):
        service._gui_callbacks = {
            'start_loading': loading_overlay.show,
            'stop_loading': loading_overlay.hide
        }
    
    # ====================== API CONFIGURATION ======================
    api_card = ModernCard(content_frame)
    api_card.pack(fill="x", pady=(0, 20))
    
    api_container = tk.Frame(api_card, bg=COLORS['bg_primary'])
    api_container.pack(fill="both", padx=25, pady=20)
    
    # Section title
    api_header = tk.Label(
        api_container,
        text="API Configuration",
        font=('Segoe UI', 14, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    api_header.pack(anchor="w", pady=(0, 15))
    
    # API Key section
    api_key_frame = tk.Frame(api_container, bg=COLORS['bg_primary'])
    api_key_frame.pack(fill="x", pady=(0, 15))
    
    api_key_label = tk.Label(
        api_key_frame,
        text="API Key",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    api_key_label.pack(anchor="w", pady=(0, 8))
    
    current_key = ""
    if hasattr(corrector, 'api_key') and corrector.api_key and corrector.api_key != "dummy-key-replace-in-gui":
        current_key = corrector.api_key
    else:
        current_key = os.getenv("GEMINI_API_KEY", "")
    
    api_key_var = tk.StringVar(value=current_key)
    
    # API Key entry with modern styling and focus effects
    entry_container = tk.Frame(api_key_frame, bg=COLORS['border'], highlightthickness=1, 
                              highlightbackground=COLORS['border'])
    entry_container.pack(fill="x")
    
    api_key_entry = tk.Entry(
        entry_container,
        textvariable=api_key_var,
        show="●",
        font=('Segoe UI', 11),
        bg=COLORS['bg_secondary'],
        fg=COLORS['text_primary'],
        relief='flat',
        borderwidth=0,
        insertbackground=COLORS['accent_primary']
    )
    api_key_entry.pack(fill="x", ipady=10, padx=12, pady=2)
    
    # Add focus effects
    def on_entry_focus_in(e):
        entry_container.config(highlightbackground=COLORS['accent_primary'], highlightthickness=2)
    
    def on_entry_focus_out(e):
        entry_container.config(highlightbackground=COLORS['border'], highlightthickness=1)
    
    api_key_entry.bind('<FocusIn>', on_entry_focus_in)
    api_key_entry.bind('<FocusOut>', on_entry_focus_out)
    
    # Show/Hide key toggle
    show_key_var = tk.BooleanVar(value=False)
    
    def toggle_key_visibility():
        api_key_entry.config(show="" if show_key_var.get() else "●")
    
    show_key_check = tk.Checkbutton(
        api_key_frame,
        text="Show API Key",
        variable=show_key_var,
        command=toggle_key_visibility,
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        activebackground=COLORS['bg_primary'],
        selectcolor=COLORS['bg_primary'],
        relief='flat',
        cursor='hand2'
    )
    show_key_check.pack(anchor="w", pady=(8, 0))
    
    # API Key help text
    help_link = tk.Label(
        api_key_frame,
        text="🔗 Get your free API key from Google AI Studio",
        font=('Segoe UI', 9),
        fg=COLORS['accent_primary'],
        bg=COLORS['bg_primary'],
        cursor='hand2'
    )
    help_link.pack(anchor="w", pady=(4, 0))
    
    def open_api_link(e):
        import webbrowser
        webbrowser.open("https://makersuite.google.com/app/apikey")
    
    help_link.bind('<Button-1>', open_api_link)
    
    # Model selection
    model_frame = tk.Frame(api_container, bg=COLORS['bg_primary'])
    model_frame.pack(fill="x", pady=(0, 15))
    
    model_label = tk.Label(
        model_frame,
        text="Model",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    model_label.pack(anchor="w", pady=(0, 8))
    
    model_var = tk.StringVar(value=config.get("model_name", "gemini-2.0-flash-exp") if config else "gemini-2.0-flash-exp")
    
    # Create modern styled combobox
    model_combo_frame = tk.Frame(model_frame, bg=COLORS['bg_secondary'])
    model_combo_frame.pack(fill="x")
    
    model_combo = ttk.Combobox(
        model_combo_frame,
        textvariable=model_var,
        values=["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"],
        state="readonly",
        font=('Segoe UI', 10)
    )
    model_combo.pack(fill="x", ipady=6, padx=2, pady=2)
    
    # Save API button
    def save_api_config():
        api_key = api_key_var.get().strip()
        model = model_var.get()
        
        if not api_key:
            messagebox.showerror("Error", "Please enter an API key")
            return
        
        if config:
            config.set("api_key", api_key)
            config.set("model_name", model)
        
        # Reinitialize corrector
        try:
            from ..gemini_corrector import GeminiCorrector
            new_corrector = GeminiCorrector(api_key=api_key, model_name=model)
            if new_corrector.is_configured:
                service._corrector = new_corrector
                status_badge.config(text="● Active", bg=COLORS['success'], fg="#FFFFFF")
                api_status_var.set(f"Gemini connected ({model})")
                model_summary_var.set(f"Model: {model}")
                messagebox.showinfo("Success", "API configuration saved successfully!")
            else:
                status_badge.config(text="● Inactive", bg=COLORS['error'], fg="#FFFFFF")
                api_status_var.set("API key not configured")
                messagebox.showerror("Error", "Failed to initialize Gemini API")
        except Exception as e:
            status_badge.config(text="● Inactive", bg=COLORS['error'], fg="#FFFFFF")
            api_status_var.set("API key not configured")
            messagebox.showerror("Error", f"Failed to configure API: {e}")
    
    save_btn = ModernButton(api_container, text="Save API Configuration", command=save_api_config, style="primary")
    save_btn.pack(fill="x")
    
    # ====================== CORRECTION SETTINGS ======================
    settings_card = ModernCard(content_frame)
    settings_card.pack(fill="x", pady=(0, 20))
    
    settings_container = tk.Frame(settings_card, bg=COLORS['bg_primary'])
    settings_container.pack(fill="both", padx=25, pady=20)
    
    settings_header = tk.Label(
        settings_container,
        text="Correction Settings",
        font=('Segoe UI', 14, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    settings_header.pack(anchor="w", pady=(0, 15))
    
    # Helper utilities for trigger capture
    modifier_keysyms = {
        'shift', 'shift_l', 'shift_r',
        'control', 'control_l', 'control_r', 'ctrl', 'ctrl_l', 'ctrl_r',
        'alt', 'alt_l', 'alt_r', 'meta', 'meta_l', 'meta_r',
        'option', 'option_l', 'option_r'
    }

    CTRL_MASK = 0x0004
    SHIFT_MASK = 0x0001
    ALT_MASK = 0x0008
    # Note: 0x20000 is NumLock on Windows, NOT Alt - removing it

    def _format_event_to_trigger(event: tk.Event) -> Optional[str]:  # type: ignore[name-defined]
        keysym = getattr(event, 'keysym', '') or ''
        lower_keysym = keysym.lower()
        if not lower_keysym or lower_keysym in modifier_keysyms:
            return None

        modifiers: list[str] = []
        state = getattr(event, 'state', 0) or 0

        # Only check the primary modifier bits (avoid NumLock and other state bits)
        if (state & CTRL_MASK) or lower_keysym.startswith(('control', 'ctrl')):
            modifiers.append('ctrl')
        if (state & SHIFT_MASK) or lower_keysym.startswith('shift'):
            modifiers.append('shift')
        if (state & ALT_MASK) or lower_keysym.startswith(('alt', 'meta', 'option')):
            modifiers.append('alt')

        ordered_mods = []
        for mod in ['ctrl', 'shift', 'alt']:
            if mod in modifiers and mod not in ordered_mods:
                ordered_mods.append(mod)

        combo_parts = ordered_mods + [lower_keysym]
        return '+'.join(combo_parts)

    def _capture_trigger(target_var: tk.StringVar, prompt_title: str) -> None:
        capture = tk.Toplevel(window)
        capture.title(prompt_title)
        capture.configure(bg=COLORS['bg_secondary'])
        capture.attributes('-topmost', True)
        capture.resizable(False, False)
        capture.transient(window)
        capture.grab_set()

        message_var = tk.StringVar(value="Press the desired key combination. Press Esc to cancel.")

        label = tk.Label(
            capture,
            textvariable=message_var,
            font=('Segoe UI', 10),
            fg=COLORS['text_primary'],
            bg=COLORS['bg_secondary'],
            justify='center'
        )
        label.pack(fill='both', expand=True, padx=20, pady=20)

        capture.update_idletasks()
        width, height = 360, 140
        x = window.winfo_rootx() + (window.winfo_width() - width) // 2
        y = window.winfo_rooty() + (window.winfo_height() - height) // 2
        capture.geometry(f"{width}x{height}+{x}+{y}")

        def _close_popup() -> None:
            try:
                capture.grab_release()
            except tk.TclError:
                pass
            capture.destroy()
            try:
                window.after(100, window.focus_force)
            except tk.TclError:
                pass

        def _on_key(event: tk.Event) -> None:  # type: ignore[name-defined]
            if event.keysym == 'Escape':
                _close_popup()
                return

            combo = _format_event_to_trigger(event)
            if combo is None:
                message_var.set("Please include a non-modifier key in your shortcut.")
                return

            normalized = AutoCorrectService.normalize_trigger_key(combo)
            if not normalized:
                message_var.set("That key isn't supported. Try a different combination.")
                return

            target_var.set(normalized)
            message_var.set(f"Captured {normalized.upper()}")
            capture.after(120, _close_popup)

        capture.bind('<KeyPress>', _on_key)
        capture.protocol("WM_DELETE_WINDOW", _close_popup)
        capture.focus_force()

    # Trigger state variables and display synchronisation
    trigger_var = tk.StringVar(value=trigger_key_initial)
    dictation_var = tk.StringVar(value=dictation_key_initial)
    clear_trigger_var = tk.StringVar(value=clear_trigger_initial)

    trigger_display_var = tk.StringVar()
    dictation_display_var = tk.StringVar()
    clear_display_var = tk.StringVar()

    def _sync_trigger_display() -> None:
        value = trigger_var.get().strip()
        display = value.upper() if value else "NOT SET"
        trigger_display_var.set(display)
        trigger_chip_var.set(f"Correction Trigger: {display}")

    def _sync_dictation_display() -> None:
        value = dictation_var.get().strip()
        display = value.upper() if value else "NOT SET"
        dictation_display_var.set(display)
        dictation_chip_var.set(f"Dictation Trigger: {display}")
        status_prefix = "Dictation active" if service.is_dictation_active() else "Dictation ready"
        dictation_status_var.set(f"{status_prefix} ({display})")

    def _sync_clear_display() -> None:
        value = clear_trigger_var.get().strip()
        display = value.upper() if value else "DISABLED"
        clear_display_var.set(display)

    trigger_var.trace_add('write', lambda *_: _sync_trigger_display())
    dictation_var.trace_add('write', lambda *_: _sync_dictation_display())
    clear_trigger_var.trace_add('write', lambda *_: _sync_clear_display())

    _sync_trigger_display()
    _sync_dictation_display()
    _sync_clear_display()

    # Trigger key configuration
    trigger_frame = tk.Frame(settings_container, bg=COLORS['bg_primary'])
    trigger_frame.pack(fill="x", pady=(0, 15))

    trigger_label = tk.Label(
        trigger_frame,
        text="Trigger Key",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    trigger_label.pack(anchor="w", pady=(0, 8))

    trigger_input = tk.Frame(trigger_frame, bg=COLORS['bg_secondary'])
    trigger_input.pack(fill="x")

    trigger_value_label = tk.Label(
        trigger_input,
        textvariable=trigger_display_var,
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_secondary'],
        anchor='w'
    )
    trigger_value_label.pack(side='left', fill='x', expand=True, padx=(12, 10), pady=6)

    trigger_set_btn = ModernButton(
        trigger_input,
        text="Set Trigger",
        command=lambda: _capture_trigger(trigger_var, "Set Correction Trigger"),
        style="secondary"
    )
    trigger_set_btn.pack(side='right', padx=(0, 10), pady=6)

    trigger_help = tk.Label(
        trigger_frame,
        text="Click \"Set Trigger\" and press any key or combination (Ctrl/Shift/Alt supported).",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        justify='left'
    )
    trigger_help.pack(fill='x', anchor='w', pady=(6, 0))

    # Dictation trigger configuration
    dictation_frame = tk.Frame(settings_container, bg=COLORS['bg_primary'])
    dictation_frame.pack(fill="x", pady=(0, 15))

    dictation_label = tk.Label(
        dictation_frame,
        text="Dictation Trigger",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    dictation_label.pack(anchor="w", pady=(0, 8))

    dictation_input = tk.Frame(dictation_frame, bg=COLORS['bg_secondary'])
    dictation_input.pack(fill="x")

    dictation_value_label = tk.Label(
        dictation_input,
        textvariable=dictation_display_var,
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_secondary'],
        anchor='w'
    )
    dictation_value_label.pack(side='left', fill='x', expand=True, padx=(12, 10), pady=6)

    dictation_set_btn = ModernButton(
        dictation_input,
        text="Set Trigger",
        command=lambda: _capture_trigger(dictation_var, "Set Dictation Trigger"),
        style="secondary"
    )
    dictation_set_btn.pack(side='right', padx=(0, 10), pady=6)

    dictation_help = tk.Label(
        dictation_frame,
        text="Choose the shortcut that toggles real-time dictation. Hold modifiers (Ctrl/Shift/Alt) and press a key.",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        justify='left'
    )
    dictation_help.pack(fill='x', anchor="w", pady=(6, 0))

    # Clear buffer trigger configuration
    clear_trigger_frame = tk.Frame(settings_container, bg=COLORS['bg_primary'])
    clear_trigger_frame.pack(fill="x", pady=(0, 15))

    clear_trigger_label = tk.Label(
        clear_trigger_frame,
        text="Clear Buffer Trigger",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    clear_trigger_label.pack(anchor="w", pady=(0, 8))

    clear_input = tk.Frame(clear_trigger_frame, bg=COLORS['bg_secondary'])
    clear_input.pack(fill="x")

    clear_value_label = tk.Label(
        clear_input,
        textvariable=clear_display_var,
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_secondary'],
        anchor='w'
    )
    clear_value_label.pack(side='left', fill='x', expand=True, padx=(12, 10), pady=6)

    clear_buttons = tk.Frame(clear_input, bg=COLORS['bg_secondary'])
    clear_buttons.pack(side='right', padx=(0, 10), pady=6)

    clear_set_btn = ModernButton(
        clear_buttons,
        text="Set Trigger",
        command=lambda: _capture_trigger(clear_trigger_var, "Set Clear Trigger"),
        style="secondary"
    )
    clear_set_btn.pack(side='left')

    clear_disable_btn = ModernButton(
        clear_buttons,
        text="Disable",
        command=lambda: clear_trigger_var.set(""),
        style="secondary"
    )
    clear_disable_btn.pack(side='left', padx=(8, 0))

    clear_help = tk.Label(
        clear_trigger_frame,
        text="Set a keyboard shortcut to clear saved paragraphs instantly, or disable the shortcut entirely.",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        justify='left'
    )
    clear_help.pack(fill='x', anchor='w', pady=(6, 0))
    
    # Number of versions
    versions_frame = tk.Frame(settings_container, bg=COLORS['bg_primary'])
    versions_frame.pack(fill="x", pady=(0, 15))
    
    versions_label = tk.Label(
        versions_frame,
        text="AI Correction Versions",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    versions_label.pack(anchor="w", pady=(0, 8))
    
    versions_var = tk.IntVar(value=versions_initial)

    versions_spin_frame = tk.Frame(versions_frame, bg=COLORS['bg_secondary'])
    versions_spin_frame.pack(fill="x")

    versions_spin = ttk.Spinbox(
        versions_spin_frame,
        from_=1,
        to=MAX_CANDIDATES,
        textvariable=versions_var,
        font=('Segoe UI', 10),
        justify='center',
        width=6,
        wrap=False,
    )
    versions_spin.pack(fill="x", ipady=6, padx=2, pady=2)

    versions_hint = tk.Label(
        versions_frame,
        text=f"Choose how many AI candidates to generate (max {MAX_CANDIDATES}). Configure tone & temperature below.",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        justify='left'
    )
    versions_hint.pack(fill='x', anchor='w', pady=(6, 4))

    # Candidate personalization panel
    candidate_header = tk.Label(
        settings_container,
        text="Candidate Personalization",
        font=('Segoe UI', 10, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    candidate_header.pack(anchor='w', pady=(0, 6))

    candidate_subtitle = tk.Label(
        settings_container,
        text="Adjust how adventurous each candidate should be. Temperature controls variability; tone sets the writing style.",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary'],
        justify='left'
    )
    candidate_subtitle.pack(fill='x', anchor='w', pady=(0, 10))

    candidate_panel = tk.Frame(
        settings_container,
        bg=COLORS['bg_secondary'],
        highlightthickness=1,
        highlightbackground=COLORS['border'],
    )
    candidate_panel.pack(fill='x', pady=(0, 20))
    candidate_panel.configure(padx=14, pady=12)

    candidate_panel.columnconfigure(0, weight=1)

    candidate_temp_vars = []
    candidate_tone_vars = []
    candidate_rows = []

    tone_labels = [opt['label'] for opt in TONE_OPTIONS]

    def _tone_label_for(key: str) -> str:
        return TONE_LABEL_MAP.get(key, key.title())

    def _tone_description_for(key: str) -> str:
        return TONE_DESCRIPTION_MAP.get(key, "")

    for idx in range(MAX_CANDIDATES):
        initial_cfg = candidate_settings_initial[idx] if idx < len(candidate_settings_initial) else fallback_defaults[idx % len(fallback_defaults)]
        initial_temp = initial_cfg.get('temperature', 0.3)
        try:
            initial_temp = float(initial_temp)
        except (TypeError, ValueError):
            initial_temp = 0.3
        initial_temp = max(0.0, min(1.0, initial_temp))

        tone_key = initial_cfg.get('tone', 'original')
        if not isinstance(tone_key, str) or tone_key.lower() not in VALID_TONE_KEYS:
            tone_key = 'original'
        else:
            tone_key = tone_key.lower()

        temp_var = tk.DoubleVar(value=initial_temp)
        tone_var = tk.StringVar(value=tone_key)
        candidate_temp_vars.append(temp_var)
        candidate_tone_vars.append(tone_var)

        row_frame = tk.Frame(candidate_panel, bg=COLORS['bg_secondary'])
        row_frame.pack(fill='x', pady=(12 if idx == 0 else 8, 8))

        top_row = tk.Frame(row_frame, bg=COLORS['bg_secondary'])
        top_row.pack(fill='x')

        name_label = tk.Label(
            top_row,
            text=f"Candidate {idx + 1}",
            font=('Segoe UI', 10, 'bold'),
            fg=COLORS['text_primary'],
            bg=COLORS['bg_secondary']
        )
        name_label.pack(side='left')

        temp_value_var = tk.StringVar(value=f"{initial_temp:.2f}")
        temp_value_label = tk.Label(
            top_row,
            textvariable=temp_value_var,
            font=('Segoe UI', 9, 'bold'),
            fg=COLORS['text_secondary'],
            bg=COLORS['bg_secondary']
        )
        temp_value_label.pack(side='right')

        def _make_temp_callback(var: tk.DoubleVar, display: tk.StringVar):
            def _callback(raw_value: str) -> None:
                try:
                    numeric = float(raw_value)
                except (TypeError, ValueError):
                    numeric = var.get()
                numeric = max(0.0, min(1.0, numeric))
                display.set(f"{numeric:.2f}")
            return _callback

        temp_scale = ttk.Scale(
            row_frame,
            from_=0.0,
            to=1.0,
            variable=temp_var,
            command=_make_temp_callback(temp_var, temp_value_var),
        )
        temp_scale.pack(fill='x', pady=(6, 4))
        temp_scale.set(initial_temp)

        tone_row = tk.Frame(row_frame, bg=COLORS['bg_secondary'])
        tone_row.pack(fill='x', pady=(4, 0))

        tone_label_widget = tk.Label(
            tone_row,
            text="Tone",
            font=('Segoe UI', 9, 'bold'),
            fg=COLORS['text_primary'],
            bg=COLORS['bg_secondary']
        )
        tone_label_widget.pack(side='left')

        tone_display_var = tk.StringVar()
        tone_desc_var = tk.StringVar()

        def _sync_tone_display(var: tk.StringVar = tone_var, display: tk.StringVar = tone_display_var, desc: tk.StringVar = tone_desc_var) -> None:
            key = var.get()
            display.set(_tone_label_for(key))
            desc.set(_tone_description_for(key))

        _sync_tone_display()
        tone_var.trace_add('write', lambda *_args, sync=_sync_tone_display: sync())

        tone_combo = ttk.Combobox(
            tone_row,
            state='readonly',
            values=tone_labels,
            textvariable=tone_display_var,
            width=28,
        )
        tone_combo.pack(side='left', padx=(10, 0), fill='x', expand=True)
        tone_combo.set(tone_display_var.get())

        def _on_tone_selected(_event, combo=tone_combo, var=tone_var):
            selection = combo.get()
            var.set(TONE_LABEL_TO_KEY.get(selection, var.get()))

        tone_combo.bind('<<ComboboxSelected>>', _on_tone_selected)

        tone_desc_label = tk.Label(
            row_frame,
            textvariable=tone_desc_var,
            font=('Segoe UI', 8),
            fg=COLORS['text_secondary'],
            bg=COLORS['bg_secondary'],
            justify='left'
        )
        tone_desc_label.pack(fill='x', pady=(4, 0))

        candidate_rows.append({
            'frame': row_frame,
            'top_row': top_row,
            'tone_row': tone_row,
            'scale': temp_scale,
            'tone_combo': tone_combo,
            'name_label': name_label,
            'temp_value_label': temp_value_label,
            'tone_desc_label': tone_desc_label,
            'tone_var': tone_var,
        })

    def _update_candidate_rows(*_args):
        try:
            count = int(versions_var.get())
        except (TypeError, ValueError, tk.TclError):
            count = versions_initial

        sanitized = max(1, min(count, MAX_CANDIDATES))
        if sanitized != count:
            versions_var.set(sanitized)
            return

        candidate_chip_var.set(f"Candidates: {sanitized}")

        for idx, row in enumerate(candidate_rows):
            is_active = idx < sanitized
            bg_color = COLORS['bg_secondary'] if is_active else '#ECEEF7'
            for widget in (row['frame'], row['top_row'], row['tone_row']):
                widget.configure(bg=bg_color)
            row['name_label'].configure(
                fg=COLORS['text_primary'] if is_active else COLORS['text_light'],
                bg=bg_color
            )
            row['temp_value_label'].configure(
                fg=COLORS['text_secondary'] if is_active else COLORS['text_light'],
                bg=bg_color
            )
            row['tone_desc_label'].configure(
                fg=COLORS['text_secondary'] if is_active else COLORS['text_light'],
                bg=bg_color
            )

            if is_active:
                row['scale'].state(['!disabled'])
                row['tone_combo'].configure(state='readonly')
            else:
                row['scale'].state(['disabled'])
                row['tone_combo'].configure(state='disabled')

    versions_spin.configure(command=lambda: _update_candidate_rows())
    versions_var.trace_add('write', lambda *_: _update_candidate_rows())
    _update_candidate_rows()

    # Enable/disable toggle
    enabled_var = tk.BooleanVar(value=config.get("paragraph_enabled", True) if config else True)
    
    enabled_check = tk.Checkbutton(
        settings_container,
        text="Enable paragraph correction",
        variable=enabled_var,
        font=('Segoe UI', 10),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary'],
        activebackground=COLORS['bg_primary'],
        selectcolor=COLORS['bg_primary'],
        relief='flat',
        cursor='hand2'
    )
    enabled_check.pack(anchor="w", pady=(0, 15))
    
    # Save settings button
    def save_settings():
        trigger_raw = trigger_var.get().strip()
        trigger_key = AutoCorrectService.normalize_trigger_key(trigger_raw)
        if not trigger_key:
            messagebox.showerror("Error", "Please set a valid correction trigger.")
            trigger_var.set(service.get_trigger_key())
            return

        dictation_raw = dictation_var.get().strip()
        dictation_key = AutoCorrectService.normalize_trigger_key(dictation_raw)
        if not dictation_key:
            messagebox.showerror("Error", "Please set a valid dictation trigger.")
            dictation_var.set(service.get_dictation_trigger_key())
            return

        if dictation_key == trigger_key:
            messagebox.showerror("Error", "Dictation trigger cannot match the correction trigger.")
            return

        clear_raw = clear_trigger_var.get().strip()
        clear_value = ""
        if clear_raw:
            clear_value = AutoCorrectService.normalize_trigger_key(clear_raw) or ""
            if not clear_value:
                messagebox.showerror("Error", "Invalid clear-buffer trigger. Choose another or disable it.")
                clear_trigger_var.set(service.get_clear_buffer_trigger_key())
                return

        if clear_value and dictation_key == clear_value:
            messagebox.showerror("Error", "Dictation trigger cannot match the clear-buffer trigger.")
            return

        if not service.set_trigger_key(trigger_key):
            messagebox.showerror("Error", f"Unable to apply correction trigger ({trigger_key.upper()}).")
            trigger_var.set(service.get_trigger_key())
            return

        if not service.set_dictation_trigger_key(dictation_key):
            messagebox.showerror("Error", f"Unable to apply dictation trigger ({dictation_key.upper()}).")
            dictation_var.set(service.get_dictation_trigger_key())
            return

        if not service.set_clear_buffer_trigger_key(clear_value):
            messagebox.showerror("Error", "Unable to apply clear-buffer trigger. Choose another or disable it.")
            clear_trigger_var.set(service.get_clear_buffer_trigger_key())
            return

        try:
            versions = int(versions_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("Error", f"Please choose a valid number of AI candidates (1-{MAX_CANDIDATES}).")
            return

        if versions < 1 or versions > MAX_CANDIDATES:
            messagebox.showerror("Error", f"The number of AI candidates must be between 1 and {MAX_CANDIDATES}.")
            versions_var.set(max(1, min(versions, MAX_CANDIDATES)))
            return

        if not service.set_versions_per_correction(versions):
            messagebox.showerror("Error", f"Unable to apply candidate count. Choose between 1 and {MAX_CANDIDATES}.")
            return

        candidate_payload = []
        for idx in range(MAX_CANDIDATES):
            temp_value = candidate_temp_vars[idx].get()
            try:
                temp_value = float(temp_value)
            except (TypeError, ValueError):
                temp_value = 0.3
            temp_value = max(0.0, min(1.0, round(temp_value, 2)))

            tone_value = candidate_tone_vars[idx].get()
            tone_value = tone_value if tone_value in VALID_TONE_KEYS else 'original'

            candidate_payload.append({
                "temperature": temp_value,
                "tone": tone_value,
            })

        if not service.set_candidate_settings(candidate_payload):
            messagebox.showerror("Error", "Unable to apply candidate personalization settings.")
            return

        if config:
            config.set("trigger_key", trigger_key)
            config.set("dictation_trigger_key", dictation_key)
            config.set("versions_per_correction", versions)
            config.set_candidate_settings(candidate_payload)
            config.set("paragraph_enabled", enabled_var.get())
            config.set("clear_buffer_trigger_key", clear_value)

        service.set_paragraph_enabled(enabled_var.get())
        versions_var.set(versions)
        candidate_chip_var.set(f"Candidates: {versions}")
        _update_candidate_rows()
        for idx, payload in enumerate(candidate_payload):
            candidate_temp_vars[idx].set(payload["temperature"])
        _sync_trigger_display()
        _sync_dictation_display()
        _sync_clear_display()
        paragraph_chip_var.set("Paragraph Mode: On" if enabled_var.get() else "Paragraph Mode: Off")
        dictation_state_text = "Dictation active" if service.is_dictation_active() else "Dictation ready"
        dictation_status_var.set(f"{dictation_state_text} ({dictation_key.upper()})")

        messagebox.showinfo("Success", "Settings saved successfully!")
    
    def clear_saved_buffer():
        service.clear_saved_paragraphs()
        messagebox.showinfo("Buffer Cleared", "Saved paragraphs cleared. New corrections will start fresh.")
    
    # Button row
    btn_row = tk.Frame(settings_container, bg=COLORS['bg_primary'])
    btn_row.pack(fill="x")
    
    save_settings_btn = ModernButton(btn_row, text="Save Settings", command=save_settings, style="primary")
    save_settings_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    clear_buffer_btn = ModernButton(btn_row, text="Clear Saved Paragraphs", command=clear_saved_buffer, style="secondary")
    clear_buffer_btn.pack(side="left", fill="x", expand=True)
    
    # ====================== LOADING INDICATOR POSITION ======================
    indicator_card = ModernCard(content_frame)
    indicator_card.pack(fill="x", pady=(0, 20))
    
    indicator_container = tk.Frame(indicator_card, bg=COLORS['bg_primary'])
    indicator_container.pack(fill="both", padx=25, pady=20)
    
    indicator_header = tk.Label(
        indicator_container,
        text="Loading Indicator",
        font=('Segoe UI', 14, 'bold'),
        fg=COLORS['text_primary'],
        bg=COLORS['bg_primary']
    )
    indicator_header.pack(anchor="w", pady=(0, 8))
    
    indicator_subtitle = tk.Label(
        indicator_container,
        text="Customize the position of the loading spinner that appears during corrections",
        font=('Segoe UI', 9),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary']
    )
    indicator_subtitle.pack(anchor="w", pady=(0, 15))
    
    position_label = tk.Label(
        indicator_container,
        text=f"Current Position: ({overlay_position[0]}, {overlay_position[1]})",
        font=('Segoe UI', 10),
        fg=COLORS['text_secondary'],
        bg=COLORS['bg_primary']
    )
    position_label.pack(anchor="w", pady=(0, 15))
    
    positioning_mode = [False]  # Use list to maintain reference
    
    def update_position_label(x, y):
        """Callback when overlay is dragged."""
        position_label.config(text=f"Current Position: ({x}, {y})")
    
    loading_overlay.set_position_callback(update_position_label)
    
    def toggle_positioning():
        if not positioning_mode[0]:
            # Enable positioning mode
            positioning_mode[0] = True
            loading_overlay.enable_dragging(True)
            position_btn.config(text="Lock Position")
            # Keep button hue in sync with hover state when toggled
            position_btn.default_bg = COLORS['success']
            position_btn.hover_bg = '#059669'
            position_btn.configure(bg=position_btn.default_bg)
            messagebox.showinfo(
                "Positioning Mode",
                "Drag the indicator on your screen to the desired position.\nClick 'Lock Position' when done."
            )
        else:
            # Disable positioning mode and save
            positioning_mode[0] = False
            loading_overlay.enable_dragging(False)
            position_btn.config(text="Position Indicator")
            position_btn.default_bg = COLORS['accent_primary']
            position_btn.hover_bg = COLORS['accent_hover']
            position_btn.configure(bg=position_btn.default_bg)
            
            # Save position
            x, y = loading_overlay.position
            if config:
                config.set('overlay_position', [x, y])
            
            position_label.config(text=f"Current Position: ({x}, {y})")
            messagebox.showinfo("Position Saved", f"Indicator position saved: ({x}, {y})")
    
    def reset_position():
        loading_overlay.set_position(50, 50)
        if config:
            config.set('overlay_position', [50, 50])
        position_label.config(text="Current Position: (50, 50)")
        messagebox.showinfo("Position Reset", "Indicator position reset to default (50, 50)")
    
    def test_indicator():
        loading_overlay.show()
        window.after(2000, loading_overlay.hide)
    
    indicator_btn_row = tk.Frame(indicator_container, bg=COLORS['bg_primary'])
    indicator_btn_row.pack(fill="x")
    
    position_btn = ModernButton(indicator_btn_row, text="Position Indicator", command=toggle_positioning, style="primary")
    position_btn.pack(side="left", padx=(0, 10))
    
    reset_btn = ModernButton(indicator_btn_row, text="Reset Position", command=reset_position, style="secondary")
    reset_btn.pack(side="left", padx=(0, 10))
    
    test_btn = ModernButton(indicator_btn_row, text="Test (2s)", command=test_indicator, style="secondary")
    test_btn.pack(side="left")
    
    # ====================== HISTORY ======================
    if history:
        history_card = ModernCard(content_frame)
        history_card.pack(fill="x", pady=(0, 20))
        
        history_container = tk.Frame(history_card, bg=COLORS['bg_primary'])
        history_container.pack(fill="both", padx=25, pady=20)
        
        history_header = tk.Label(
            history_container,
            text="Correction History",
            font=('Segoe UI', 14, 'bold'),
            fg=COLORS['text_primary'],
            bg=COLORS['bg_primary']
        )
        history_header.pack(anchor="w", pady=(0, 8))
        
        history_subtitle = tk.Label(
            history_container,
            text="View and manage your correction history",
            font=('Segoe UI', 9),
            fg=COLORS['text_secondary'],
            bg=COLORS['bg_primary']
        )
        history_subtitle.pack(anchor="w", pady=(0, 15))
        
        def view_history():
            try:
                stats = history.get_statistics(30)
                recent = history.get_recent_corrections(5)
                
                msg = f"CORRECTION HISTORY\n\n"
                msg += f"Auto-cleanup: Every {history.cleanup_interval//60} minutes\n"
                msg += f"Retention: {history.retention_hours} hour(s)\n\n"
                msg += f"Total: {stats['total_corrections']} corrections\n"
                msg += f"Characters: {stats['total_characters']:,}\n"
                msg += f"Words: {stats['total_words']:,}\n\n"
                msg += f"Recent Corrections:\n"
                
                for i, rec in enumerate(recent, 1):
                    orig = rec['original_text'][:30]
                    msg += f"{i}. {orig}...\n"
                
                messagebox.showinfo("History", msg)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to retrieve history: {e}")
        
        def clear_history():
            if messagebox.askyesno("Confirm", "Clear all correction history?"):
                try:
                    history.clear_history()
                    messagebox.showinfo("Success", "History cleared successfully!")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to clear history: {e}")
        
        history_btn_row = tk.Frame(history_container, bg=COLORS['bg_primary'])
        history_btn_row.pack(fill="x")
        
        view_history_btn = ModernButton(history_btn_row, text="View History", command=view_history, style="primary")
        view_history_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        clear_history_btn = ModernButton(history_btn_row, text="Clear History", command=clear_history, style="danger")
        clear_history_btn.pack(side="left", fill="x", expand=True)
    
    # ====================== FOOTER ======================
    footer_frame = tk.Frame(content_frame, bg=COLORS['bg_secondary'])
    footer_frame.pack(fill="x", pady=(20, 0))
    
    footer_divider = tk.Frame(footer_frame, bg=COLORS['border'], height=1)
    footer_divider.pack(fill="x", pady=(0, 15))
    
    footer_text = tk.Label(
        footer_frame,
        text="CorreX v1.0 • Powered by Google Gemini AI • Made with ❤️",
        font=('Segoe UI', 9),
        fg=COLORS['text_light'],
        bg=COLORS['bg_secondary']
    )
    footer_text.pack()
    
    # Handle window close
    def on_closing():
        nonlocal loading_overlay
        global _ACTIVE_ROOT

        if resize_job['id'] is not None:
            try:
                window.after_cancel(resize_job['id'])
            except tk.TclError:
                pass
            resize_job['id'] = None

        def _cleanup_overlay() -> None:
            nonlocal loading_overlay
            try:
                if loading_overlay:
                    loading_overlay.destroy()
            except Exception as e:
                print(f"[WARNING] Failed to destroy overlay: {e}")
            finally:
                loading_overlay = None

        service._gui_callbacks = None

        if keep_service_running:
            _cleanup_overlay()
            _ACTIVE_ROOT = None
            _reset_ui_channel()
            if on_close:
                on_close()
            window.destroy()
            base_root.destroy()
            return

        if messagebox.askokcancel("Quit", "Stop the autocorrect service and exit?"):
            _cleanup_overlay()
            _ACTIVE_ROOT = None
            _reset_ui_channel()
            service.stop()
            window.destroy()
            base_root.destroy()
    
    window.protocol("WM_DELETE_WINDOW", on_closing)
    base_root.mainloop()
