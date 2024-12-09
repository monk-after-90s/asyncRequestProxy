# asyncRequestProxy

异步请求代理，将一个HTTP请求代理为异步请求。

## 安装

```shell
pip install -r requirements.txt
```

## 运行

```python
OPENAI_API_KEY=[your api key] OPENAI_BASE_URL=[your openai compatible base url] MODEL=[your model] uvicorn main:app
```

更多关于Fastapi的使用请参考[Fastapi文档](https://fastapi.tiangolo.com/zh/)。

## 使用

参见文档路径“/docs”或者“/redoc”。