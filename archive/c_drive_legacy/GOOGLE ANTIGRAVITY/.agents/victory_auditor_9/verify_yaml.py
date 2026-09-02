import re
import yaml

spec_path = r"G:\My Drive\GOOGLE ANTIGRAVITY\apps\V1_OMNICHANNEL_ARCHITECTURE_SPEC.md"

with open(spec_path, "r", encoding="utf-8") as f:
    content = f.read()

# YAML blocks
yaml_blocks = re.findall(r"```yaml(.*?)```", content, re.DOTALL)
print(f"Found {len(yaml_blocks)} YAML code blocks.")
for i, block in enumerate(yaml_blocks):
    clean_yaml = "\n".join([line for line in block.splitlines() if not line.strip().startswith("# filepath:")])
    try:
        parsed = yaml.safe_load(clean_yaml)
        print(f"[PASS] YAML code block {i+1} parsed successfully. Title: {parsed.get('info', {}).get('title')}")
    except Exception as e:
        print(f"[FAIL] YAML code block {i+1} parse error: {e}")
