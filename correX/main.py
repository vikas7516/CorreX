"""Application entry point wiring together background service and optional GUI."""
from __future__ import annotations

import argparse
import logging
import os
import threading
from pathlib import Path
from typing import Optional

if __package__:
    from .autocorrect_service import AutoCorrectService
    from .gemini_corrector import GeminiCorrector
    from .gui.app_gui import launch_app, focus_existing_window
    from .asset_manager import get_asset_manager
    from .logger import CorreXLogger

    try:
        from .config_manager import ConfigManager
        from .history_manager import HistoryManager
        from .tray_icon import TrayIcon
    except ImportError as e:
        print(f"[WARNING] Some modules not available: {e}")
        ConfigManager = None
        HistoryManager = None
        TrayIcon = None
else:
    # Allow running as a script (python correX/main.py) by fixing sys.path
    import sys

    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.append(str(package_root))

    from correX.autocorrect_service import AutoCorrectService  # type: ignore[import-not-found]
    from correX.gemini_corrector import GeminiCorrector  # type: ignore[import-not-found]
    from correX.gui.app_gui import launch_app, focus_existing_window  # type: ignore[import-not-found]
    from correX.asset_manager import get_asset_manager  # type: ignore[import-not-found]
    from correX.logger import CorreXLogger  # type: ignore[import-not-found]

    try:
        from correX.config_manager import ConfigManager  # type: ignore[import-not-found]
        from correX.history_manager import HistoryManager  # type: ignore[import-not-found]
        from correX.tray_icon import TrayIcon  # type: ignore[import-not-found]
    except ImportError as e:
        print(f"[WARNING] Some modules not available: {e}")
        ConfigManager = None
        HistoryManager = None
        TrayIcon = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CorreX - AI-Powered Text Correction with Gemini")
    parser.add_argument("--api-key", type=str, default=None, help="Gemini API key (or set GEMINI_API_KEY env var)")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash-exp", help="Gemini model to use")
    parser.add_argument("--no-gui", action="store_true", help="Run the background service without launching the configuration window")
    parser.add_argument("--show-gui", action="store_true", help="Open the configuration window immediately on startup")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress all console output except errors")
    parser.add_argument("--log-file", type=str, default=None, help="Write logs to specified file")
    return parser.parse_args()


def main() -> None:
    """Main application entry point with comprehensive error handling."""
    try:
        args = parse_args()

        # Setup logging based on command-line arguments
        log_level = logging.ERROR if args.quiet else (logging.DEBUG if args.verbose else logging.INFO)
        log_file = Path(args.log_file) if args.log_file else None
        
        CorreXLogger.setup(
            level=log_level,
            log_file=log_file,
            console=not args.quiet
        )

        print(f"[INFO] Starting CorreX with Google Gemini API")
        print(f"[INFO] Default Model: {args.model}")
        if args.verbose:
            print(f"[INFO] Logging level: DEBUG")
        if log_file:
            print(f"[INFO] Writing logs to: {log_file}")

        # Initialize config manager
        config = ConfigManager() if ConfigManager else None
        minimize_to_tray = True
        if config:
            print(f"[INFO] Configuration loaded from: {config.config_file}")
            try:
                minimize_to_tray = config.should_minimize_to_tray()
            except Exception as config_error:
                print(f"[WARNING] Failed to read 'minimize_to_tray' from config: {config_error}")
        
        # Initialize history manager
        history = HistoryManager() if HistoryManager else None
        if history:
            print(f"[INFO] History database: {history.db_file}")

        # Try to initialize Gemini corrector
        corrector = None
        api_key = args.api_key or (config.get_api_key() if config else None) or os.getenv("GEMINI_API_KEY")
        model_name = (config.get_model_name() if config else None) or args.model
        
        if api_key:
            try:
                print(f"[INFO] API key found - initializing Gemini...")
                corrector = GeminiCorrector(api_key=api_key, model_name=model_name)
                print(f"[INFO] ✓ Gemini initialized successfully")
            except Exception as e:
                print(f"[WARNING] Failed to initialize Gemini: {e}")
                print(f"[INFO] You can set the API key in the GUI")
                corrector = None
        else:
            print(f"[INFO] No API key found - please configure in GUI")
            print(f"[INFO] Get your key: https://makersuite.google.com/app/apikey")

        # Create with dummy key if none exists (allows GUI to launch)
        if corrector is None:
            try:
                corrector = GeminiCorrector(api_key="dummy-key-replace-in-gui", model_name=model_name, allow_dummy=True)
                print(f"[INFO] Using placeholder - configure API key in GUI to activate")
            except Exception as e:
                print(f"[ERROR] Failed to create placeholder corrector: {e}")
                print(f"[ERROR] Cannot proceed without corrector object")
                return

        # Trigger-based autocorrect service with instant buffer replacement
        print(f"[INFO] Initializing trigger-based autocorrect service...")
        try:
            trigger_key = AutoCorrectService.normalize_trigger_key("ctrl+space") or "ctrl+space"
            if config:
                configured_trigger = config.get_trigger_key()
                if isinstance(configured_trigger, str):
                    normalized_trigger = AutoCorrectService.normalize_trigger_key(configured_trigger)
                    if normalized_trigger:
                        trigger_key = normalized_trigger

            clear_trigger = AutoCorrectService.normalize_trigger_key("ctrl+shift+delete") or "ctrl+shift+delete"
            if config:
                configured_clear = config.get_clear_buffer_trigger_key()
                if isinstance(configured_clear, str):
                    normalized_clear = AutoCorrectService.normalize_trigger_key(configured_clear)
                    if not configured_clear.strip():
                        clear_trigger = ""
                    elif normalized_clear:
                        if normalized_clear == trigger_key:
                            print(f"[WARNING] Clear-buffer trigger '{normalized_clear}' matches correction trigger; disabling clear trigger")
                            clear_trigger = ""
                        else:
                            clear_trigger = normalized_clear
                    elif configured_clear.strip():
                        print(f"[WARNING] Invalid clear-buffer trigger in config: {configured_clear} - defaulting to CTRL+SHIFT+DELETE")

            versions = 3
            if config:
                configured_versions = config.get_versions_per_correction()
                if isinstance(configured_versions, int) and 1 <= configured_versions <= GeminiCorrector.MAX_CANDIDATES:
                    versions = configured_versions

            candidate_settings = GeminiCorrector.default_candidate_settings()
            if config:
                try:
                    candidate_settings = config.get_candidate_settings()
                except Exception as candidate_error:
                    print(f"[WARNING] Failed to load candidate personalization: {candidate_error}")
                    candidate_settings = GeminiCorrector.default_candidate_settings()

            dictation_trigger = AutoCorrectService.normalize_trigger_key("ctrl+shift+d") or "ctrl+shift+d"
            if config:
                configured_dictation = config.get("dictation_trigger_key", "ctrl+shift+d")
                if isinstance(configured_dictation, str) and configured_dictation.strip():
                    normalized_dictation = AutoCorrectService.normalize_trigger_key(configured_dictation)
                    if normalized_dictation:
                        if normalized_dictation != trigger_key and normalized_dictation != clear_trigger:
                            dictation_trigger = normalized_dictation
                        else:
                            print(f"[WARNING] Dictation trigger conflicts with other triggers - using default")

            enabled = config.is_paragraph_enabled() if config else True
            if enabled is None:
                enabled = True
            
            service = AutoCorrectService(
                corrector,
                enable_paragraph=enabled,
                trigger_key=trigger_key,
                clear_buffer_trigger_key=clear_trigger,
                dictation_trigger_key=dictation_trigger,
                versions_per_correction=versions,
                    candidate_settings=candidate_settings,
                history_manager=history,
            )
            service.start()
        except Exception as e:
            print(f"[ERROR] Failed to start autocorrect service: {e}")
            import traceback
            traceback.print_exc()
            return

        exit_event = threading.Event()
        gui_active = threading.Event()
        shutdown_once = threading.Event()
        tray_icon = None

        def update_tray_status_from_service(enabled: bool) -> None:
            if tray_icon:
                tray_icon.update_status(enabled)

        def shutdown_service() -> None:
            if shutdown_once.is_set():
                return
            shutdown_once.set()
            try:
                service.stop()
            except Exception as stop_error:
                print(f"[WARNING] Failed to stop service cleanly: {stop_error}")
            if tray_icon:
                try:
                    tray_icon.stop()
                except Exception as tray_error:
                    print(f"[WARNING] Failed to stop tray icon: {tray_error}")
            exit_event.set()

        def handle_toggle(enabled: bool) -> None:
            service.set_paragraph_enabled(enabled)
            if config:
                config.set_paragraph_enabled(enabled)
            state = "enabled" if enabled else "paused"
            print(f"[CONFIG] Auto-correct {state}")

        def handle_exit() -> None:
            print("[INFO] Exiting CorreX")
            shutdown_service()

        def handle_show_gui() -> None:
            if focus_existing_window():
                return
            if gui_active.is_set():
                print("[INFO] Settings window is already open")
                return

            gui_active.set()

            def _open_gui() -> None:
                try:
                    launch_app(
                        service=service,
                        corrector=corrector,
                        config=config,
                        history=history,
                        keep_service_running=True,
                        on_close=gui_active.clear,
                    )
                except Exception as gui_error:
                    print(f"[ERROR] GUI error: {gui_error}")
                    import traceback
                    traceback.print_exc()
                finally:
                    gui_active.clear()

            threading.Thread(target=_open_gui, daemon=True).start()

        service.add_status_listener(update_tray_status_from_service)

        try:
            if args.no_gui:
                if hasattr(corrector, 'is_configured') and corrector.is_configured:
                    print("[INFO] CorreX running in background. Press Ctrl+C to exit.")
                    _block_forever()
                else:
                    print("[ERROR] Cannot run without GUI - API key not configured!")
                    print("[ERROR] Please set GEMINI_API_KEY or run with GUI to configure")
                    shutdown_service()
                    return
            else:
                if TrayIcon is not None:
                    # Use asset manager to get logo path
                    asset_manager = get_asset_manager()
                    logo_path = asset_manager.get_icon_path("CorreX_logo.png")
                    tray_icon = TrayIcon(
                        on_show_gui=handle_show_gui,
                        on_toggle_service=handle_toggle,
                        on_exit=handle_exit,
                        on_clear_saved=service.clear_saved_paragraphs,
                        logo_path=str(logo_path) if logo_path else None,
                        initial_enabled=enabled,
                    )
                    tray_icon.start()
                    print("[INFO] CorreX is running in the system tray.")
                    notify_flag = Path.home() / ".correx" / "tray_tip.flag"
                    try:
                        notify_flag.parent.mkdir(parents=True, exist_ok=True)
                        if not notify_flag.exists():
                            tray_icon.show_notification(
                                "CorreX",
                                "CorreX is now running from the system tray. Click the tray icon to open settings."
                            )
                            notify_flag.write_text("shown", encoding="utf-8")
                    except Exception as notify_error:
                        print(f"[WARNING] Failed to show tray notification: {notify_error}")
                    should_show_gui = args.show_gui
                    if not getattr(corrector, 'is_configured', False):
                        should_show_gui = True
                    if not minimize_to_tray:
                        should_show_gui = True
                    if should_show_gui:
                        handle_show_gui()
                    exit_event.wait()
                else:
                    print("[WARNING] pystray is not available - launching configuration window")
                    launch_app(service=service, corrector=corrector, config=config, history=history)
                    shutdown_service()
        except KeyboardInterrupt:
            print("\n[INFO] Keyboard interrupt detected")
            shutdown_service()
        except Exception as e:
            print(f"\n[ERROR] Application error: {e}")
            import traceback
            traceback.print_exc()
            shutdown_service()
        finally:
            shutdown_service()
    except Exception as e:
        print(f"\n[FATAL] Unhandled error in main: {e}")
        import traceback
        traceback.print_exc()


def _block_forever() -> None:
    stop = threading.Event()
    while True:
        try:
            stop.wait(timeout=3600)
        except KeyboardInterrupt:
            raise


if __name__ == "__main__":
    main()
