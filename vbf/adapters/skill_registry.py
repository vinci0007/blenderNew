# SkillRegistry - Singleton for centralized skill management
"""Skill registry singleton for caching and managing skills loaded from Blender via RPC.

This module provides a thread-safe singleton that:
- Caches skills globally to avoid repeated RPC calls
- Supports multiple clients (VBFClient instances)
- Provides skill validation and lookup utilities

Usage:
    from vbf.adapters.skill_registry import SkillRegistry

    registry = SkillRegistry.get_instance()
    await registry.load_skills(client)
    skills = registry.list_skills()
    registry.validate_skill("create_primitive")  # -> True/False
"""

import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import VBFClient


class SkillRegistry:
    """Singleton skill registry with global caching.

    Skills are loaded once and cached globally, shared across all adapter instances.
    Thread-safe for concurrent access.
    """

    _instance: Optional["SkillRegistry"] = None
    _lock: asyncio.Lock = None
    _sync_lock = None  # For non-async contexts

    def __init__(self):
        """Initialize registry (called once via get_instance)."""
        self._skills: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._client: Optional["VBFClient"] = None
        self._last_load_time: Optional[float] = None

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Get singleton instance, creating if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None
        cls._lock = None
        cls._sync_lock = None

    async def ensure_lock(self) -> asyncio.Lock:
        """Ensure async lock exists (lazily created)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def initialized(self) -> bool:
        """Whether skills have been loaded."""
        return self._initialized

    @property
    def client(self) -> Optional["VBFClient"]:
        """Get current client."""
        return self._client

    async def load_skills(
        self,
        client: "VBFClient",
        force_refresh: bool = False,
    ) -> int:
        """Load skills from Blender via RPC.

        Uses global cache unless force_refresh is True.

        Args:
            client: VBFClient instance for RPC calls
            force_refresh: Force re-fetch even if already loaded

        Returns:
            Number of skills loaded
        """
        # Check cache first
        if self._initialized and not force_refresh:
            # Verify client connection is still valid
            if self._client is not None:
                return len(self._skills)
            # Client disconnected, need to refresh
            force_refresh = True

        lock = await self.ensure_lock()
        async with lock:
            # Double-check after acquiring lock
            if self._initialized and not force_refresh:
                return len(self._skills)

            self._client = client

            # Fetch all skill names
            skill_names = await client.list_skills()
            if not skill_names:
                raise RuntimeError(
                    "No skills available from Blender. Is the addon loaded?"
                )

            # Fetch skill schemas in batches
            all_schemas: Dict[str, Dict[str, Any]] = {}
            batch_size = 50

            for i in range(0, len(skill_names), batch_size):
                batch = skill_names[i:i + batch_size]
                schemas = await client.describe_skills(batch)
                if schemas:
                    all_schemas.update(schemas)

            self._skills = all_schemas
            self._initialized = True
            import time
            self._last_load_time = time.time()

            return len(self._skills)

    def load_skills_sync(self, client: "VBFClient") -> int:
        """Sync wrapper for load_skills.

        Note: Creates a new event loop if not in async context.
        Prefer async load_skills() when possible.
        """
        import asyncio
        try:
            asyncio.get_running_loop()
            # Already in async context - schedule task
            asyncio.create_task(self.load_skills(client))
            return len(self._skills) if self._initialized else 0
        except RuntimeError:
            # Not in async context
            return asyncio.run(self.load_skills(client))

    async def refresh_skills(self) -> int:
        """Re-fetch skills from Blender. Call after addon update."""
        if self._client is None:
            raise RuntimeError("No client connected. Call load_skills first.")
        self._initialized = False
        return await self.load_skills(self._client, force_refresh=True)

    # --- Public API (uses cached skills) ---

    def validate_skill(self, skill_name: str) -> bool:
        """Check if skill exists in registry."""
        return skill_name in self._skills

    def get_skill_params(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get skill parameter schema.

        Returns args dict with keys: type, required, default
        """
        skill = self._skills.get(skill_name)
        if skill:
            return skill.get("args", {})
        return None

    def get_skill_description(self, skill_name: str) -> Optional[str]:
        """Get skill description."""
        skill = self._skills.get(skill_name)
        return skill.get("description") if skill else None

    def list_skills(self) -> List[str]:
        """List all available skill names."""
        return list(self._skills.keys())

    def get_skill_full(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get complete skill definition."""
        return self._skills.get(skill_name)

    def get_skills_by_category(self, category: str) -> List[str]:
        """Get skills by category (requires category in skill metadata)."""
        return [
            name
            for name, skill in self._skills.items()
            if skill.get("category") == category
        ]

    def __len__(self) -> int:
        """Return number of cached skills."""
        return len(self._skills)

    def __contains__(self, skill_name: str) -> bool:
        """Support 'in' operator for skill validation."""
        return skill_name in self._skills


# Convenience function for quick access
def get_registry() -> SkillRegistry:
    """Get the singleton skill registry instance."""
    return SkillRegistry.get_instance()