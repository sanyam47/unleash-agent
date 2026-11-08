path = r"c:\coding\ai-trainer\backend\core\agent_engine.py"
lines = open(path, "r", encoding="utf-8").readlines()

fixed_lines = []
for l in lines:
    if "re.findall(r'(\\w+)\\s*=\\s*" in l:
        fixed_lines.append("                for k, _, v in re.findall(r'(\\\\w+)\\\\s*=\\\\s*([\\\\'\\\"])(.*?)\\\\2', text[search_start:], re.DOTALL):\\n")
    else:
        fixed_lines.append(l)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print("FIXED LINE 140")
