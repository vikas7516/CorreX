"""System tray icon manager."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING, Any

from .asset_manager import get_asset_manager

if TYPE_CHECKING:
    import pystray
    from PIL import Image

try:
    import pystray
    from PIL import Image, ImageDraw, ImageEnhance
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    ImageEnhance = None
    print("[ERROR] pystray not installed. Run: pip install pystray Pillow")


class TrayIcon:
    """Manages system tray icon and menu."""
    
    def __init__(
        self,
        on_show_gui: Optional[Callable] = None,
        on_toggle_service: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
        on_clear_saved: Optional[Callable] = None,
        logo_path: Optional[str | Path] = None,
        initial_enabled: bool = True,
    ):
        """Initialize tray icon."""
        self.on_show_gui = on_show_gui
        self.on_toggle_service = on_toggle_service
        self.on_exit = on_exit
        self.on_clear_saved = on_clear_saved
        self.service_enabled = initial_enabled
        
        # Use asset manager to get logo path
        self._asset_manager = get_asset_manager()
        if logo_path:
            self.logo_path = Path(logo_path).expanduser()
        else:
            # Default to CorreX_logo.png from assets
            logo_asset_path = self._asset_manager.get_icon_path("CorreX_logo.png")
            self.logo_path = logo_asset_path if logo_asset_path else None
        
        if self.logo_path and not self.logo_path.exists():
            print(f"[WARNING] Tray logo not found at: {self.logo_path}")
            self.logo_path = None
        
        self._logo_cache: dict[bool, Any] = {}
        
        self.icon = None
        self._running = False
    
    def create_icon_image(self, enabled: bool = True) -> Any:
        """Create tray icon image, preferring the bundled logo when available."""
        if Image is None:
            return None

        if enabled in self._logo_cache:
            return self._logo_cache[enabled]

        if self.logo_path:
            try:
                with Image.open(self.logo_path) as source_image:
                    image = source_image.convert("RGBA")
                    # Use high-quality resampling when available
                    resample = getattr(Image, "LANCZOS", Image.BICUBIC)
                    image = image.resize((64, 64), resample=resample)
                    if not enabled:
                        if ImageEnhance is not None:
                            enhancer = ImageEnhance.Brightness(image)
                            image = enhancer.enhance(0.75)
                        overlay = Image.new("RGBA", image.size, (220, 53, 69, 90))
                        image = Image.alpha_composite(image, overlay)
                    self._logo_cache[enabled] = image
                    return image
            except Exception as e:
                print(f"[WARNING] Failed to load tray logo: {e}")
                self.logo_path = None
                self._logo_cache.clear()

        if ImageDraw is None:
            return None

        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        color = "#10b981" if enabled else "#ef4444"
        padding = 6
        draw.ellipse(
            [padding, padding, width - padding, height - padding],
            fill=color,
            outline='#111827',
            width=2
        )
        text = "CX"
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill='white')
        self._logo_cache[enabled] = image
        return image
    
    def create_menu(self) -> Any:
        """Create tray menu."""
        if pystray is None:
            return None
        items = [
            pystray.MenuItem(
                "Show Settings",
                self._on_show_gui,
                default=True
            ),
            pystray.MenuItem(
                lambda text: f"AutoCorrect: {'ON' if self.service_enabled else 'OFF'}",
                self._on_toggle_service,
                checked=lambda item: self.service_enabled
            )
        ]

        if self.on_clear_saved:
            items.append(pystray.MenuItem("Clear Saved Text", self._on_clear_saved))

        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                self._on_exit
            )
        ])

        return pystray.Menu(*items)
    
    def start(self) -> None:
        """Start the tray icon."""
        if pystray is None:
            print("[ERROR] Cannot start tray - pystray not installed")
            return
        
        if self._running:
            return
        
        self._running = True
        
        # Create icon
        icon_image = self.create_icon_image(self.service_enabled)
        self.icon = pystray.Icon(
            "CorreX",
            icon_image,
            f"CorreX - {'Running' if self.service_enabled else 'Paused'}",
            self.create_menu()
        )
        
        # Run in separate thread
        thread = threading.Thread(target=self._run_icon, daemon=True)
        thread.start()
        
        print("[TRAY] System tray icon started")
    
    def _run_icon(self) -> None:
        """Run the icon (blocking call)."""
        try:
            self.icon.run()
        except Exception as e:
            print(f"[ERROR] Tray icon error: {e}")
    
    def stop(self) -> None:
        """Stop the tray icon."""
        if self.icon and self._running:
            self.icon.stop()
            self._running = False
            print("[TRAY] System tray icon stopped")
    
    def update_status(self, enabled: bool) -> None:
        """Update service status in tray."""
        self.service_enabled = enabled
        
        if self.icon:
            self.icon.icon = self.create_icon_image(enabled)
            self.icon.title = f"CorreX - {'Running' if enabled else 'Paused'}"
            
            # Update menu
            self.icon.menu = self.create_menu()
    
    def show_notification(self, title: str, message: str) -> None:
        """Show system tray notification."""
        delivered = False
        if self.icon and self._running:
            try:
                self.icon.notify(message, title)
                delivered = True
            except Exception as e:
                print(f"[ERROR] Failed to show notification: {e}")
        if not delivered:
            self._fallback_notification(title, message)

    def _fallback_notification(self, title: str, message: str) -> None:
        """Fallback notification path when native tray notifications fail."""
        if os.name == "nt":
            try:
                import ctypes

                def _show_box() -> None:
                    try:
                        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
                            None,
                            message,
                            title,
                            0x00000040 | 0x00010000  # MB_ICONINFORMATION | MB_SETFOREGROUND
                        )
                    except Exception:
                        pass

                threading.Thread(target=_show_box, daemon=True).start()
                return
            except Exception as fallback_error:
                print(f"[WARNING] Tray notification fallback failed: {fallback_error}")

        print(f"[NOTICE] {title}: {message}")
    
    def _on_show_gui(self, icon, item) -> None:
        """Handle show GUI menu item."""
        if self.on_show_gui:
            self.on_show_gui()
    
    def _on_toggle_service(self, icon, item) -> None:
        """Handle toggle service menu item."""
        self.service_enabled = not self.service_enabled
        if self.on_toggle_service:
            self.on_toggle_service(self.service_enabled)
        self.update_status(self.service_enabled)
    
    def _on_clear_saved(self, icon, item) -> None:
        """Handle clear saved text menu item."""
        if self.on_clear_saved:
            self.on_clear_saved()

    def _on_exit(self, icon, item) -> None:
        """Handle exit menu item."""
        if self.on_exit:
            self.on_exit()
        self.stop()
