#!/usr/bin/env python3
"""Generate enhanced SKILL.md with detailed parameter descriptions"""

import inspect
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock bpy
class MockBpy:
    pass
sys.modules['bpy'] = MockBpy()

from blender_provider.vbf_addon.skills_impl.registry import SKILL_REGISTRY, SKILL_CATEGORIES

def extract_skill_signature(fn):
    """Extract function signature and parameter details"""
    sig = inspect.signature(fn)
    params = []

    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue

        param_info = {
            'name': param_name,
            'type': str(param.annotation) if param.annotation != inspect.Parameter.empty else 'any',
            'required': param.default == inspect.Parameter.empty,
            'default': repr(param.default) if param.default != inspect.Parameter.empty else None
        }
        params.append(param_info)

    return params

def format_type(type_str):
    """Simplify type strings"""
    type_str = str(type_str)
    replacements = {
        'List[float]': 'float[]',
        'List[str]': 'string[]',
        'Dict[str, Any]': 'dict',
        'Optional[str]': 'string | None',
        'Union[None, str]': 'string | None',
    }
    for old, new in replacements.items():
        type_str = type_str.replace(old, new)
    return type_str

def generate_skill_doc(skill_name, skill_fn):
    """Generate detailed documentation for one skill"""
    sig = inspect.signature(skill_fn)
    doc = inspect.getdoc(skill_fn) or ""
    first_line = doc.split('\n')[0].strip() if doc else f"Execute {skill_name}"

    params = extract_skill_signature(skill_fn)

    # Generate parameter markdown
    if params:
        param_md = "### Parameters\n\n"
        for p in params:
            type_str = format_type(p['type'])
            req_str = "**Required**" if p['required'] else "*Optional*"
            default_str = f", default={p['default']}" if p['default'] and p['default'] != 'None' else ""

            # Format the parameter line
            if p['name'] == 'location' or p['name'] == 'rotation_euler' or p['name'] == 'scale':
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): List of 3 values [x, y, z]\n"
            elif p['name'].endswith('_location') or p['name'].endswith('_rotation') or p['name'].endswith('_scale'):
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): List of 3 values\n"
            elif p['name'].endswith('_uv'):
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): UV coordinate pair [u, v]\n"
            elif p['name'] == 'primitive_type' or p['name'] == 'tool_name' or p['name'] == 'operation':
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): {p['default'] if p['default'] and p['default'] != 'None' else 'See allowed values'}\n"
            elif p['name'].endswith('_name') or p['name'].endswith('_path') or p['name'].endswith('_id'):
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): String identifier\n"
            elif p['name'] == 'kwargs' or p['name'] == 'args':
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}): Additional arguments\n"
            else:
                param_md += f"- **`{p['name']}`** ({type_str}, {req_str}){default_str}\n"

        # Add returns section
        param_md += "\n### Returns\n\n"
        param_md += f"- `{skill_name}` returns: `{skill_name}_result` (dict with `ok: bool` and `data: {...}`)\n"
    else:
        param_md = "### Parameters\n\n- No parameters (uses selected objects/scenes)\n\n### Returns\n\n- `{skill_name}` returns: `{skill_name}_result` (dict with `ok: bool` and `data: {...}`)\n"

    return f"**`{skill_name}`**: {first_line}\n{param_md}"

def main():
    print(f"Generating enhanced SKILL.md with parameter descriptions...")
    print(f"Skills in registry: {len(SKILL_REGISTRY)}")
    print(f"Categories: {len(SKILL_CATEGORIES)}")

    # Read template
    with open('blender_provider/SKILL.md', 'r', encoding='utf-8') as f:
        template = f.read()

    # Find the "Allowed Skills" section
    allowed_section_start = template.find("## Allowed Skills (290+)")

    if allowed_section_start == -1:
        print("ERROR: Could not find Allowed Skills section")
        return

    # Generate new skills section
    new_skills_section = "\n## Allowed Skills (290+)\n\n"
    new_skills_section += "Complete list of registered skills with parameter schemas.\n\n"

    for category_name, skill_names in SKILL_CATEGORIES.items():
        skill_count = len(skill_names)
        new_skills_section += f"### {category_name} ({skill_count} skills)\n\n"

        for skill_name in sorted(skill_names):
            if skill_name not in SKILL_REGISTRY:
                print(f"Warning: {skill_name} in SKILL_CATEGORIES but not in SKILL_REGISTRY")
                continue

            skill_fn = SKILL_REGISTRY[skill_name]
            skill_doc = generate_skill_doc(skill_name, skill_fn)
            new_skills_section += skill_doc + "\n"

        new_skills_section += "\n"

    # Replace the old section
    allowed_section_end = template.find("\n---\n", allowed_section_start)
    if allowed_section_end == -1:
        allowed_section_end = template.find("\n## Runtime Gateway Skills", allowed_section_start)

    enhanced_template = template[:allowed_section_start] + new_skills_section + template[allowed_section_end:]

    # Write back
    output_path = Path(__file__).parent / 'blender_provider' / 'SKILL.md'
    output_path.write_text(enhanced_template, encoding='utf-8')

    print(f"✓ Enhanced SKILL.md saved with parameter descriptions")
    print(f"  - Skills documented: {len(SKILL_REGISTRY)}")
    print(f"  - Categories: {len(SKILL_CATEGORIES)}")
    print(f"  - Total lines: {len(enhanced_template.splitlines())}")

if __name__ == '__main__':
    main()
