path = r"c:\coding\ai-trainer\backend\core\agent_engine.py"
lines = open(path, "r", encoding="utf-8").readlines()

new_lines = []
for l in lines:
    if "re.findall" in l and "search_start" in l:
        new_lines.append("                for match in re.finditer(r'(\\w+)\\s*=\\s*[\"\\'](.*?)[\"\\']', text[search_start:], re.DOTALL):\n")
        new_lines.append("                    action_args[match.group(1)] = match.group(2)\n")
    elif "action_args[k] = v" in l:
        continue
    else:
        new_lines.append(l)

open(path, "w", encoding="utf-8").writelines(new_lines)
print("LINE REPLACED CLEANLY")
