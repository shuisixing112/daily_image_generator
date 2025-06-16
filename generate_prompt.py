# 生成 prompt 並上傳至 Firebase Storage

import os
from dotenv import load_dotenv
import requests
import json
import re
import base64
from datetime import datetime

from google.cloud import storage
import firebase_admin
from firebase_admin import credentials, storage

# 載入 .env 檔案中的環境變數
load_dotenv()
API_KEY = os.getenv("OPENROUTER_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_API_KEY
Bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
print(" os.getenv：\n", os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
print(" os.getenv：\n", os.getenv("FIREBASE_STORAGE_BUCKET"))

# 載入 Firebase Admin SDK
# cred = credentials.ApplicationDefault()
# initialize_app(cred,{
#     'storageBucket': os.getenv("daily-image-ai.appspot.com")
# })
cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
firebase_admin.initialize_app(cred, {
    'storageBucket': Bucket_name  # 替換為你的Firebase專案ID
})

# === 上傳文字檔到 Firebase Storage ===
def upload_txt_to_firebase(filepath, remote_path, Bucket_name):
    # client = storage.Client()
    bucket =storage.bucket(Bucket_name)
    blob = bucket.blob(remote_path)
    blob.upload_from_filename(filepath)
    print(f"☁️ 已上傳 {filepath} 到 Firebase Storage: {remote_path}")

# === 要送給 LLM 的欄位模板 ===
prompt_template = """
請協助將以下模板中的欄位 {} 隨機填入合適的詞彙，並請以固定 JSON 格式回傳以下結構：

{
  "animal": "hedgehog",
  "clothing": "knitted scarf",
  "action": "curled up",
  "location_description": "on a mossy tree stump",
  "prompt": "A peaceful hedgehog wearing a soft knitted scarf, curled up on a mossy tree stump. 2D pastel and colored pencil illustration, warm and muted color palette, soft yellow sunlight, hand-drawn with subtle paper texture. No harsh outlines, smooth shading, fuzzy edges, gentle expressions. Delicate details and warm tones throughout. Children's picture book style, calm and emotionally soothing atmosphere."
}

模板如下：
A {adj_animal} {animal} wearing a {adj_clothing} {clothing}, {action} {location_description}.
2D pastel and colored pencil illustration, warm and muted color palette, soft yellow sunlight, hand-drawn with subtle paper texture.
No harsh outlines, smooth shading, fuzzy edges, gentle expressions.
Delicate details and warm tones throughout.
Children's picture book style, calm and emotionally soothing atmosphere

"""

# === 設定模型與 API 請求參數 ===
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "deepseek/deepseek-r1-0528:free",  # 或換成 openrouter/cinematika-7b、meta-llama/codellama-13b-instruct 等
    "messages": [
        #{"role": "system", "content": "你是一位擅長文案創作的插畫腳本生成助手"}, # ***測試看看，效果不好要拿掉***
        {"role": "user", "content": prompt_template}
    ]
}

# === 發送請求並取得生成結果 ===
response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

if response.status_code == 200:
    result = response.json()
    generated_prompt = result['choices'][0]['message']['content']

    # 擷取資訊
    animal_match = re.search(r'"animal"\s*:\s*"([^"]+)"', generated_prompt, re.DOTALL)
    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', generated_prompt, re.DOTALL)

    animal = animal_match.group(1).replace(" ", "_") if animal_match else "unknown"
    action = action_match.group(1).replace(" ", "_") if action_match else "unknown"

    # 檔名
    now = datetime.now().strftime("%Y-%m-%d_%H%M-%S")
    filename = f"{now}_{animal}_{action}.txt"

    if animal == "unknown" or action == "unknown":
        print("⚠️ 無法擷取檔名關鍵字，改用 timestamp 儲存")
        filename = f"{now}_unknown.txt"

    # 儲存
    os.makedirs("prompts", exist_ok=True)
    filepath = os.path.join("prompts", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(generated_prompt)

        print("✅ 檔案已儲存！內容如下：\n", generated_prompt)
    
    # 上傳到 Firebase Storage
    remote_path = f"prompts/{filename}"
    print("憑證路徑：", os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    print("✅ 使用的 bucket：", Bucket_name)
    upload_txt_to_firebase(filepath, remote_path, Bucket_name)


else:
    print("❌ 發生錯誤：", response.status_code)
    print(response.text)