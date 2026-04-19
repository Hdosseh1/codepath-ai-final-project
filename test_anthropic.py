import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

print("Key exists:", api_key is not None)
print("Key prefix:", api_key[:10] if api_key else "None")

client = Anthropic(api_key=api_key)

try:
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=20,
        messages=[{"role": "user", "content": "Say hello"}]
    )
    print("SUCCESS:", response)
except Exception as e:
    print("ERROR:", e)