import os

def merge():
    source_path = "blender_provider/SKILL.md"
    extracted_path = "SKILL_EXTRACTED.md"
    target_path = "blender_provider/SKILL.md"

    if not os.path.exists(source_path) or not os.path.exists(extracted_path):
        print("Source files missing")
        return

    with open(source_path, 'r', encoding='utf-8') as f:
        source_lines = f.readlines()

    with open(extracted_path, 'r', encoding='utf-8') as f:
        extracted_content = f.read()

    # Remove the header from extracted content
    lines = extracted_content.split('\n')
    # Skip the first line "# VBF Skills API Reference\n\n"
    api_content = '\n'.join(lines[2:])

    pre_content = []
    post_content = []
    in_skills_list = False

    for line in source_lines:
        if "## Allowed Skills" in line:
            in_skills_list = True
            continue

        if in_skills_list and "## Runtime Gateway Skills" in line:
            in_skills_list = False
            post_content.append(line)
            continue

        if not in_skills_list:
            pre_content.append(line)

    final_output = "".join(pre_content) + "\n" + api_content + "\n\n" + "".join(post_content)

    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(final_output)
    print("Successfully merged detailed API into blender_provider/SKILL.md")

if __name__ == "__main__":
    merge()
