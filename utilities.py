import base64

import httpx


async def forward_response(r: httpx.Response, forward_url: str, client: httpx.AsyncClient | None = None):
    # 获取响应头、状态码和其他可能需要的元数据
    response_headers = r.headers
    response_status_code = r.status_code

    # 根据响应的Content-Type决定如何处理内容
    if 'application/json' in response_headers.get('Content-Type', ''):
        # 如果是JSON数据
        response_data = r.json()  # 获取JSON内容

        post_json = {
            'response_status_code': response_status_code,
            'response_data': response_data
        }
    elif 'text' in response_headers.get('Content-Type', ''):
        # 如果是文本数据
        post_json = {
            'response_status_code': response_status_code,
            'response_data': r.text
        }
    else:
        # 其他类型的处理
        post_json = {
            'response_status_code': response_status_code,
            'response_data': base64.b64encode(r.content).decode('utf-8')
        }

    # 转发请求
    new_c = None
    client = client or (new_c := httpx.AsyncClient())
    try:
        forward_res = await client.post(forward_url, json=post_json)
        # 返回转发后的响应
        return forward_res
    finally:
        if new_c: await new_c.aclose()
