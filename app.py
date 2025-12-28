from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import traceback
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# 使用新版 openai 客戶端，金鑰從環境變數 OPENAI_API_KEY 取得
client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


@app.route("/airobot")
def home():
    return "🟢 🟢 Flask AIROBOT Server is Running."


# 共用的 Chat API：給一般 chatbot、AI Report 前兩階段使用
@app.route("/airobot/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json() or {}
        messages = data.get("messages", [])
        model = data.get("model", "gpt-4o-mini")
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
            "tip": "請確認是否已正確設定 OPENAI_API_KEY，並啟用正確的模型"
        }), 500


# 兼容舊版 /api/generate，如果還有其他前端在呼叫這條，就轉給 /airobot/api/generate
@app.route("/api/generate", methods=["POST"])
def generate_compat():
    return generate()


@app.route("/aireport/api/opinion", methods=["POST"])
def generate_aireport_opinion():
    """
    LawAI 法詢：AI 法律意見書（aireport）專用後端。
    接收前端的情境摘要、追問題目與使用者作答摘要，在後端組裝完整提示詞後呼叫 OpenAI。
    這樣可避免前端程式碼直接暴露關鍵提示詞與結構。
    """
    try:
        data = request.get_json() or {}

        chosen_scenario = (data.get("chosenScenario") or "").strip()
        followups = data.get("followups") or []
        answers_meta = data.get("answersMeta") or []

        # 安全處理：確保 followups 與 answers_meta 長度一致時才讀取
        def _get_meta(idx: int):
            if 0 <= idx < len(answers_meta):
                m = answers_meta[idx] or {}
                return {
                    "selectedText": (m.get("selectedText") or "").strip(),
                    "customText": (m.get("customText") or "").strip(),
                }
            return {"selectedText": "", "customText": ""}

        # ===== 這一段是原本藏在前端 JS 裡的法律意見書提示詞，現在改放在後端 =====
        final_prompt = f"""根據以下用戶回答內容，請撰寫一份法律意見書，重點如下：

【案件情境摘要】
使用者已確認本案主要情境如下：
{chosen_scenario}

一、案件事實：
稱用戶為"您"，用語溫暖人性，以兩段文字敘述方式，具體重述事件經過（含人物、過程、爭議、現況及目前案件的法律階段），篇幅至少300字。除使用者所述外，亦可推測可能存在之背景與流程，合理補述未明示之關鍵情節。

二、案件爭執重點釐清：
說明主要爭點、責任歸屬認知差異、爭議關鍵與後續可能影響（不得引用任何法律條文、條號、案號）。

三、關鍵要點分析：
請務必分成兩段撰寫，並用空行分隔。
第一段：說明對您有利的情節。
第二段：說明對您不利的風險，並在段落後半加入整體判斷與後續建議（不得另起第三段）。

四、建議行動方案：
提出三項具體可執行建議，例如聯繫、保存紀錄、委託第三方處理等。

五、證據與紀錄清單：
條列當事人應準備的資料、紀錄與其用途。

請僅針對事實、爭點、建議與證據整理進行撰寫，回覆內容請使用台灣法律用語與台灣民眾習慣表達方式，避免任何法律條文、裁判見解、法理說明或法律意見推論。禁止用**符號，影響美觀。

以下為用戶問答紀錄（每題含：點選選項＋補充）：
------------------------------\n\n"""

        for idx, item in enumerate(followups):
            q = (item.get("q") or "").strip()
            meta = _get_meta(idx)
            picked = meta["selectedText"]
            custom = meta["customText"]

            final_prompt += f"問題{idx + 1}：{q}\n"
            final_prompt += f"點選選項：{picked if picked else '（未點選）'}\n"
            final_prompt += f"補充內容：{custom if custom else '（無）'}\n\n"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.3,
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
            "tip": "請確認是否已正確設定 OPENAI_API_KEY，並啟用正確的模型"
        }), 500


# AI Report「發送給律師」使用的 Email 文字 API
# 前端會送進來 JSON：{ name, phone, line, text }
# 本實作會使用環境變數中的 GMAIL_ACCOUNT / GMAIL_PASSWORD 登入，
# 但收件人固定寄到 tony0975127359@gmail.com。
@app.route("/api/email-text", methods=["POST"])
def email_text():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        phone = (data.get("phone") or "").strip()
        line_id = (data.get("line") or "").strip()
        text = (data.get("text") or "").strip()

        gmail_user = os.environ.get("GMAIL_ACCOUNT")
        gmail_pass = os.environ.get("GMAIL_PASSWORD")
        receiver = "tony0975127359@gmail.com"

        if not gmail_user or not gmail_pass:
            raise RuntimeError("GMAIL_ACCOUNT 或 GMAIL_PASSWORD 未設定")

        subject = "LawAI 法詢 - AI 法律意見書諮詢"
        body = f"""收到一則來自 LawAI 法詢 AI Report 的諮詢：

姓名：{name}
電話：{phone}
LINE ID：{line_id}

以下為 AI 整理出的文字內容：

{text}
"""

        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [receiver], msg.as_string())

        print("=== 已成功寄出 AI Report Email 給律師信箱 ===")
        print("收件人:", receiver)
        print("姓名:", name, "電話:", phone, "LINE:", line_id)
        print("=== 結束 ===")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# PDF 附件版寄信 API：前端以 form-data 上傳 pdf + 基本聯絡資訊
# 同樣固定寄到 tony0975127359@gmail.com。
@app.route("/api/email", methods=["POST"])
def email_with_pdf():
    try:
        gmail_user = os.environ.get("GMAIL_ACCOUNT")
        gmail_pass = os.environ.get("GMAIL_PASSWORD")
        receiver = "tony0975127359@gmail.com"

        if not gmail_user or not gmail_pass:
            raise RuntimeError("GMAIL_ACCOUNT 或 GMAIL_PASSWORD 未設定")

        # 從 form-data 取得欄位與檔案
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        line_id = (request.form.get("line") or "").strip()
        pdf_file = request.files.get("pdf")

        if not pdf_file:
            return jsonify({"error": "缺少 pdf 檔案"}), 400

        pdf_bytes = pdf_file.read()
        filename = secure_filename(pdf_file.filename or "法律意見書.pdf")

        subject = "LawAI 法詢 - AI 法律意見書 PDF 附件"
        body = f"""收到一則來自 LawAI 法詢 AI Report 的 PDF 諮詢：

姓名：{name}
電話：{phone}
LINE ID：{line_id}

附件為使用者下載的法律意見書 PDF 檔案。
"""

        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [receiver], msg.as_string())

        print("=== 已成功寄出 AI Report PDF Email 給律師信箱 ===")
        print("收件人:", receiver)
        print("姓名:", name, "電話:", phone, "LINE:", line_id, "檔名:", filename)
        print("=== 結束 ===")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
