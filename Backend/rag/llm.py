import os
import time
import random
from google import genai
from google.genai.errors import APIError

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


class LLM:

    def __init__(self,
                 model=None):

        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def generate(self,
                 prompt: str) -> str:
        
        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt
                )
                return response.text
            except APIError as e:
                # Retry on 429 (Rate Limit) or 503 (Service Unavailable)
                if (e.code in [429, 503]) and attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini API returned {e.code}. Retrying in {sleep_time:.2f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    raise e
            except Exception as e:
                raise e

    def generate_stream(self,
                        prompt: str):
        """
        Yield response chunks from Gemini model in real-time.
        """
        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            yielded_any = False
            try:
                response_stream = client.models.generate_content_stream(
                    model=self.model,
                    contents=prompt
                )
                for chunk in response_stream:
                    if chunk.text:
                        yielded_any = True
                        yield chunk.text
                return
            except APIError as e:
                # Only retry if we haven't yielded any chunks yet
                if not yielded_any and (e.code in [429, 503]) and attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Gemini stream API returned {e.code}. Retrying in {sleep_time:.2f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    raise e
            except Exception as e:
                raise e