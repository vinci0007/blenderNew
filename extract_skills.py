import ast
import os
import glob
from typing import Dict, Any, List

def parse_skill_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse a python file and extract skill definitions using AST."""
    with open(file_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())

    skills = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Extract docstring
            doc = ast.get_docstring(node) or "No description available."

            # Extract parameters and defaults
            params = []
            # Combine args and defaults
            # node.args.args contains the parameter names
            # node.args.defaults contains the default values for the last N arguments
            all_args = node.args.args
            defaults = node.args.defaults

            # offset to match defaults to the correct arguments
            default_offset = len(all_args) - len(defaults)

            for i, arg in enumerate(all_args):
                arg_name = arg.arg
                # Type annotation
                arg_type = "any"
                if arg.annotation:
                    # Basic attempt to convert AST node to string
                    arg_type = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else "any"

                # Default value
                has_default = i >= default_offset
                default_val = "-"
                if has_default:
                    try:
                        default_val = ast.unparse(defaults[i - default_offset]) if hasattr(ast, 'unparse') else "default"
                    except:
                        default_val = "default"

                params.append({
                    "name": arg_name,
                    "type": arg_type,
                    "required": "No" if has_default else "Yes",
                    "default": default_val
                })

            skills.append({
                "name": node.name,
                "description": doc.split('\n')[0],
                "params": params
            })
    return skills

def main():
    # Search for all .py files in skills_impl directory
    skill_files = glob.glob("blender_provider/vbf_addon/skills_impl/*.py", recursive=True)
    all_skills = {}

    for file in skill_files:
        # Skip __init__.py
        if os.path.basename(file) == "__init__.py":
            continue

        try:
            file_skills = parse_skill_file(file)
            for s in file_skills:
                # We only care about functions that are likely skills (usually based on naming or just all functions in this dir)
                # To be safe and match registry.py, we'll collect all, then we can filter if needed.
                all_skills[s['name']] = s
        except Exception as e:
            print(f"Error parsing {file}: {e}")

    # Sort skills alphabetically
    sorted_names = sorted(all_skills.keys())

    output = "# VBF Skills API Reference\n\n"
    for name in sorted_names:
        skill = all_skills[name]
        output += f"## {name}\n"
        output += f"**Description**: {skill['description']}\n\n"

        if skill['params']:
            output += "| Parameter | Type | Required | Default |\n"
            output += "|---|---|---|---|\n"
            for p in skill['params']:
                output += f"| {p['name']} | {p['type']} | {p['required']} | {p['default']} |\n"
        else:
            output += "*No parameters*\n"

        output += "\n---\n\n"

    with open("SKILL_EXTRACTED.md", "w", encoding="utf-8") as f:
        f.write(output)
    print(f"Successfully extracted {len(all_skills)} skills to SKILL_EXTRACTED.md")

if __name__ == "__main__":
    main()
