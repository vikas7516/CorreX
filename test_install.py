#!/usr/bin/env python3
"""Quick test script to verify CorreX installation and basic imports."""
from __future__ import annotations

import sys
from pathlib import Path


def test_imports():
    """Test that all core modules can be imported."""
    print("Testing CorreX imports...\n")
    
    failures = []
    
    # Test package metadata
    try:
        import correX
        print(f"✅ Package: correX v{correX.__version__}")
        print(f"   Author: {correX.__author__}")
        print(f"   License: {correX.__license__}")
    except ImportError as e:
        failures.append(("correX package", str(e)))
        print(f"❌ Failed to import correX: {e}")
    
    # Test core modules
    modules = [
        ("correX.main", "Main entry point"),
        ("correX.autocorrect_service", "Autocorrect service"),
        ("correX.gemini_corrector", "Gemini API corrector"),
        ("correX.keystroke_buffer", "Keystroke buffer"),
        ("correX.text_buffer", "Text buffer"),
        ("correX.config_manager", "Config manager"),
        ("correX.history_manager", "History manager"),
        ("correX.logger", "Logging system"),
        ("correX.asset_manager", "Asset manager"),
        ("correX.gui.app_gui", "GUI application"),
    ]
    
    print("\nCore Modules:")
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name:30s} - {description}")
        except ImportError as e:
            failures.append((module_name, str(e)))
            print(f"❌ {module_name:30s} - FAILED: {e}")
    
    # Test optional modules
    optional_modules = [
        ("correX.dictation_manager", "Dictation manager"),
        ("correX.tray_icon", "System tray icon"),
        ("correX.loading_overlay", "Loading overlay"),
        ("correX.mic_overlay", "Microphone overlay"),
    ]
    
    print("\nOptional Modules:")
    for module_name, description in optional_modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name:30s} - {description}")
        except ImportError as e:
            print(f"⚠️  {module_name:30s} - Not available: {e}")
    
    return failures


def test_dependencies():
    """Test that required dependencies are installed."""
    print("\n" + "="*60)
    print("Testing Dependencies...\n")
    
    dependencies = [
        ("google.generativeai", "Google Gemini API", True),
        ("keyboard", "Keyboard hooks", True),
        ("win32gui", "Windows API (pywin32)", True),
        ("pywinauto", "GUI automation", True),
        ("PIL", "Pillow (Image processing)", True),
        ("pystray", "System tray icon", False),
        ("speech_recognition", "Speech recognition", False),
        ("pyaudio", "Audio I/O", False),
        ("noisereduce", "Noise reduction", False),
        ("numpy", "Numerical computing", False),
    ]
    
    missing_required = []
    missing_optional = []
    
    for module_name, description, required in dependencies:
        try:
            __import__(module_name)
            print(f"✅ {module_name:30s} - {description}")
        except ImportError:
            if required:
                missing_required.append((module_name, description))
                print(f"❌ {module_name:30s} - REQUIRED: {description}")
            else:
                missing_optional.append((module_name, description))
                print(f"⚠️  {module_name:30s} - Optional: {description}")
    
    return missing_required, missing_optional


def test_assets():
    """Test that asset files are present."""
    print("\n" + "="*60)
    print("Testing Assets...\n")
    
    # Try to find assets directory
    possible_paths = [
        Path("assets"),
        Path("correX/assets"),
        Path(__file__).parent / "assets",
        Path(__file__).parent / "correX" / "assets",
    ]
    
    assets_dir = None
    for path in possible_paths:
        if path.exists():
            assets_dir = path
            break
    
    if not assets_dir:
        print("⚠️  Assets directory not found in expected locations")
        return False
    
    print(f"✅ Assets directory: {assets_dir}")
    
    # Check for icon files
    icons_dir = assets_dir / "icons"
    if icons_dir.exists():
        icons = list(icons_dir.glob("*.ico"))
        print(f"✅ Found {len(icons)} icon files:")
        for icon in icons:
            print(f"   - {icon.name}")
    else:
        print("⚠️  Icons directory not found")
    
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("CorreX Installation Test")
    print("="*60)
    print()
    
    # Test imports
    import_failures = test_imports()
    
    # Test dependencies
    missing_required, missing_optional = test_dependencies()
    
    # Test assets
    test_assets()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    if import_failures:
        print(f"\n❌ {len(import_failures)} module import(s) failed:")
        for module, error in import_failures:
            print(f"   - {module}: {error}")
    else:
        print("\n✅ All core modules imported successfully")
    
    if missing_required:
        print(f"\n❌ {len(missing_required)} required dependencies missing:")
        for module, desc in missing_required:
            print(f"   - {module}: {desc}")
        print("\nInstall with: pip install -r correX/requirements.txt")
    else:
        print("\n✅ All required dependencies installed")
    
    if missing_optional:
        print(f"\n⚠️  {len(missing_optional)} optional dependencies missing:")
        for module, desc in missing_optional:
            print(f"   - {module}: {desc}")
        print("\nThese are optional but recommended for full functionality")
    
    # Exit code
    if import_failures or missing_required:
        print("\n❌ Tests FAILED - Installation incomplete")
        sys.exit(1)
    else:
        print("\n✅ Tests PASSED - Installation looks good!")
        print("\nYou can now run CorreX with: python -m correX")
        sys.exit(0)


if __name__ == "__main__":
    main()
