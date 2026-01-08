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

稱用戶為「您」，用語溫暖且中性，以兩段文字敘述方式，完整重述使用者所描述之事件經過，內容須包含人物關係、事件起點、關鍵過程、主要爭議、目前狀態，以及目前所處之爭議或法律程序階段（以概括描述為限），篇幅至少 150 字。

本段以整理與重述既有事實為限，不得評價對錯或責任歸屬。
若需補充未明示之背景或流程，僅能以「可能」「通常情況下」「一般會發生」等推測性語句說明，並明確區分於使用者明確陳述之事實，不得將推測內容寫成既定事實。

二、案件爭執重點釐清：

僅就目前事件中雙方對事實、責任、金錢或權利流向之認知差異進行說明，指出爭議形成的原因、核心分歧所在，以及導致目前僵局的關鍵卡點。

本段不得判斷誰對誰錯，僅能描述雙方立場差異與爭議狀態；
可概括提及與爭議相關之權利義務概念或金錢往來情形，不得引用任何訴訟案號或裁判見解，並避免作成結論性判斷，以導引出目前爭議停滯或難以推進之原因。

三、關鍵要點分析：

請務必分成兩段撰寫，並以空行分隔。

第一段：
說明目前事實中對您相對有利、可被主張或可被強調的情節，著重於哪些已知事實有助於支撐您的立場，而非作成責任判斷。

第二段：
說明目前可能存在的不利因素或潛在風險，例如事實不明確、證據不足或容易被對方質疑之處，並於本段後半一併提出整體風險觀察與可行的補強方向或因應建議，不得另起第三段。

四、建議行動方案：

請提出三項具體且可實際執行的行動建議，建議依時間或處理順序排列，例如：立即可進行之處理、對方不配合時的應對方向，以及進一步進入法律程序前可先完成之準備事項，避免抽象或概念性描述。

五、證據與紀錄清單：

請條列目前建議準備或整理之資料與紀錄，並於每一項後簡要說明其用途或可能有助釐清之事項，避免使用「一定要有」等絕對語氣。

撰寫總則：

請僅就事實整理、爭點釐清、行動建議與證據準備進行撰寫，全文使用台灣法律實務用語與台灣民眾習慣之表達方式，不得引用任何裁判見解或判決內容，並禁止使用任何符號或強調格式，以維持正式書面文件之整體美觀與一致性。

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
# 本實作會使用環境變數中的 GMAIL_ACCOUNT / GMAIL_PASSWORD，透過 Gmail SMTP 寄信。
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
        msg["To"] = gmail_user
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [gmail_user], msg.as_string())

        print("=== 已成功寄出 AI Report Email 給律師信箱 ===")
        print("收件人:", gmail_user)
        print("姓名:", name, "電話:", phone, "LINE:", line_id)
        print("=== 結束 ===")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# PDF 附件版寄信 API：前端以 form-data 上傳 pdf + 基本聯絡資訊
@app.route("/api/email", methods=["POST"])
def email_with_pdf():
    try:
        gmail_user = os.environ.get("GMAIL_ACCOUNT")
        gmail_pass = os.environ.get("GMAIL_PASSWORD")
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
        msg["To"] = gmail_user
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [gmail_user], msg.as_string())

        print("=== 已成功寄出 AI Report PDF Email 給律師信箱 ===")
        print("收件人:", gmail_user)
        print("姓名:", name, "電話:", phone, "LINE:", line_id, "檔名:", filename)
        print("=== 結束 ===")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
