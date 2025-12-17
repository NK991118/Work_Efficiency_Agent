import os
import requests
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# SLLM_API_URL = os.getenv("SLLM_API_URL")


# url = SLLM_API_URL + "/api/v1/chat"
headers = {"Content-Type": "application/json"}


def run_sllm(history, permission="none", tone="formal"):
    base = os.getenv("SLLM_API_URL")
    if not base:
        raise ValueError("SLLM_API_URL is not set")
    
    url = base.rstrip("/") + "/api/v1/chat"
    
    logger.info(f"permission={permission}, tone={tone}")
    data = {"history": history, "permission": permission, "tone": tone}

    # response = requests.post(url, headers=headers, json=data)
    # response = requests.post(url, headers=headers, json=data, timeout=(5, 180))
    
    # if not response.ok:
    #     raise RuntimeError(f"sLLM error {response.status_code}: {response.text[:200]}")

    # res = response.json()
    response = requests.post(url, headers=headers, json=data, timeout=120)

    if response.status_code != 200:
        logger.error(f"SLLM error {response.status_code}: {response.text}")
        raise RuntimeError(f"SLLM error {response.status_code}: {response.text}")

    res = response.json()


    # tool_calls와 tool_responses가 없을 경우 빈 문자열 반환
    tool_calls = res.get("tool_calls", "")
    tool_responses = res.get("tool_responses", "")

    return res["response"], res["title"], tool_calls, tool_responses
