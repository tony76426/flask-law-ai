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
        final_prompt = f"""請根據以下用戶回答內容，撰寫一份「訴訟/處理策略導向」的法律意見書（以台灣法律實務用語表達），務必以可執行的行動路徑為核心。

【案件情境摘要】
使用者已確認本案主要情境如下：
{chosen_scenario}

寫作與輸出規則：
1) 稱呼用戶為「您」，語氣專業但清楚，不需艱澀法理。
2) 不必引用法條條號、裁判案號，也不要整段貼法典。
3) 不要下結論式斷言（例如「一定告得贏」「一定構成」），以「可能」「通常需要」「視證據而定」等表述。
4) 請用清楚標題與條列，讓讀者可直接照著做；避免冗長鋪陳。
5) 禁止使用粗體符號（例如 ** ）。

一、案件事實重述（重點版）
用 150～250 字，按時間順序重述：當事人、關係、關鍵行為、爭議點、目前卡關之處、現況。

二、目前所處程序/談判階段判斷（很重要）
請依目前資訊判斷較接近下列何者並說明理由（擇一或複合）：
- 爭議前/蒐證中
- 已協商/對方不回應或拒絕
- 已寄存證信函/律師函
- 已進入訴訟或調解程序
- 已有判決/調解筆錄，準備強制執行

三、爭點與目標釐清
1) 主要爭點（2～4 點）
2) 您的主要目標（例如：拿回款項/停止侵害/要求履約/離婚與子女安排/賠償等）
3) 對方可能的抗辯方向（1～3 點，避免想像新事實，僅以常見抗辯型態描述）

四、核心：訴訟/處理策略路徑（請給出強而有力的「路徑與順序」）
請提出 2～3 條可行路徑，每條都要包含：
- 適用情境：何時適合走這條
- 優點：為何有力/效率高
- 代價與風險：時間、成本、可能反效果
並在最後明確選出「最推薦的一條」，給出具體理由（以目前資訊為準）。

五、推薦路徑的行動清單（可直接照做）
請用 Step 1～Step 6 條列具體行動，包含：
- 先做什麼、目的是什麼
- 需要準備哪些材料/證據
- 何時應升級（例如：對方逾期不回、拒絕履行、態度惡化）
- 可能的替代選項（例如：先行保全、先調解、先支付命令或先提告等，以「選項」呈現）

六、證據與紀錄清單（對應上面步驟）
請條列「您應該準備的東西」，並在每一項後面註明用途（例如：用來證明金額、用來證明對方承諾、用來證明損害、用來證明通知送達等）。

七、風險提醒與備案
列出 3～5 點風險（例如：證據不足、對方脫產、時效風險、對方反告/反制、程序拖延），並給出各風險的備案作法（對應前述路徑）。

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
