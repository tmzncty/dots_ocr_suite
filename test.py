import openai
import time
import threading

client = openai.OpenAI(
    api_key="EMPTY",
    base_url="http://192.168.24.78:4000/v1"  # 连 LiteLLM
)

def send_request(i):
    try:
        start = time.time()
        print(f"请求 {i} 发送中...")
        completion = client.chat.completions.create(
            model="dots-ocr",
            messages=[
                {"role": "user", "content": "hello"}
            ],
            max_tokens=10
        )
        duration = time.time() - start
        print(f"✅ 请求 {i} 完成! 耗时: {duration:.2f}s | 回复: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"❌ 请求 {i} 失败: {e}")

# 模拟 4 个并发请求，看看是不是两张卡一起动
threads = []
for i in range(4):
    t = threading.Thread(target=send_request, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()