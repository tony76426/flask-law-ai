from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import logging
import json
import re

app = Flask(__name__)
CORS(app)

# 日志设置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化OpenAI客户端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 支持的模型映射
MODEL_MAPPING = {
    "gpt-4o-mini": "gpt-4-1106-preview",
    "gpt-3.5-turbo": "gpt-3.5-turbo"
}

def enforce_json_format(content):
    """确保AI返回标准JSON格式"""
    try:
        # 尝试直接解析
        parsed = json.loads(content)
        if isinstance(parsed, list) and len(parsed) == 3:
            return json.dumps(parsed)
        
        # 处理可能的JSON对象包裹情况
        if isinstance(parsed, dict):
            for value in parsed.values():
                if isinstance(value, list) and len(value) == 3:
                    return json.dumps(value)
        
        # 自动修正常见问题
        fixed = re.sub(r'[^{}\[\]]', '', content)
        if len(fixed) > 10:  # 最小有效JSON长度
            return fixed
    
    except json.JSONDecodeError:
        # 提取可能的JSON部分
        match = re.search(r'(\[.*\]|\{.*\})', content, re.DOTALL)
        if match:
            return match.group(1)
    
    return json.dumps(["问题解析失败，请重试", "请简化问题描述", "或联系管理员"])

@app.route("/api/generate", methods=["POST"])
def generate():
    raw_content = ""
    try:
        data = request.get_json()
        logger.info(f"收到请求: {json.dumps(data, ensure_ascii=False)[:500]}...")

        # 验证必要字段
        if not data or "messages" not in data:
            return jsonify({"error": "Missing required fields"}), 400

        # 模型验证
        model = data.get("model", "gpt-3.5-turbo")
        if model not in MODEL_MAPPING:
            return jsonify({"error": f"Unsupported model. Available: {list(MODEL_MAPPING.keys())}"}), 400

        # 强化提示词规范
        messages = data["messages"]
        if messages and messages[0]["role"] == "user":
            messages[0]["content"] = f"""你必须严格按以下规则响应：
1. 只返回标准JSON数组
2. 必须包含3个问题
3. 不要任何解释文本
4. 示例格式：["问题1","问题2","问题3"]

用户问题：
{messages[0]['content']}"""

        # API调用
        response = client.chat.completions.create(
            model=MODEL_MAPPING[model],
            messages=messages,
            temperature=min(max(float(data.get("temperature", 0.5)), 0, 2),
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        enforced_json = enforce_json_format(raw_content)
        
        return jsonify({
            "result": json.loads(enforced_json),
            "raw": raw_content  # 调试用
        })

    except Exception as e:
        logger.error(f"处理失败: {str(e)}\n原始内容: {raw_content}")
        return jsonify({
            "error": "AI响应格式异常",
            "details": str(e),
            "raw": raw_content
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)