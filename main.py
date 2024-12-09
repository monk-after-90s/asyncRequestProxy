import asyncio
import os
from urllib.parse import urljoin
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, HttpUrl, Field
from typing import List
import httpx
from contextlib import asynccontextmanager

from utilities import forward_response

httpx_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global httpx_client
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(500.0, connect=10.0), verify=False)
    yield
    await httpx_client.aclose()


app = FastAPI(title="异步请求代理", description="将一个网络请求代理为异步请求，通过Webhook返回结果", lifespan=lifespan)


class ForwardRequest(BaseModel):
    """
    用于转发HTTP请求的数据模型。

    Attributes:
        http_desc (str): 需要转发的HTTP请求的字符串表示。这个字符串应该尽可能详细地描述请求的意图，
                         包括请求方法（GET, POST, PUT, DELETE 等）、目标URL、任何查询参数、头信息以及请求体内容。
                         例如："发送一个POST请求到'https://www.example.com'，携带JSON{'name': 'John', 'age': 30}"。
        webhooks (List[HttpUrl]): 接收转发请求结果的Webhook URL列表。每当代理完成HTTP请求并收到响应后，
                                  它会将响应结果发送到此列表中的每一个URL。每个URL都必须是有效的HTTP或HTTPS URL。
    """

    http_desc: str = Field(
        ...,
        title="HTTP请求描述",
        description="需要转发的HTTP请求的字符串表示，尽可能详细地描述请求的意图。这段话是发给AI的，代码或者自然语言都行，不行的话多多尝试。",
        example="发送一个POST请求到'https://www.example.com'，携带JSON{'name': 'John', 'age': 30}"
    )

    webhooks: List[HttpUrl] = Field(
        ...,
        min_items=0,
        title="Webhook URLs",
        description="接收转发请求结果的Webhook URL列表。每个URL都必须是有效的HTTP或HTTPS URL。该接口需要处理post请求，接收JSON数据，"
                    "其中包含字段response_data和response_status_code。",
        example=["http://localhost:8000/receive_data"]
    )


@app.post("/", summary="请求代理与异步化", responses={
    200: {
        "description": "请求成功。",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "value": {"code": 200, "msg": "success", "data": ""}
                    }
                }
            }
        },
    }
})
async def root(request_data: ForwardRequest = Body(
    description="请求代理数据",
    example={
        "http_desc": "发送一个POST请求到‘https://www.example.com’，携带JSON{\"name\":\"John\",\"age\":30}",
        "webhooks": [
            "http://localhost:8000/receive_data"
        ]
    }
)):
    """
    转发HTTP请求，并异步返回结果。参数说明详见参数处具体描述。
    """
    payload = {
        "model": os.environ.get("MODEL", ""),
        "messages": [
            {
                "role": "system",
                "content": "你是Python代码生成器，httpx是你主要使用的库。你会收到HTTP请求的描述，将其转化为一个叫“httpx_request”的异"
                           "步函数，该函数只接受一个参数“httpx_client”，是httpx.AsyncClient的实例，你的全部回复就是这个异步函数定义代码，"
                           "即以'async def httpx_request(httpx_client):'开头的普通文本且没有markdown代码。"
                           "例如用户问题“发送一个POST请求到‘https://www.example.com’，携带JSON{\"name\":\"John\",\"age\":30}”，"
                           """那么你的全部回复是“
                           async def httpx_request(httpx_client):
                               return await httpx_client.post('https://www.example.com', json={'name': 'John', 'age': 30})
                           ”
                           ”"""
            },
            {
                "role": "user",
                "content": request_data.http_desc
            }
        ]
    }
    response = await httpx_client.post(
        url=urljoin(os.environ.get("OPENAI_BASE_URL") + "/", "chat/completions"),
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    response.raise_for_status()

    try:
        response_data = response.json()
    except ValueError:
        raise HTTPException(status_code=500, detail="Response is not valid JSON")

    # Extract the relevant message content from the response
    reply = response_data["choices"][0]["message"]["content"]
    exec(reply, globals())

    # 后台任务
    def reply_to_webhooks(task: asyncio.Task):
        if task.exception():
            raise task.exception()
        # 响应结果处理
        resp = task.result()
        # 异步返回结果
        for webhook in request_data.webhooks:
            # 原封不动将请求结果返给webhook
            asyncio.create_task(forward_response(resp, str(webhook), httpx_client))

    asyncio.create_task(httpx_request(httpx_client)).add_done_callback(reply_to_webhooks)
    return {"code": 200, "msg": "success", "data": ""}
