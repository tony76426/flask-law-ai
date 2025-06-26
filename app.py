
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import traceback

app = Flask(__name__)
CORS(app)

# 從環境變數取得 OpenAI 金鑰（請至 Render 設定 OPENAI_API_KEY）
openai.api_key = os.environ.get("OPENAI_API_KEY")

@app.route("/")
def home():
    return "🟢 Flask Law AI Server is Running."

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        model = data.get("model", "gpt-3.5-turbo")
        temperature = data.get("temperature", 0.5)

        if not messages or not isinstance(messages, list):
            return jsonify({"error": "Invalid or missing 'messages'"}), 400

        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        print("🔥 Exception in /api/generate:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
