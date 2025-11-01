"""Correction history manager using SQLite."""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


class HistoryManager:
    """Manages correction history with SQLite persistence and auto-cleanup."""
    
    def __init__(self, db_file: str = "correx_history.db", auto_cleanup: bool = True):
        """Initialize history manager."""
        self.db_dir = Path.home() / ".correx"
        self.db_dir.mkdir(exist_ok=True)
        self.db_file = self.db_dir / db_file
        self._init_database()
        
        # Auto-cleanup configuration
        self.auto_cleanup = auto_cleanup
        self.cleanup_interval = 3600  # 1 hour in seconds
        self.retention_hours = 1  # Keep corrections for 1 hour only
        
        if self.auto_cleanup:
            self._start_cleanup_thread()
    
    def _init_database(self) -> None:
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                # Improve concurrent access resilience
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")

                # Create corrections table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS corrections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        original_text TEXT NOT NULL,
                        corrected_text TEXT NOT NULL,
                        selected_version INTEGER DEFAULT 1,
                        total_versions INTEGER DEFAULT 1,
                        application TEXT,
                        char_count INTEGER,
                        word_count INTEGER
                    )
                """)

                # Create statistics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date DATE DEFAULT CURRENT_DATE,
                        total_corrections INTEGER DEFAULT 0,
                        total_characters INTEGER DEFAULT 0,
                        total_words INTEGER DEFAULT 0,
                        UNIQUE(date)
                    )
                """)

                # Create index for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON corrections(timestamp DESC)
                """)

            print(f"[HISTORY] Database initialized: {self.db_file}")

        except Exception as e:
            print(f"[ERROR] Failed to initialize database: {e}")
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for automatic cleanup."""
        def cleanup_loop():
            while self.auto_cleanup:
                try:
                    # Sleep for the cleanup interval
                    time.sleep(self.cleanup_interval)
                    
                    # Perform cleanup
                    deleted = self._cleanup_old_corrections()
                    if deleted > 0:
                        print(f"[HISTORY] Auto-cleanup: Removed {deleted} corrections older than {self.retention_hours} hour(s)")
                except Exception as e:
                    print(f"[ERROR] Auto-cleanup failed: {e}")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True, name="HistoryCleanup")
        thread.start()
        print(f"[HISTORY] Auto-cleanup enabled: Corrections kept for {self.retention_hours} hour(s), cleanup every {self.cleanup_interval//60} minutes")
    
    def _cleanup_old_corrections(self) -> int:
        """Remove corrections older than retention period."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                # Calculate cutoff time
                cutoff = datetime.now() - timedelta(hours=self.retention_hours)

                # Delete old corrections
                cursor.execute("""
                    DELETE FROM corrections
                    WHERE timestamp < ?
                """, (cutoff,))

                deleted = cursor.rowcount

                # Also clean up old statistics (keep last 7 days only)
                cursor.execute("""
                    DELETE FROM statistics
                    WHERE date < DATE('now', '-7 days')
                """)

                return deleted

        except Exception as e:
            print(f"[ERROR] Failed to cleanup old corrections: {e}")
            return 0
    
    def stop_auto_cleanup(self) -> None:
        """Stop automatic cleanup."""
        self.auto_cleanup = False
        print(f"[HISTORY] Auto-cleanup stopped")
    
    def add_correction(
        self,
        original: str,
        corrected: str,
        selected_version: int = 1,
        total_versions: int = 1,
        application: Optional[str] = None
    ) -> bool:
        """Add a correction to history."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                # Count words and characters
                char_count = len(corrected)
                word_count = len(corrected.split())

                # Insert correction
                cursor.execute("""
                    INSERT INTO corrections 
                    (original_text, corrected_text, selected_version, total_versions, 
                     application, char_count, word_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (original, corrected, selected_version, total_versions, 
                      application, char_count, word_count))

                # Update daily statistics
                cursor.execute("""
                    INSERT INTO statistics (date, total_corrections, total_characters, total_words)
                    VALUES (DATE('now'), 1, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        total_corrections = total_corrections + 1,
                        total_characters = total_characters + ?,
                        total_words = total_words + ?
                """, (char_count, word_count, char_count, word_count))

                return True

        except Exception as e:
            print(f"[ERROR] Failed to add correction to history: {e}")
            return False
    
    def get_recent_corrections(self, limit: int = 50) -> List[dict]:
        """Get recent corrections."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, timestamp, original_text, corrected_text, 
                           selected_version, total_versions, application
                    FROM corrections
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"[ERROR] Failed to get recent corrections: {e}")
            return []
    
    def get_statistics(self, days: int = 30) -> dict:
        """Get correction statistics for last N days."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                # Get daily stats
                cursor.execute("""
                    SELECT date, total_corrections, total_characters, total_words
                    FROM statistics
                    WHERE date >= DATE('now', '-' || ? || ' days')
                    ORDER BY date DESC
                """, (days,))

                daily_stats = cursor.fetchall()

                # Get total stats
                cursor.execute("""
                    SELECT 
                        SUM(total_corrections) as total_corrections,
                        SUM(total_characters) as total_characters,
                        SUM(total_words) as total_words
                    FROM statistics
                    WHERE date >= DATE('now', '-' || ? || ' days')
                """, (days,))

                totals = cursor.fetchone()

                return {
                    "daily_stats": daily_stats,
                    "total_corrections": totals[0] or 0,
                    "total_characters": totals[1] or 0,
                    "total_words": totals[2] or 0,
                }

        except Exception as e:
            print(f"[ERROR] Failed to get statistics: {e}")
            return {
                "daily_stats": [],
                "total_corrections": 0,
                "total_characters": 0,
                "total_words": 0,
            }
    
    def search_corrections(self, query: str, limit: int = 50) -> List[dict]:
        """Search corrections by text content."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                search_pattern = f"%{query}%"
                cursor.execute("""
                    SELECT id, timestamp, original_text, corrected_text, 
                           selected_version, total_versions, application
                    FROM corrections
                    WHERE original_text LIKE ? OR corrected_text LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (search_pattern, search_pattern, limit))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            print(f"[ERROR] Failed to search corrections: {e}")
            return []
    
    def clear_history(self, older_than_days: Optional[int] = None) -> bool:
        """Clear correction history."""
        try:
            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                if older_than_days:
                    cursor.execute("""
                        DELETE FROM corrections
                        WHERE timestamp < DATE('now', '-' || ? || ' days')
                    """, (older_than_days,))

                    cursor.execute("""
                        DELETE FROM statistics
                        WHERE date < DATE('now', '-' || ? || ' days')
                    """, (older_than_days,))
                else:
                    cursor.execute("DELETE FROM corrections")
                    cursor.execute("DELETE FROM statistics")

                print(f"[HISTORY] History cleared")
                return True

        except Exception as e:
            print(f"[ERROR] Failed to clear history: {e}")
            return False
    
    def export_to_csv(self, output_file: str) -> bool:
        """Export history to CSV file."""
        try:
            import csv

            with sqlite3.connect(self.db_file, timeout=5) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT timestamp, original_text, corrected_text, 
                           selected_version, total_versions, application
                    FROM corrections
                    ORDER BY timestamp DESC
                """)

                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'Timestamp', 'Original Text', 'Corrected Text',
                        'Selected Version', 'Total Versions', 'Application'
                    ])
                    writer.writerows(cursor.fetchall())

            print(f"[HISTORY] Exported to {output_file}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to export history: {e}")
            return False
