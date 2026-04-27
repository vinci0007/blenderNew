import ast
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_IMPL = ROOT / "blender_provider" / "vbf_addon" / "skills_impl"
API_REF = ROOT / "reference" / "blender_python_reference_5_1"


def _call_name(node: ast.AST) -> str | None:
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def _extract_bpy_ops_calls() -> list[tuple[str, Path, int, list[str]]]:
    calls = []
    for path in sorted(SKILLS_IMPL.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if not name or not name.startswith("bpy.ops."):
                continue
            keywords = [kw.arg for kw in node.keywords if kw.arg is not None]
            calls.append((name, path, node.lineno, keywords))
    return calls


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _parse_operator_docs() -> dict[str, set[str]]:
    docs = {}
    for path in sorted(API_REF.glob("bpy.ops.*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(
            r'<dt class="sig sig-object py" id="(bpy\.ops\.[^"]+)">(.*?)</dt>',
            text,
            flags=re.S,
        ):
            op_name = match.group(1)
            signature = _strip_tags(match.group(2))
            params = set(
                re.findall(
                    r"([A-Za-z_][A-Za-z0-9_]*)\s*=",
                    signature,
                )
            )
            docs[op_name] = params
    return docs


def test_all_skill_bpy_ops_calls_match_blender_51_docs():
    calls = _extract_bpy_ops_calls()
    docs = _parse_operator_docs()
    assert docs, "Blender 5.1 API docs were not parsed"

    missing_ops = []
    unknown_keywords = []
    for op_name, path, lineno, keywords in calls:
        if op_name not in docs:
            missing_ops.append(f"{path.relative_to(ROOT)}:{lineno} {op_name}")
            continue
        valid_params = docs[op_name]
        for keyword in keywords:
            if keyword not in valid_params:
                unknown_keywords.append(
                    f"{path.relative_to(ROOT)}:{lineno} {op_name} unknown keyword {keyword}"
                )

    assert not missing_ops, "Missing Blender 5.1 operators:\n" + "\n".join(missing_ops)
    assert not unknown_keywords, "Unknown Blender 5.1 operator keywords:\n" + "\n".join(unknown_keywords)
