import json

with open("cov.json") as f:
    d = json.load(f)

files = {k: v["summary"] for k, v in d["files"].items()}
total = d["totals"]

print(f"\nTOTAL: {total['percent_covered']:.1f}%  ({total['covered_lines']}/{total['num_statements']} lines)\n")
print(f"{'Coverage':>8}  {'File'}")
print("-" * 80)
for k, v in sorted(files.items(), key=lambda x: x[1]["percent_covered"]):
    print(f"{v['percent_covered']:7.1f}%  {k}")
