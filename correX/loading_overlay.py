"""Floating loading indicator overlay that appears on screen during API calls.

This implementation intentionally avoids external image/animation assets and
renders a smooth spinner using Tkinter's Canvas. It is lightweight and
portable, and keeps the same public API as before:

    - create_window(root)
    - enable_dragging(enabled)
    - set_position_callback(cb)
    - set_position(x, y)
    - show()
    - hide()
    - is_visible()
    - destroy()
"""
from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Callable


class LoadingOverlay:
    """Tiny floating loading indicator that appears over all windows."""
    
    def __init__(self, position: tuple[int, int] = (50, 50)):
        """
        Initialize the loading overlay.
        
        Args:
            position: (x, y) screen position in pixels from top-left
        """
        self.position = position
        self.window: Optional[tk.Toplevel] = None
        self.root: Optional[tk.Tk] = None
        self.animation_running = False
        self._angle = 0.0              # Current spinner angle in degrees
        self._speed = 6.0              # Degrees per frame (higher = faster)
        self._thickness = 6            # Arc thickness in pixels
        self._radius = 22              # Radius for spinner circle
        self._color_bg = "#f0f0f0"     # Window bg (transparentcolor where supported)
        self._color_arc = "#2196F3"    # Primary spinner color
        self._color_trail = "#90CAF9"  # Trail color for nicer look
        self.canvas: Optional[tk.Canvas] = None
        self._arc_items: list[int] = []
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.position_callback: Optional[Callable[[int, int], None]] = None
    
    def create_window(self, root: tk.Tk) -> None:
        """Create the overlay window (call once during app init)."""
        self.root = root
        self.window = tk.Toplevel(root)
        
        # Make it floating and borderless
        self.window.withdraw()  # Start hidden
        self.window.overrideredirect(True)  # Remove window decorations
        self.window.attributes('-topmost', True)  # Always on top
        
        # Platform-specific transparency
        try:
            self.window.attributes('-transparentcolor', self._color_bg)  # Transparent background
        except tk.TclError:
            pass  # Not supported on all platforms
        
        try:
            self.window.attributes('-alpha', 0.95)  # Slight transparency
        except tk.TclError:
            pass
        
        # Position with validation
        x, y = self.position
        x = max(0, min(x, 1920))  # Clamp to reasonable screen bounds
        y = max(0, min(y, 1080))
        self.position = (x, y)
        self.window.geometry(f"+{x}+{y}")
        
        # Create canvas-based spinner (no external assets)
        size = (self._radius * 2) + (self._thickness * 2)
        self.canvas = tk.Canvas(
            self.window,
            width=size,
            height=size,
            bg=self._color_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(padx=8, pady=8)
        self._draw_static_background()
        
        # Bind mouse events for dragging
        self.canvas.bind('<Button-1>', self._start_drag)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._stop_drag)

    def _draw_static_background(self) -> None:
        """Draw the faint trail circle as a background for the spinner."""
        if not self.canvas:
            return
        size = (self._radius * 2) + (self._thickness * 2)
        cx, cy = size // 2, size // 2
        r = self._radius
        # Faint circular trail
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=self._color_trail,
            width=self._thickness,
        )
        
    def enable_dragging(self, enabled: bool) -> None:
        """Enable or disable dragging of the overlay."""
        self.dragging = enabled
        if enabled and self.window:
            # Show semi-transparent placeholder when dragging is enabled
            self.window.deiconify()
            if self.canvas:
                # Draw a static orange dot to indicate the overlay position
                self.canvas.delete("all")
                size = (self._radius * 2) + (self._thickness * 2)
                cx, cy = size // 2, size // 2
                self.canvas.create_oval(
                    cx - 6, cy - 6, cx + 6, cy + 6,
                    fill="#FF9800",
                    outline="",
                )
        elif not enabled and self.window and not self.animation_running:
            self.window.withdraw()
    
    def set_position_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback to be called when position changes via drag."""
        self.position_callback = callback
    
    def _start_drag(self, event) -> None:
        """Start dragging the overlay."""
        if not self.dragging:
            return
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def _on_drag(self, event) -> None:
        """Handle dragging motion."""
        if not self.dragging or not self.window:
            return
        
        # Calculate new position
        x = self.window.winfo_x() + (event.x - self.drag_start_x)
        y = self.window.winfo_y() + (event.y - self.drag_start_y)
        
        # Clamp to screen bounds
        x = max(0, min(x, 2000))
        y = max(0, min(y, 2000))
        
        # Update position
        self.position = (x, y)
        self.window.geometry(f"+{x}+{y}")
        
        # Notify callback
        if self.position_callback:
            self.position_callback(x, y)
    
    def _stop_drag(self, event) -> None:
        """Stop dragging the overlay."""
        pass  # Position already updated during drag
        
    def set_position(self, x: int, y: int) -> None:
        """Update the overlay position with validation."""
        # Validate and clamp position
        x = max(0, min(x, 2000))
        y = max(0, min(y, 2000))
        self.position = (x, y)
        
        if self.window and self.window.winfo_exists():
            try:
                self.window.geometry(f"+{x}+{y}")
            except tk.TclError:
                pass  # Window may be destroyed
    
    def show(self) -> None:
        """Show the loading indicator and start animation (THREAD-SAFE)."""
        if not self.window or not self.root:
            return
        
        # Use after_idle to ensure we're on the main thread
        try:
            self.root.after_idle(self._show_internal)
        except tk.TclError:
            pass  # Root window may be destroyed
    
    def _show_internal(self) -> None:
        """Internal show method (runs on main thread)."""
        if not self.root or not self.root.winfo_exists():
            return
            
        if not self.window or not self.window.winfo_exists():
            return
        
        if self.dragging:
            return  # Don't interfere with positioning mode
            
        try:
            self.animation_running = True
            self._angle = 0.0
            self.window.deiconify()  # Show window
            # Redraw background trail before animation
            if self.canvas:
                self.canvas.delete("all")
                self._draw_static_background()
            self._animate()
        except tk.TclError:
            pass  # Window may be destroyed
    
    def hide(self) -> None:
        """Hide the loading indicator and stop animation (THREAD-SAFE)."""
        if not self.window or not self.root:
            return
        
        # Use after_idle to ensure we're on the main thread
        try:
            self.root.after_idle(self._hide_internal)
        except tk.TclError:
            pass  # Root window may be destroyed
    
    def _hide_internal(self) -> None:
        """Internal hide method (runs on main thread)."""
        self.animation_running = False
        
        if self.dragging:
            return  # Keep visible in positioning mode
        
        if not self.root or not self.root.winfo_exists():
            return
        
        if self.window and self.window.winfo_exists():
            try:
                self.window.withdraw()  # Hide window
            except tk.TclError:
                pass  # Window may be destroyed
        # Reset canvas content
        if self.canvas and self.canvas.winfo_exists():
            try:
                self.canvas.delete("all")
            except tk.TclError:
                pass
        self._angle = 0.0
    
    def _animate(self) -> None:
        """Animate the canvas-based spinner by rotating arc segments."""
        if not self.animation_running:
            return
        if not self.root or not self.root.winfo_exists():
            self.animation_running = False
            return
        if not self.window or not self.window.winfo_exists():
            self.animation_running = False
            return
        if not self.canvas or not self.canvas.winfo_exists():
            self.animation_running = False
            return

        try:
            # Clear previous arc items
            for item in self._arc_items:
                try:
                    self.canvas.delete(item)
                except tk.TclError:
                    pass
            self._arc_items.clear()

            # Compute arc bounding box
            size = (self._radius * 2) + (self._thickness * 2)
            cx, cy = size // 2, size // 2
            r = self._radius
            bbox = (cx - r, cy - r, cx + r, cy + r)

            # Draw two arc segments to create a smooth spinner effect
            # Leading arc (primary color)
            extent = 120  # degrees
            lead = self.canvas.create_arc(
                *bbox,
                start=self._angle,
                extent=extent,
                style=tk.ARC,
                outline=self._color_arc,
                width=self._thickness,
            )
            self._arc_items.append(lead)

            # Trailing arc (lighter color) offset by 180 degrees
            trail = self.canvas.create_arc(
                *bbox,
                start=(self._angle + 180) % 360,
                extent=extent,
                style=tk.ARC,
                outline=self._color_trail,
                width=self._thickness,
            )
            self._arc_items.append(trail)

            # Increment angle for next frame
            self._angle = (self._angle + self._speed) % 360

            # Schedule next frame (higher FPS for smoothness)
            self.window.after(33, self._animate)  # ~30 FPS
        except tk.TclError:
            self.animation_running = False  # Stop on error
    
    def is_visible(self) -> bool:
        """Check if overlay is currently visible."""
        return self.animation_running
    
    def destroy(self) -> None:
        """Clean up the overlay window."""
        self.animation_running = False
        self.dragging = False
        if self.window and self.window.winfo_exists():
            try:
                self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.canvas = None
        self.root = None
