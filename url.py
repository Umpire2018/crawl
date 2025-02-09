import re

pattern = r".*Olympics.*"
test_strings = [
    "https://en.wikipedia.org/wiki/2024_Summer_Olympics",
]

for text in test_strings:
    match = re.search(pattern, text)
    print(f"✅ Found in: {text}") if match else print(f"❌ Not found in: {text}")
