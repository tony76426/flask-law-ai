from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os

app = Flask(__name__)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/")
def home():
    return "<h3>🟢 Flask Law AI Server is Running.</h3>"

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({'error': 'Missing question'}), 400

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "你是一位台灣的專業律師，擅長民事與刑事訴訟。"},
                {"role": "user", "content": data['question']}
            ],
            temperature=0.7
        )
        result = response.choices[0].message.content
        return jsonify({'result': [{'content': result}]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run()
