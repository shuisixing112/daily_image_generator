import json

with open("test.json", "r") as f:
    data = json.load(f)

print("✅ JSON 正確，可以被載入")
