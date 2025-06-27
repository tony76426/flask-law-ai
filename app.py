from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        question = data.get('question', '')

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "你是一位法律專家，擅長協助當事人釐清事實與判斷訴訟策略。請根據使用者輸入的法律問題，協助提出後續建議。"},
                {"role": "user", "content": question}
            ]
        )
        reply = response.choices[0].message.content
        return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def home():
    return "🟢 Flask Law AI Server is Running."

if __name__ == '__main__':
    app.run(debug=True)
