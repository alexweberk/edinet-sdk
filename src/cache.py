"""
Caching layer for EDINET API responses with TTL support.

This module provides a simple file-based caching system for API responses
and document downloads to reduce redundant requests to the EDINET API.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


class CacheManager:
    """
    File-based cache manager with TTL (Time To Live) support.

    Provides caching for both JSON-serializable data and binary content.
    """

    def __init__(self, cache_dir: str = ".cache", default_ttl: int = 3600):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files.
            default_ttl: Default time-to-live in seconds (default: 1 hour).
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl

        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """
        Generate a filesystem-safe cache key using SHA256 hash.

        Args:
            key: Original cache key.

        Returns:
            Hashed cache key safe for filesystem use.
        """
        return hashlib.sha256(key.encode()).hexdigest()

    def _get_cache_path(self, key: str, is_binary: bool = False) -> Path:
        """
        Get the full path for a cache file.

        Args:
            key: Cache key.
            is_binary: Whether this is binary content (affects file extension).

        Returns:
            Path to the cache file.
        """
        cache_key = self._get_cache_key(key)
        extension = ".bin" if is_binary else ".json"
        return self.cache_dir / f"{cache_key}{extension}"

    def _is_expired(self, filepath: Path, ttl: int) -> bool:
        """
        Check if a cache file has expired.

        Args:
            filepath: Path to the cache file.
            ttl: Time-to-live in seconds.

        Returns:
            True if the file has expired or doesn't exist.
        """
        if not filepath.exists():
            return True

        file_age = time.time() - filepath.stat().st_mtime
        return file_age > ttl

    def get_json(self, key: str, ttl: int | None = None) -> Any | None:
        """
        Retrieve JSON-serializable data from cache.

        Args:
            key: Cache key.
            ttl: Time-to-live in seconds. If None, uses default_ttl.

        Returns:
            Cached data if valid and not expired, None otherwise.
        """
        ttl = ttl if ttl is not None else self.default_ttl
        cache_path = self._get_cache_path(key, is_binary=False)

        if self._is_expired(cache_path, ttl):
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            # If we can't read the cache file, treat it as a cache miss
            return None

    def set_json(self, key: str, data: Any) -> bool:
        """
        Store JSON-serializable data in cache.

        Args:
            key: Cache key.
            data: Data to cache (must be JSON-serializable).

        Returns:
            True if successfully cached, False otherwise.
        """
        cache_path = self._get_cache_path(key, is_binary=False)

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except (OSError, TypeError) as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to cache data for key {key}: {e}")
            return False

    def get_binary(self, key: str, ttl: int | None = None) -> bytes | None:
        """
        Retrieve binary data from cache.

        Args:
            key: Cache key.
            ttl: Time-to-live in seconds. If None, uses default_ttl.

        Returns:
            Cached binary data if valid and not expired, None otherwise.
        """
        ttl = ttl if ttl is not None else self.default_ttl
        cache_path = self._get_cache_path(key, is_binary=True)

        if self._is_expired(cache_path, ttl):
            return None

        try:
            with open(cache_path, "rb") as f:
                return f.read()
        except (FileNotFoundError, OSError):
            # If we can't read the cache file, treat it as a cache miss
            return None

    def set_binary(self, key: str, data: bytes) -> bool:
        """
        Store binary data in cache.

        Args:
            key: Cache key.
            data: Binary data to cache.

        Returns:
            True if successfully cached, False otherwise.
        """
        cache_path = self._get_cache_path(key, is_binary=True)

        try:
            with open(cache_path, "wb") as f:
                f.write(data)
            return True
        except OSError as e:
            # Log error but don't fail the operation
            print(f"Warning: Failed to cache binary data for key {key}: {e}")
            return False

    def clear_expired(self) -> int:
        """
        Remove all expired cache files.

        Returns:
            Number of files removed.
        """
        removed_count = 0

        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                # Use default TTL for cleanup
                if self._is_expired(cache_file, self.default_ttl):
                    try:
                        cache_file.unlink()
                        removed_count += 1
                    except OSError:
                        # Skip files we can't remove
                        continue

        return removed_count

    def clear_all(self) -> int:
        """
        Remove all cache files.

        Returns:
            Number of files removed.
        """
        removed_count = 0

        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                try:
                    cache_file.unlink()
                    removed_count += 1
                except OSError:
                    # Skip files we can't remove
                    continue

        return removed_count

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        if not self.cache_dir.exists():
            return {
                "cache_dir": str(self.cache_dir),
                "total_files": 0,
                "total_size_bytes": 0,
                "json_files": 0,
                "binary_files": 0,
            }

        json_files = 0
        binary_files = 0
        total_size = 0

        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                total_size += cache_file.stat().st_size
                if cache_file.suffix == ".json":
                    json_files += 1
                elif cache_file.suffix == ".bin":
                    binary_files += 1

        return {
            "cache_dir": str(self.cache_dir),
            "total_files": json_files + binary_files,
            "total_size_bytes": total_size,
            "json_files": json_files,
            "binary_files": binary_files,
        }
