path = r"c:\coding\ai-trainer\backend\core\agent_engine.py"
content = open(path, "r", encoding="utf-8").read()

bad_str = 'for k, _, v in re.findall(r\'(\\\\w+)\\\\s*=\\\\s*([\\\\\'\\"])(.*?)\\\\2\', text[search_start:], re.DOTALL):\\n'
good_str = 'for k, _, v in re.findall(r"(\\w+)\\s*=\\s*([\'\"])(.*?)\\2", text[search_start:], re.DOTALL):\n'

if bad_str in content:
    content = content.replace(bad_str, good_str, 1)
    open(path, "w", encoding="utf-8").write(content)
    print("REPLACED BAD STR")
else:
    # Let's inspect line 139-142
    lines = content.splitlines(True)
    for i, l in enumerate(lines):
        if "action_args = {}" in l:
            lines[i+1] = '                for k, _, v in re.findall(r"(\\w+)\\s*=\\s*([\'\"])(.*?)\\2", text[search_start:], re.DOTALL):\n'
            break
    open(path, "w", encoding="utf-8").writelines(lines)
    print("REPLACED BY LINE INDEX")
