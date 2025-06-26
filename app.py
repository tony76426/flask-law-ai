from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 設置日誌記錄
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變量讀取 API 金鑰
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY 環境變量未設置！")

# 支援的模型列表
SUPPORTED_MODELS = {
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4o-mini": "gpt-4-1106-preview"  # 實際使用 GPT-4 最新模型
}

@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        
        # 驗證必要欄位
        if not data or "messages" not in data:
            return jsonify({"error": "缺少 messages 參數"}), 400
        
        # 驗證 messages 格式
        messages = data.get("messages", [])
        if not isinstance(messages, list) or not all(
            isinstance(msg, dict) and "role" in msg and "content" in msg 
            for msg in messages
        ):
            return jsonify({"error": "無效的 messages 格式"}), 400
        
        # 驗證模型和溫度參數
        model = data.get("model", "gpt-3.5-turbo")
        if model not in SUPPORTED_MODELS:
            return jsonify({"error": f"不支援的模型，請使用: {', '.join(SUPPORTED_MODELS.keys())}"}), 400
        
        temperature = min(max(float(data.get("temperature", 0.5)), 0), 2)  # 限制範圍 0~2
        
        logger.info(f"請求參數 - model: {model}, temperature: {temperature}")
        
        # 調用 OpenAI API (映射模型名稱)
        actual_model = SUPPORTED_MODELS[model]
        response = openai.ChatCompletion.create(
            model=actual_model,
            messages=messages,
            temperature=temperature,
        )
        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        logger.error(f"API 錯誤: {str(e)}", exc_info=True)
        return jsonify({"error": f"伺服器錯誤: {str(e)}"}), 500

@app.route("/api/download", methods=["POST"])
def download():
    try:
        data = request.get_json()
        content = data.get("content", "")
        
        # 生成檔案並返回下載連結
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"AI法律意見書_{timestamp}.html"
        
        return jsonify({
            "filename": filename,
            "content": content,
            "download_url": f"/downloads/{filename}"  # 需配合實際檔案服務
        })
        
    except Exception as e:
        logger.error(f"下載錯誤: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)