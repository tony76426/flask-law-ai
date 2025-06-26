from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os

app = Flask(__name__)
CORS(app)

# 請將下列金鑰改為你自己的 OpenAI API Key
openai.api_key = os.environ.get("OPENAI_API_KEY", "sk-...")

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        model = data.get("model", "gpt-3.5-turbo")
        temperature = data.get("temperature", 0.5)

        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "🟢 Flask Law AI Server is Running."


if __name__ == "__main__":
    app.run(debug=True)