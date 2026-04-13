#!/usr/bin/env python3
"""Analyze mapping between logical categories and physical files."""

import re
import os

def extract_registry_categories():
    """Extract categories from SKILL_REGISTRY."""
    with open('blender_provider/vbf_addon/skills_impl/registry.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    match = re.search(r'SKILL_CATEGORIES\s*=\s*\{(.*?)\n\}', content, re.DOTALL)
    if not match:
        return {}

    cat_content = match.group(1)
    cats = {}

    for m in re.finditer(r'"([^"]+)":\s*\[([^\]]*)\]', cat_content):
        cat_name = m.group(1)
        skills_str = m.group(2)
        skills = re.findall(r'"([^"]+)"', skills_str)
        cats[cat_name] = skills

    return cats

def extract_category_file_skills(filepath):
    """Extract skills from a category markdown file."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    skills = re.findall(r'^## ([a-zA-Z_][a-zA-Z0-9_]*)', content, re.MULTILINE)
    return skills

def main():
    logical_cats = extract_registry_categories()
    cats_dir = 'blender_provider/vbf_addon/skills_docs/categories/'

    print('=' * 70)
    print('LOGICAL vs PHYSICAL CATEGORY MAPPING')
    print('=' * 70)
    print()

    # Map logical to physical
    mapping = {}
    for fname in os.listdir(cats_dir):
        if not fname.endswith('.md') or fname == 'README.md':
            continue

        physical = fname.replace('.md', '')
        skills = set(extract_category_file_skills(os.path.join(cats_dir, fname)))

        # Find matching logical categories
        matches = []
        for logical, logical_skills in logical_cats.items():
            logical_set = set(logical_skills)
            overlap = len(skills & logical_set)
            if overlap > 0:
                matches.append((logical, overlap, len(logical_skills)))

        # Sort by overlap
        matches.sort(key=lambda x: -x[1])

        if matches:
            mapping[physical] = {
                'file': fname,
                'skills': len(skills),
                'logical_matches': matches
            }

    for phys, data in sorted(mapping.items(), key=lambda x: -x[1]['skills']):
        print(f"\n{phys} ({data['skills']} skills)")
        for logical, overlap, total in data['logical_matches'][:3]:
            pct = overlap / total * 100
            print(f"  -> {logical}: {overlap}/{total} ({pct:.0f}%)")

    # Check for unmapped logical categories
    print()
    print('=' * 70)
    print('UNMAPPED LOGICAL CATEGORIES')
    print('=' * 70)

    all_covered = set()
    for phys, data in mapping.items():
        for logical, _, _ in data['logical_matches']:
            all_covered.add(logical)

    unmapped = set(logical_cats.keys()) - all_covered
    for cat in sorted(unmapped):
        print(f"  {cat}: {len(logical_cats[cat])} skills")

if __name__ == '__main__':
    main()
