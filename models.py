import google.generativeai as genai

# Load your API key
api_key = open("gemini_key.txt").read().strip()

# Configure Gemini SDK
genai.configure(api_key=api_key)

# List all available models
models = genai.list_models()
print("These are the models you have access to:")
for m in models:
    print(m.name)