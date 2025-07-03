from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from email.message import EmailMessage
import smtplib
import openai
import os
import traceback
from dotenv import load_dotenv

# 載入 .env 設定
load_dotenv()

app = Flask(__name__)
CORS(app)

# OpenAI 設定
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_KEY)

# Gmail 設定
GMAIL_ACCOUNT = os.getenv("GMAIL_ACCOUNT")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")

@app.route("/")
def home():
    return "✅ LawAI Flask Server is Running."

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        model = data.get("model", "gpt-3.5-turbo")
        temperature = data.get("temperature", 0.5)

        if not messages or not isinstance(messages, list):
            return jsonify({"error": "Invalid or missing 'messages'"}), 400

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return jsonify({
            "choices": [{
                "message": {
                    "content": response.choices[0].message.content
                }
            }]
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "tip": "請確認 OPENAI_API_KEY 是否正確"
        }), 500

@app.route('/api/email', methods=['POST'])
def send_email():
    if 'pdf' not in request.files:
        return jsonify({"error": "缺少 PDF 檔案"}), 400

    pdf_file = request.files['pdf']
    name = request.form.get('name', '')
    phone = request.form.get('phone', '')
    line_id = request.form.get('line', '')

    pdf_bytes = pdf_file.read()

    msg = EmailMessage()
    msg['Subject'] = f"📨 法律意見書諮詢 - {name}"
    msg['From'] = GMAIL_ACCOUNT
    msg['To'] = 'tony0975127359@gmail.com'
    msg.set_content(
    f"以下為用戶聯絡資訊:\n\n"
    f"姓名: {name}\n"
    f"電話: {phone}\n"
    f"LINE ID: {line_id}\n\n"
    f"請參閱附加的法律意見書 PDF 檔案。"
)

    msg.add_attachment(pdf_bytes, maintype='application', subtype='pdf', filename=secure_filename("法律意見書.pdf"))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_ACCOUNT, GMAIL_PASSWORD)
            smtp.send_message(msg)
        return jsonify({"status": "ok"})
    except Exception as e:
        print("📧 發送錯誤：", e)
        return jsonify({
        "error": "Email 發送失敗",
        "detail": str(e)
    }), 500


@app.route("/api/send_text", methods=["POST"])
def send_text():
    try:
        data = request.get_json()
        name = data.get("name", "")
        phone = data.get("phone", "")
        line = data.get("line", "")
        content = data.get("content", "")

        full_message = f"【姓名】{name}\n【電話】{phone}\n【LINE ID】{line}\n\n【法律意見書內容】\n{content}"

        msg = EmailMessage()
        msg['Subject'] = f"📨 純文字法律諮詢 - {name}"
        msg['From'] = GMAIL_ACCOUNT
        msg['To'] = 'tony0975127359@gmail.com'
        msg.set_content(full_message)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ACCOUNT, GMAIL_PASSWORD)
            smtp.send_message(msg)

        return jsonify({"status": "success"})
    except Exception as e:
        print("❌ 發送錯誤：", e)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)