from logging import exception

from google import genai
import time
from google.genai import interactions

client = genai.Client()


for attempt in range(5):
    try:
        interactions = client.interactions.create(
            model="gemini-4-hydrogen",
            input = "Explain how AI works in a few words"
        )

        print(interactions.output_text)
        break
    except Exception as e:
        error_429 = str(e)
        if "429" in error_429:
            print("Лимит исчерпан")
            break
        wait = (attempt + 1) * 2
        print(f"Произошла ошибка {e}\n Повтор через {wait} секунд")
        time.sleep(wait)