import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vbf.app.client import VBFClient

async def main():
    prompt = Path('assets/prompt_test.md').read_text(encoding='utf-8')
    client = VBFClient(port=28006)
    result = await client.run_task_with_feedback(
        prompt=prompt,
        style='hard_surface_realistic',
        enable_auto_check=True,
        enable_llm_feedback=True,
    )
    print(result)

if __name__ == '__main__':
    asyncio.run(main())
