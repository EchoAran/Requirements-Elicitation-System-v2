import asyncio
import httpx
from typing import Optional
import time

class LLMHandler:

    def __init__(self, api_url: str, api_key: str, model_name: str):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    async def aclose(self) -> None:
        await self.client.aclose()

    def _validate_settings(self) -> bool:
        required_fields = [self.api_url, self.api_key, self.model_name]
        return all(field and field.strip() for field in required_fields)

    def _should_retry_status(self, status_code: int) -> bool:
        if status_code == 429:
            return True
        return 500 <= status_code < 600

    async def call_llm(self, prompt: str, query: str = "") -> Optional[str]:
        if not self._validate_settings():
            print("The LLM Settings are incomplete, making it impossible to call the large model")
            return None

        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": query}]
        request_data = {"model": self.model_name, "messages": messages}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        attempts = 3
        base_delay = 0.8
        last_error_text = None
        for i in range(attempts):
            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[PROMPT] LLM call attempt {i + 1} with prompt: \n{prompt}")
            if query.strip():
                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[QUERY] LLM call attempt {i + 1} with query: \n{query}")
            print(f"\n{'---'*40}")
            try:
                response = await self.client.post(self.api_url, json=request_data, headers=headers, timeout=httpx.Timeout(30.0))
                if response.status_code == 200:
                    try:
                        result = response.json()
                    except Exception:
                        last_error_text = "response_json_error"
                        if i >= attempts - 1:
                            break
                        delay = base_delay * (2 ** i)
                        await asyncio.sleep(delay)
                        continue
                    if 'choices' in result and len(result['choices']) > 0:
                        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] response: {result['choices'][0]['message']['content'].strip()}")
                        print(f"\n{'---'*40}")
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] response format exception: {result}")
                        last_error_text = "format_error"
                    # fallthrough to retry
                else:
                    last_error_text = f"{response.status_code} - {response.text}"
                    print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] call failed: {last_error_text}")
                    if not self._should_retry_status(response.status_code):
                        break
            except httpx.ConnectError as e:
                last_error_text = str(e)
                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] connection failed: {last_error_text}")
            except httpx.TimeoutException as e:
                last_error_text = str(e)
                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] request timed out: {last_error_text}")
            except Exception as e:
                last_error_text = f"{str(e)} ({type(e).__name__})"
                print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[LLM] error occurred when invoking the LLM service: {last_error_text}")
            if i < attempts - 1:
                delay = base_delay * (2 ** i)
                try:
                    await asyncio.sleep(delay)
                except Exception:
                    pass
        return None

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0,
    ) -> Optional[dict]:
        if not self._validate_settings():
            return None
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        attempts = 3
        base_delay = 0.8
        for i in range(attempts):
            tools_info = payload.get("tools", [])
            print(f"\n{'---'*40}")
            print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[SKILL] LLM call attempt {i + 1} with skill: \n{tools_info}")
            try:
                response = await self.client.post(self.api_url, json=payload, headers=headers, timeout=httpx.Timeout(60.0))
                if response.status_code == 200:
                    try:
                        result = response.json()
                    except Exception:
                        if i >= attempts - 1:
                            break
                        delay = base_delay * (2 ** i)
                        await asyncio.sleep(delay)
                        continue
                    choices = result.get("choices") if isinstance(result, dict) else None
                    if isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict):
                        print(f"\n{'---'*40}")
                        print(f"\n{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}[SKILL] response: {choices[0]}")
                        return choices[0]
                else:
                    if not self._should_retry_status(response.status_code):
                        break
            except httpx.ConnectError:
                pass
            except httpx.TimeoutException:
                pass
            except Exception:
                pass
            if i < attempts - 1:
                delay = base_delay * (2 ** i)
                try:
                    await asyncio.sleep(delay)
                except Exception:
                    pass
        return None

    async def get_embedding(self, text: str, embedding_api_url: Optional[str] = None, model_name: Optional[str] = None) -> Optional[list[float]]:
        url = embedding_api_url or "https://api.rcouyi.com/v1/embeddings"
        model = model_name or "text-embedding-3-large"
        data = {"model": model, "input": text}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        attempts = 3
        base_delay = 0.8
        for i in range(attempts):
            try:
                response = await self.client.post(url, json=data, headers=headers, timeout=httpx.Timeout(30.0))
                if response.status_code == 200:
                    result = response.json()
                    if "data" in result and len(result["data"]) > 0 and "embedding" in result["data"][0]:
                        return result["data"][0]["embedding"]
                    else:
                        pass
                else:
                    if not self._should_retry_status(response.status_code):
                        break
            except httpx.ConnectError:
                pass
            except httpx.TimeoutException:
                pass
            except Exception:
                pass
            if i < attempts - 1:
                delay = base_delay * (2 ** i)
                try:
                    await asyncio.sleep(delay)
                except Exception:
                    pass
        return None

 
