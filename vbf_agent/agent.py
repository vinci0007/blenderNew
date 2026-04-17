import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from vbf.client import VBFClient
from vbf.adapters import get_adapter

class VBFAgent:
    """
    Autonomous Agent wrapper for VBF.

    Provides a high-level autonomous loop that translates goals into VBF tasks,
    manages session memory, and autonomously handles repair loops without
    user intervention (unless requested).
    """

    def __init__(self, goal: str, memory_file: Optional[str] = None):
        self.goal = goal
        self.client = VBFClient()
        self.memory_file = memory_file or os.path.join(os.path.dirname(__file__), "agent_memory.json")
        self.memory: List[Dict[str, Any]] = self._load_memory()
        self._done = False

    def _load_memory(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Agent] Memory save failed: {e}")

    async def _call_llm(self, prompt: str, system_prompt: str = "You are an autonomous 3D modeling agent.") -> str:
        """Uses the existing VBF adapter system to call the LLM."""
        adapter = await self.client._ensure_adapter()
        messages = adapter.format_messages(prompt)
        # Insert system prompt at the beginning if needed
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = system_prompt + "\n" + messages[0]["content"]
        else:
            messages.insert(0, {"role": "system", "content": system_prompt})

        response = await self.client._adapter_call(messages)
        return response if isinstance(response, str) else response.get("content", str(response))

    async def run(self, auto_approve: bool = True):
        """
        Main Agent Loop:
        Goal -> Sub-tasks -> Execution -> Evaluation -> Repair -> Completion
        """
        print(f"[Agent] Starting autonomous task: {self.goal}")
        await self.client.ensure_connected()

        # 1. High-level decomposition
        decomposition_prompt = (
            f"Goal: {self.goal}\n"
            "Break this goal down into a sequence of high-level VBF tasks. "
            "Each task should be a standalone prompt that the VBF system can execute. "
            "Return only a JSON list of strings: ['task1', 'task2', ...]"
        )
        tasks_json = await self._call_llm(decomposition_prompt, "You are a project manager for 3D modeling.")
        try:
            # Simple JSON extraction
            import re
            match = re.search(r'\[.*\]', tasks_json, re.DOTALL)
            tasks = json.loads(match.group(0)) if match else [self.goal]
        except Exception:
            tasks = [self.goal]

        print(f"[Agent] Decomposed into {len(tasks)} sub-tasks.")

        for i, task_prompt in enumerate(tasks):
            if self._done: break

            print(f"[Agent] Step {i+1}/{len(tasks)}: {task_prompt}")

            # 2. Execute via VBFClient
            try:
                # We use run_task which includes the 4-layer recovery system internally
                result = await self.client.run_task(task_prompt)

                # 3. Autonomous Evaluation
                eval_prompt = f"Task: {task_prompt}\nResult: {result}\nDoes this result satisfy the task? Reply with 'YES' or 'NO' and a brief reason."
                eval_resp = await self._call_llm(eval_prompt)

                if "NO" in eval_resp.upper():
                    print(f"[Agent] Evaluation failed: {eval_resp}. Attempting autonomous repair...")
                    # Autonomous Repair Loop
                    repair_prompt = f"The task '{task_prompt}' failed with result: {result}. {eval_resp}. Please provide a corrected prompt to fix this."
                    fixed_prompt = await self._call_llm(repair_prompt)
                    await self.client.run_task(fixed_prompt)

                self.memory.append({
                    "timestamp": datetime.now().isoformat(),
                    "task": task_prompt,
                    "result": result,
                    "eval": eval_resp
                })
                self._save_memory()

            except Exception as e:
                print(f"[Agent] Critical error during step {i+1}: {e}")
                # Attempt to resume from the last checkpoint
                try:
                    state_path = self.client._default_save_path
                    await self.client.run_task(task_prompt, resume_state_path=state_path)
                except Exception as e2:
                    print(f"[Agent] Resume also failed: {e2}")
                    break

        print("[Agent] Task completed.")
        self._done = True

async def main():
    # Example usage
    agent = VBFAgent(goal="Create a futuristic cyberpunk drone with neon lights and a camera lens")
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
