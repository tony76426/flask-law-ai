from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import logging
import re

app = Flask(__name__)
CORS(app)

# 日誌設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化 OpenAI 客戶端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def clean_ai_response(text):
    """清理 AI 回應中的非 JSON 內容"""
    try:
        # 移除 Markdown 程式碼塊
        cleaned = re.sub(r'```json|```', '', text)
        # 提取第一個有效的 JSON 對象或陣列
        json_match = re.search(r'(\[.*\]|\{.*\})', cleaned, re.DOTALL)
        return json_match.group(1) if json_match else cleaned
    except Exception as e:
        logger.error(f"清理回應時出錯: {str(e)}")
        return text

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

        # 強化提示詞規範
        if len(data["messages"]) > 0:
            data["messages"][0]["content"] = f"{data['messages'][0]['content']}\n\n請嚴格遵守以下回應規則：\n1. 只返回純JSON格式\n2. 不要包含任何Markdown標記\n3. 不要包含解釋文字"

        # 新版 API 呼叫
        response = client.chat.completions.create(
            model=MODEL_MAPPING[model],
            messages=data["messages"],
            temperature=temperature,
            response_format={"type": "json_object"}  # 強制 JSON 格式
        )
        
        # 清理回應內容
        result = clean_ai_response(response.choices[0].message.content)
        return jsonify({"result": result})

    except Exception as e:
        logger.error(f"API 錯誤: {str(e)}", exc_info=True)
        return jsonify({"error": f"內部錯誤: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)