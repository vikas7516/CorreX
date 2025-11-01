"""Centralized asset manager for CorreX application resources."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None  # type: ignore[assignment]
    ImageTk = None  # type: ignore[assignment]

import tkinter as tk


class AssetManager:
    """Manages all application assets (images, icons, animations)."""
    
    def __init__(self):
        """Initialize asset manager and locate assets directory."""
        self.assets_root = self._find_assets_root()
        self.icons_dir = self.assets_root / "icons" if self.assets_root else None
        self.images_dir = self.assets_root / "images" if self.assets_root else None
        self.animations_dir = self.assets_root / "animations" if self.assets_root else None
        
        # Cache for loaded images to prevent garbage collection
        self._image_cache: dict[str, tk.PhotoImage] = {}
    
    def _find_assets_root(self) -> Optional[Path]:
        """Find the assets directory by searching parent directories."""
        # Start from this file's location
        current = Path(__file__).resolve()
        
        # Search up to 3 parent levels
        for parent in [current.parent, current.parent.parent, current.parent.parent.parent]:
            assets_dir = parent / "assets"
            if assets_dir.exists() and assets_dir.is_dir():
                return assets_dir
        
        return None
    
    def get_icon_path(self, icon_name: str) -> Optional[Path]:
        """Get path to an icon file with graceful extension fallbacks."""
        if not self.icons_dir:
            return None

        candidates: list[str] = []
        base_name = icon_name
        suffix = ""

        if "." in icon_name:
            base_name, suffix = icon_name.rsplit(".", 1)
            candidates.append(icon_name)
            if suffix.lower() == "png":
                candidates.append(f"{base_name}.ico")
            elif suffix.lower() == "ico":
                candidates.append(f"{base_name}.png")
        else:
            candidates.extend([icon_name, f"{icon_name}.png", f"{icon_name}.ico"])

        if suffix.lower() not in {"png", "ico"}:
            candidates.extend([f"{base_name}.png", f"{base_name}.ico"])

        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            icon_path = self.icons_dir / candidate
            if icon_path.exists():
                return icon_path
        return None
    
    def get_image_path(self, image_name: str) -> Optional[Path]:
        """Get path to an image file."""
        if not self.images_dir:
            return None
        
        image_path = self.images_dir / image_name
        return image_path if image_path.exists() else None
    
    def get_animation_path(self, animation_name: str) -> Optional[Path]:
        """Get path to an animation file."""
        if not self.animations_dir:
            return None
        
        animation_path = self.animations_dir / animation_name
        return animation_path if animation_path.exists() else None
    
    def load_image(
        self,
        image_name: str,
        size: Optional[tuple[int, int]] = None,
        cache_key: Optional[str] = None
    ) -> Optional[tk.PhotoImage]:
        """
        Load an image from the images directory.
        
        Args:
            image_name: Name of the image file
            size: Optional (width, height) tuple to resize
            cache_key: Optional key for caching (default: image_name)
        
        Returns:
            PhotoImage object or None if loading fails
        """
        cache_key = cache_key or f"{image_name}_{size}"
        
        # Return cached image if available
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]
        
        image_path = self.get_image_path(image_name)
        if not image_path:
            return None
        
        try:
            if HAS_PIL and size:
                # Use PIL for resizing
                with Image.open(image_path) as pil_image:
                    pil_image = pil_image.convert("RGBA")
                    
                    if hasattr(Image, "Resampling"):
                        resample = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
                    else:
                        resample = Image.LANCZOS  # type: ignore[attr-defined]
                    
                    resized = pil_image.resize(size, resample)
                    photo = ImageTk.PhotoImage(resized)
            else:
                # Use Tkinter's PhotoImage directly
                photo = tk.PhotoImage(file=str(image_path))
            
            # Cache the image
            self._image_cache[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"[ASSET] Failed to load image '{image_name}': {e}")
            return None
    
    def load_icon(
        self,
        icon_name: str,
        size: Optional[tuple[int, int]] = None,
        cache_key: Optional[str] = None
    ) -> Optional[tk.PhotoImage]:
        """
        Load an icon from the icons directory.
        
        Args:
            icon_name: Name of the icon file
            size: Optional (width, height) tuple to resize
            cache_key: Optional key for caching (default: icon_name)
        
        Returns:
            PhotoImage object or None if loading fails
        """
        cache_key = cache_key or f"icon_{icon_name}_{size}"
        
        # Return cached icon if available
        if cache_key in self._image_cache:
            return self._image_cache[cache_key]
        
        icon_path = self.get_icon_path(icon_name)
        if not icon_path:
            return None
        
        try:
            if HAS_PIL and size:
                # Use PIL for resizing
                with Image.open(icon_path) as pil_image:
                    pil_image = pil_image.convert("RGBA")
                    
                    if hasattr(Image, "Resampling"):
                        resample = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
                    else:
                        resample = Image.LANCZOS  # type: ignore[attr-defined]
                    
                    resized = pil_image.resize(size, resample)
                    photo = ImageTk.PhotoImage(resized)
            else:
                # Use Tkinter's PhotoImage directly
                photo = tk.PhotoImage(file=str(icon_path))
            
            # Cache the icon
            self._image_cache[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"[ASSET] Failed to load icon '{icon_name}': {e}")
            return None
    
    def create_ico_from_png(self, png_name: str, output_name: str = "app_icon.ico") -> Optional[Path]:
        """
        Create an ICO file from a PNG icon (for Windows taskbar/tray).
        
        Args:
            png_name: Name of the PNG file in icons directory
            output_name: Name for the output ICO file
        
        Returns:
            Path to created ICO file or None if failed
        """
        icon_path = self.get_icon_path(png_name)
        if not icon_path:
            return None
        
        output_dir = Path.home() / ".correx"
        output_dir.mkdir(parents=True, exist_ok=True)
        ico_path = output_dir / output_name

        if not HAS_PIL:
            try:
                png_bytes = icon_path.read_bytes()
                if not png_bytes.startswith(b"\x89PNG"):
                    return None

                # Extract width and height from PNG header (IHDR chunk)
                width = int.from_bytes(png_bytes[16:20], "big")
                height = int.from_bytes(png_bytes[20:24], "big")

                width_byte = width if 0 < width < 256 else 0
                height_byte = height if 0 < height < 256 else 0

                icon_dir = struct.pack("<HHH", 0, 1, 1)
                entry = struct.pack(
                    "<BBBBHHII",
                    width_byte,
                    height_byte,
                    0,
                    0,
                    1,
                    32,
                    len(png_bytes),
                    6 + 16,
                )

                with open(ico_path, "wb") as ico_file:
                    ico_file.write(icon_dir)
                    ico_file.write(entry)
                    ico_file.write(png_bytes)

                return ico_path
            except Exception as fallback_error:
                print(f"[ASSET] Failed to build ICO without Pillow: {fallback_error}")
                return None
        
        try:
            with Image.open(icon_path) as pil_image:
                pil_image = pil_image.convert("RGBA")
                
                # Create multiple sizes for ICO
                icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
                
                if hasattr(Image, "Resampling"):
                    resample = Image.Resampling.LANCZOS  # type: ignore[attr-defined]
                else:
                    resample = Image.LANCZOS  # type: ignore[attr-defined]
                
                # Make image square
                base_w, base_h = pil_image.size
                max_dim = max(base_w, base_h)
                canvas = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                offset = ((max_dim - base_w) // 2, (max_dim - base_h) // 2)
                canvas.paste(pil_image, offset, pil_image)
                
                # Save as ICO with multiple sizes
                canvas.save(ico_path, format="ICO", sizes=icon_sizes)
                
                return ico_path
                
        except Exception as e:
            print(f"[ASSET] Failed to create ICO from '{png_name}': {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the image cache to free memory."""
        self._image_cache.clear()


# Global asset manager instance
_asset_manager: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    """Get the global asset manager instance."""
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager()
    return _asset_manager
