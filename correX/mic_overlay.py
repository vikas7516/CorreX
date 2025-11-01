"""Floating microphone indicator overlay for dictation status."""
from __future__ import annotations

import tkinter as tk
from typing import Optional

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore
    _HAS_PIL = False

from .asset_manager import get_asset_manager


class MicOverlay:
    """
    Floating overlay window that shows microphone status during dictation.
    Displays at bottom-center of screen with pulsing animation.
    """
    
    def __init__(self):
        """Initialize mic overlay (hidden by default)."""
        self.window: Optional[tk.Toplevel] = None
        self.is_visible = False
        self._animation_id: Optional[str] = None
        self._fade_level = 1.0
        self._fade_direction = -1
        self._mic_icon: Optional[tk.PhotoImage] = None
        self._mic_pil_base = None  # Cached PIL base image
        self._mic_path = None
        self._asset_manager = get_asset_manager()
        self._root: Optional[tk.Misc] = None
        self._container: Optional[tk.Frame] = None
        self._icon_label: Optional[tk.Label] = None
        self._text_label: Optional[tk.Label] = None
        
    def attach_root(self, root: tk.Misc) -> None:
        """Attach the overlay to an existing Tk root for thread-safe updates."""
        self._root = root

    def show(self) -> None:
        """Show the microphone overlay."""
        self._run_on_ui_thread(self._show_internal)
    
    def hide(self) -> None:
        """Hide the microphone overlay."""
        self._run_on_ui_thread(self._hide_internal)

    def _run_on_ui_thread(self, callback) -> None:
        """Ensure the provided callback runs on an active Tk UI thread."""
        target_root = None
        try:
            if self._root and self._root.winfo_exists():
                target_root = self._root
            elif tk._default_root is not None and tk._default_root.winfo_exists():  # type: ignore[attr-defined]
                target_root = tk._default_root  # type: ignore[attr-defined]
        except tk.TclError:
            target_root = None

        if target_root is not None:
            try:
                target_root.after(0, callback)
                return
            except tk.TclError:
                pass

        # Fall back to direct call if scheduling is not possible
        callback()

    def _show_internal(self) -> None:
        """Internal implementation that builds and shows the overlay."""
        if self.is_visible and self.window and self.window.winfo_exists():
            return

        self._ensure_window()
        if not self.window:
            return

        try:
            self.window.deiconify()
            self.is_visible = True
            self._draw_mic_indicator()
            self._animate_pulse()
            print("[MIC_OVERLAY] Shown")
        except tk.TclError:
            pass

    def _hide_internal(self) -> None:
        """Internal implementation that hides and cleans up the overlay."""
        if not self.is_visible:
            return

        self.is_visible = False

        if self._animation_id and self.window:
            try:
                self.window.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

        if self.window and self.window.winfo_exists():
            try:
                self.window.destroy()
            except tk.TclError:
                pass

        self.window = None
        self._container = None
        self._icon_label = None
        self._text_label = None
        print("[MIC_OVERLAY] Hidden")

    def _ensure_window(self) -> None:
        """Create the overlay window if it does not exist."""
        parent = None
        try:
            if self._root and self._root.winfo_exists():
                parent = self._root
        except tk.TclError:
            parent = None

        if self.window and self.window.winfo_exists():
            return

        try:
            self.window = tk.Toplevel(parent) if parent else tk.Toplevel()
        except tk.TclError:
            self.window = None
            return

        self.window.title("Dictation Active")
        self.window.overrideredirect(True)  # Remove window decorations
        try:
            self.window.attributes('-topmost', True)  # Always on top
            self.window.attributes('-alpha', 0.95)
        except tk.TclError:
            pass

        width = 200
        height = 130
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = screen_height - height - 100  # 100px from bottom
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        self.window.configure(bg='#1e1e1e')
        self._container = tk.Frame(self.window, bg='#1e1e1e')
        self._container.pack(expand=True, fill='both')

        self._icon_label = tk.Label(self._container, bg='#1e1e1e')

        self._text_label = tk.Label(
            self._container,
            text="CorreX is listning...",
            fg='#FFFFFF',
            bg='#1e1e1e',
            font=('Segoe UI', 12, 'bold')
        )
        self._text_label.pack(pady=(40, 0))
    
    def _draw_mic_indicator(self) -> None:
        """Draw the microphone icon and status text."""
        if not self.window:
            return
        if self._mic_icon is None:
            self._load_icon()

        if self._icon_label:
            if self._mic_icon:
                self._icon_label.configure(image=self._mic_icon)
                self._icon_label.image = self._mic_icon
                if not self._icon_label.winfo_ismapped():
                    self._icon_label.pack(pady=(20, 8))
                if self._text_label:
                    self._text_label.pack_configure(pady=(0, 0))
            else:
                self._icon_label.pack_forget()
                if self._text_label:
                    self._text_label.pack_configure(pady=(40, 0))
    
    def _animate_pulse(self) -> None:
        """Animate the pulsing effect on the microphone icon."""
        if not self.is_visible or not self.window:
            return

        if not self._mic_icon:
            return
        
        self._fade_level += 0.05 * self._fade_direction
        if self._fade_level >= 1.0:
            self._fade_level = 1.0
            self._fade_direction = -1
        elif self._fade_level <= 0.35:
            self._fade_level = 0.35
            self._fade_direction = 1

        self._mic_icon = self._create_faded_icon(self._fade_level) or self._mic_icon
        self._draw_mic_indicator()

        self._animation_id = self.window.after(66, self._animate_pulse)

    def _load_icon(self) -> None:
        """Load the base microphone icon image."""
        if self._mic_icon:
            return

        self._mic_path = self._asset_manager.get_icon_path("Mic_icon.ico")
        if _HAS_PIL and self._mic_path:
            try:
                with Image.open(self._mic_path) as img:
                    self._mic_pil_base = img.convert("RGBA")
            except Exception:
                self._mic_pil_base = None

        if self._mic_pil_base is not None:
            self._mic_icon = self._create_faded_icon(self._fade_level)
        else:
            self._mic_icon = self._asset_manager.load_icon(
                "Mic_icon.ico",
                size=(48, 48),
                cache_key="mic_overlay_static"
            )

    def _create_faded_icon(self, intensity: float) -> Optional[tk.PhotoImage]:
        """Build a PhotoImage with the requested alpha intensity."""
        if not _HAS_PIL or self._mic_pil_base is None:
            if self.window:
                try:
                    self.window.attributes('-alpha', max(0.4, min(1.0, intensity)))
                except tk.TclError:
                    pass
            return None

        try:
            resample = getattr(Image, "Resampling", None)
            resample_mode = getattr(resample, "LANCZOS", getattr(Image, "LANCZOS", None)) if resample else getattr(Image, "LANCZOS", None)
            base = self._mic_pil_base.resize((48, 48), resample=resample_mode) if resample_mode else self._mic_pil_base
            base = base.copy()
            r, g, b, a = base.split()
            alpha = a.point(lambda value: int(value * intensity))
            base.putalpha(alpha)
            return ImageTk.PhotoImage(base)
        except Exception:
            return None
