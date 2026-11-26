import os
import time
from mistralai.client import Mistral

client = Mistral(api_key=os.environ["MENSTRAL_API_KEY"])

models = client.models.list().data
chat = sorted({
    m.id for m in models
    if getattr(getattr(m, "capabilities", None), "completion_chat", False)
})
print("Чат-моделей:", len(chat))

ok = []
for mid in chat:
    for attempt in range(2):
        try:
            r = client.chat.complete(
                model=mid,
                messages=[{"role": "user", "content": "Ответь одним словом: ок"}],
                max_tokens=5,
            )
            ok.append(mid)
            print(mid, "-> OK:", r.choices[0].message.content)
            break
        except Exception as e:
            text = str(e)
            if "429" in text and attempt == 0:
                print(mid, "-> 429, жду 35 с")
                time.sleep(35)
                continue
            print(mid, "->", text[:90])
            break
    time.sleep(31)

print("\nРаботают:", ok if ok else "ни одна модель не ответила")