from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI  # 新版導入方式
import os
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 日誌設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        logger.info(f"收到請求: {data}")

        # 驗證必要欄位
        if not data or "messages" not in data:
            return jsonify({"error": "缺少 messages 參數"}), 400

        # 模型映射表
        MODEL_MAPPING = {
            "gpt-4o-mini": "gpt-4-1106-preview",
            "gpt-3.5-turbo": "gpt-3.5-turbo"
        }

        model = data.get("model", "gpt-3.5-turbo")
        if model not in MODEL_MAPPING:
            return jsonify({"error": f"不支援的模型，請使用: {list(MODEL_MAPPING.keys())}"}), 400

        # 溫度參數安全處理
        temperature = min(max(float(data.get("temperature", 0.5)), 0), 2)

        # 新版 API 呼叫方式
        response = client.chat.completions.create(
            model=MODEL_MAPPING[model],
            messages=data["messages"],
            temperature=temperature,
        )
        
        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        logger.error(f"API 錯誤: {str(e)}", exc_info=True)
        return jsonify({"error": f"內部錯誤: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)