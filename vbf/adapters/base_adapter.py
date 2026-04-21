# Base Adapter - Multi-model support with RPC-based skill loading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import VBFClient
    from .skill_registry import SkillRegistry


class VBFModelAdapter(ABC):
    """Base adapter for all LLM models.

    Skills are loaded from Blender via RPC calls through SkillRegistry singleton,
    not from local files. This allows the adapter to work as a standalone package
    when the skill documents are not available locally.

    The adapter delegates skill management to SkillRegistry, ensuring:
    - Skills are cached globally (not per-instance)
    - Multiple adapters share the same skill cache
    - Skills are loaded once via RPC, not repeatedly
    """

    def __init__(
        self,
        client: Optional["VBFClient"] = None,
        model_config: Optional[Dict] = None,
    ):
        """Initialize adapter.

        Args:
            client: VBFClient instance for RPC communication with Blender
            model_config: Model-specific configuration from models_config.json
        """
        self._client = client
        self._model_config = model_config or {}
        self._initialized = False
        self.model_name = self.__class__.__name__.replace("Adapter", "").lower()

    @property
    def initialized(self) -> bool:
        """Whether skills have been loaded from Blender."""
        return self._initialized

    @property
    def client(self) -> Optional["VBFClient"]:
        """Get the VBF client instance."""
        return self._client

    @property
    def _registry(self) -> "SkillRegistry":
        """Get the skill registry (lazy import to avoid circular deps)."""
        from .skill_registry import SkillRegistry
        return SkillRegistry.get_instance()

    async def init(self) -> None:
        """Load skills from Blender via RPC using SkillRegistry.

        Must be called after establishing connection to Blender.
        Raises RuntimeError if client not provided.

        Note: Delegated to SkillRegistry for global caching.
        """
        if self._initialized:
            return

        if self._client is None:
            raise RuntimeError(
                "VBFClient required for skill loading. "
                "Use: get_adapter('model', client=client)"
            )

        # Use SkillRegistry for caching
        skill_count = await self._registry.load_skills(self._client)
        self._initialized = True
        return skill_count

    def init_sync(self) -> None:
        """Sync version of init - for use in sync contexts.

        Note: This creates a temporary event loop. Use init() in async code.
        """
        import asyncio
        try:
            asyncio.get_running_loop()
            # Already in async context - schedule task
            asyncio.create_task(self.init())
        except RuntimeError:
            # Not in async context - run in new loop
            asyncio.run(self.init())

    async def refresh_skills(self) -> None:
        """Re-fetch skills from Blender. Call after addon update."""
        self._initialized = False
        await self._registry.refresh_skills()
        self._initialized = True

    # --- Public API (delegates to SkillRegistry for caching) ---

    def validate_skill(self, skill_name: str) -> bool:
        """Check if skill exists in registry."""
        return self._registry.validate_skill(skill_name)

    def get_skill_params(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get skill parameter schema.

        Returns args dict with keys: type, required, default
        """
        return self._registry.get_skill_params(skill_name)

    def get_skill_description(self, skill_name: str) -> Optional[str]:
        """Get skill description."""
        return self._registry.get_skill_description(skill_name)

    def list_available_skills(self) -> List[str]:
        """List all available skill names."""
        return self._registry.list_skills()

    def get_skill_full(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get complete skill definition."""
        return self._registry.get_skill_full(skill_name)

    def get_skills_by_category(self, category: str) -> List[str]:
        """Get skills by category (requires category in skill metadata)."""
        return self._registry.get_skills_by_category(category)

    # --- Abstract methods for model-specific behavior ---

    @abstractmethod
    def build_system_prompt(self, skills_subset: Optional[List[str]] = None) -> str:
        """Build model-specific system prompt.

        Args:
            skills_subset: Optional list of skills to include. If None, include all.
        """
        pass

    @abstractmethod
    def format_messages(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        stream: bool = False,
        skills_subset: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Format messages for specific model API.

        Args:
            user_input: User's natural language input
            context: Optional project context
            stream: Whether streaming response is expected
            skills_subset: Optional subset of skills to expose in prompt
        """
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse model response to VBF plan."""
        pass

    def supports_streaming(self) -> bool:
        """Whether this model supports streaming responses."""
        return self._model_config.get("supports_streaming", False)
