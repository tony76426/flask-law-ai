
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def index():
    return "AI 法律諮詢 API 已啟動"

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({'error': 'Missing question'}), 400

    question = data['question']
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": question}],
            temperature=0.5
        )
        return jsonify({
            "result": response.choices[0].message.content.strip()
        })
    except Exception as e:
        print(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
