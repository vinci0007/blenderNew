#!/usr/bin/env python3
"""Extract and verify all skills from SKILL.md."""
import re
from pathlib import Path

SKILL_MD_PATH = Path(r'E:\0001_Work_New\013_Work_Git\0003_AI\00001_design\blenderNew\blender_provider\vbf_addon\skills_docs\SKILL.md')
REFERENCE_DIR = Path(r'E:\0001_Work_New\013_Work_Git\0003_AI\00001_design\blenderNew\reference\blender_python_reference_5_1')

def extract_skills_from_skill_md():
    """Extract all skill definitions from SKILL.md."""
    with open(SKILL_MD_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    skills = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Match skill header: ## skill_name (with underscore, not section header)
        if line.startswith('## '):
            name = line[3:].strip()
            # Skip section headers (no underscore)
            if '_' not in name:
                i += 1
                continue

            # Skip workflow stage names (like 18_Stage, etc)
            if name.replace('_', '').replace('-', '').isalpha() == False:
                i += 1
                continue

            # Find section end
            j = i + 1
            section_lines = []
            while j < len(lines):
                if lines[j].strip().startswith('## ') and j > i + 1:
                    break
                section_lines.append(lines[j])
                j += 1

            section = '\n'.join(section_lines)

            # Extract description
            desc = ""
            desc_match = re.search(r'\*\*Description\*\*:?\s*([^\n]+)', section)
            if desc_match:
                desc = desc_match.group(1).strip()

            # Parse parameters
            has_params = '| Parameter |' in section
            params = {}

            if has_params:
                table_start = section.find('| Parameter |')
                if table_start >= 0:
                    table_section = section[table_start:]
                    table_end = table_section.find('\n---')
                    if table_end >= 0:
                        table_section = table_section[:table_end]

                    for line in table_section.split('\n'):
                        line = line.strip()
                        # Match | name | type | required | default |
                        m = re.match(r'^\|\s*([^-][^|]*?)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*([^|]*)\s*\|', line)
                        if m:
                            p_name = m.group(1).strip()
                            if p_name and p_name not in ['Parameter', '---', '-']:
                                params[p_name] = {
                                    'type': m.group(2),
                                    'required': m.group(3).lower() == 'yes',
                                    'default': m.group(4).strip()
                                }

            skills.append({
                'name': name,
                'description': desc,
                'has_params': has_params,
                'params': params
            })

        i += 1

    return skills

def check_api_reference(skill_name, reference_dir):
    """Check if skill maps to bpy.ops API."""
    parts = skill_name.split('_', 1)
    if len(parts) < 2:
        return None

    prefix = parts[0]
    func_name = parts[1]

    # Map prefixes to API files
    prefix_map = {
        'add': 'bpy.ops.mesh.html',
        'apply': 'bpy.ops.object.html',
        'armature': 'bpy.ops.armature.html',
        'asset': 'bpy.ops.asset.html',
        'boolean': 'bpy.ops.mesh.html',
        'bake': 'bpy.ops.object.html',
        'camera': 'bpy.ops.object.html',
        'clear': 'bpy.ops.object.html',
        'clone': 'bpy.ops.image.html',
        'cloth': 'bpy.ops.object.html',
        'compositor': 'bpy.ops.node.html',
        'constraint': 'bpy.ops.constraint.html',
        'create': 'bpy.ops.mesh.html',
        'delete': 'bpy.ops.object.html',
        'driver': 'bpy.ops.anim.html',
        'edge': 'bpy.ops.mesh.html',
        'extrude': 'bpy.ops.mesh.html',
        'face': 'bpy.ops.mesh.html',
        'geometry': 'bpy.ops.node.html',
        'gpencil': 'bpy.ops.gpencil.html',
        'ik': 'bpy.ops.armature.html',
        'image': 'bpy.ops.image.html',
        'insert': 'bpy.ops.graph.html',
        'join': 'bpy.ops.object.html',
        'light': 'bpy.ops.object.html',
        'link': 'bpy.ops.object.html',
        'loop': 'bpy.ops.mesh.html',
        'make': 'bpy.ops.file.html',
        'mark': 'bpy.ops.uv.html',
        'material': 'bpy.ops.material.html',
        'mesh': 'bpy.ops.mesh.html',
        'mirror': 'bpy.ops.mesh.html',
        'modifier': 'bpy.ops.object.html',
        'move': 'bpy.ops.transform.html',
        'node': 'bpy.ops.node.html',
        'normal': 'bpy.ops.mesh.html',
        'object': 'bpy.ops.object.html',
        'ops': 'bpy.ops.html',
        'parent': 'bpy.ops.object.html',
        'particle': 'bpy.ops.particle.html',
        'py': 'bpy.html',
        'raycast': 'bpy.ops.object.html',
        'remove': 'bpy.ops.object.html',
        'rename': 'bpy.ops.object.html',
        'render': 'bpy.ops.render.html',
        'rigidbody': 'bpy.ops.rigidbody.html',
        'scale': 'bpy.ops.transform.html',
        'scene': 'bpy.ops.scene.html',
        'sculpt': 'bpy.ops.sculpt.html',
        'select': 'bpy.ops.object.html',
        'sequence': 'bpy.ops.sequencer.html',
        'sequencer': 'bpy.ops.sequencer.html',
        'set': 'bpy.ops.object.html',
        'shader': 'bpy.ops.node.html',
        'shape': 'bpy.ops.object.html',
        'smooth': 'bpy.ops.mesh.html',
        'snap': 'bpy.ops.view3d.html',
        'subdivision': 'bpy.ops.object.html',
        'texture': 'bpy.ops.texture.html',
        'track': 'bpy.ops.object.html',
        'tracking': 'bpy.ops.clip.html',
        'transform': 'bpy.ops.transform.html',
        'triangulate': 'bpy.ops.mesh.html',
        'unwrap': 'bpy.ops.uv.html',
        'uv': 'bpy.ops.uv.html',
        'vertex': 'bpy.ops.mesh.html',
        'view3d': 'bpy.ops.view3d.html',
    }

    api_file = prefix_map.get(prefix)
    if api_file:
        full_path = reference_dir / api_file
        if full_path.exists():
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Check if function exists
            search_patterns = [func_name, func_name.replace('_', '.')]
            for pattern in search_patterns:
                if f'{pattern}(' in content:
                    return api_file

    return None

# Extract skills
print("=" * 80)
print("EXTRACTING SKILLS FROM SKILL.MD")
print("=" * 80)

skills = extract_skills_from_skill_md()
print(f"\nTotal skills found: {len(skills)}")

# Group by prefix
prefixes = {}
for s in skills:
    parts = s['name'].split('_', 1)
    prefix = parts[0] if len(parts) > 1 else s['name']
    if prefix not in prefixes:
        prefixes[prefix] = []
    prefixes[prefix].append(s)

print(f"\nSkills by prefix:")
for prefix, skill_list in sorted(prefixes.items(), key=lambda x: -len(x[1]))[:15]:
    print(f"  {prefix}: {len(skill_list)}")

# Check for missing parameter tables
missing_params = [s for s in skills if not s['has_params']]
print(f"\nSkills without parameter tables: {len(missing_params)}")
for s in missing_params[:10]:
    print(f"  - {s['name']}: {s['description'][:50] if s['description'] else 'No description'}")

# Sample API verification
print(f"\n{'='*80}")
print("SAMPLE API REFERENCE CHECK")
print(f"{'='*80}")

sample_skills = [
    'add_modifier_bevel',
    'add_modifier_subdivision',
    'apply_modifier',
    'view3d_view_all',
    'view3d_snap_cursor_to_center',
    'mark_seam',
    'unwrap_mesh',
    'extrude_faces',
    'loop_cut',
    'bridge_edge_loops',
    'create_primitive',
    'object_select_all',
    'boolean_tool',
    'join_objects',
    'delete_object',
]

for skill_name in sample_skills:
    for s in skills:
        if s['name'] == skill_name:
            api_file = check_api_reference(skill_name, REFERENCE_DIR)
            if api_file:
                print(f"[FOUND] {skill_name} -> {api_file}")
            else:
                print(f"[---] {skill_name} (no direct API match)")
            print(f"       Desc: {s['description'][:60] if s['description'] else 'N/A'}")
            print(f"       Params: {len(s['params'])}")
            break
    else:
        print(f"[MISSING] {skill_name} - not in SKILL.md")

print(f"\n{'='*80}")