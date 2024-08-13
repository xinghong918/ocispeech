from fastapi import FastAPI,Body
import argparse,uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from pydantic import BaseModel
import pydantic
from typing import Any
import threading
import asyncio

import websockets
from myWebSocketServer import WebsocketServerRun, WebsocketServerStop, sendMsg as wsServerSendMsg, getWSStatus, connections as wsClientConnections
from MyAudioService import myAudioServ
import config as cfg

import pyaudio


# app = FastAPI()

## allow cors
OPEN_CROSS_DOMAIN = True

ws_connection = None
audio_ws_on = False
audio_ws_loop = None

async def onHandleWSConnection(websocket, path):
    # 处理新的 WebSocket 连接
    print("New WebSocket client connected")
    wsClientConnections.add(websocket)
    if cfg.SPEECH_REALTIME_SERVER_URI is not None and len(cfg.SPEECH_REALTIME_SERVER_URI)>0:
        start_audio_ws()
    try:
        # 循环接收客户端消息并处理
        async for message in websocket:
            # print(f"Received message from client: {message}")
            global audio_ws_on
            if len(message) > 0 and audio_ws_on == False:
                print(f"接收消息{message}")
                start_audio_ws(message)
    except websockets.exceptions.ConnectionClosed:
        # connections.remove(websocket)
        wsClientConnections.discard(websocket)
        stop_audio_ws()
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
        stop_audio_ws()
    except RuntimeError as e:
        print(f"Connection RuntimeError: {e}")
        stop_audio_ws()
    except Exception as e:
        print(f"Connection Exception: {e}")
        stop_audio_ws()
    finally:
        # 处理完毕，关闭 WebSocket 连接
        wsClientConnections.discard(websocket)

    print("My WebSocket connection closed")
    stop_audio_ws()





def onHandleAudioCallback(in_data, frame_count, time_info, status):
    # This function will be called by PyAudio when there's new audio data
    # send audio data
    send_audio_data(in_data)
    # print(f"queue size is:{queue.qsize()}")
    return (None, pyaudio.paContinue)

async def wsclient_send_data(data):
    global ws_connection
    if ws_connection is not None:
        await ws_connection.send(data)

def send_audio_data(data):
    # global ws_connection
    # # 判断连接状态
    # if ws_connection.connected:
    #     print("WebSocket当前处于连接状态")
    # else:
    #     print("WebSocket当前不处于连接状态")
    try:
        asyncio.run(wsclient_send_data(data))
    except Exception as e:
        print(f"send_audio_data exception :{e}")

async def document():
    return RedirectResponse(url="/docs")

class BaseResponse(BaseModel):
    code: int = pydantic.Field(200, description="API status code")
    msg: str = pydantic.Field("success", description="API status message")
    data: Any = pydantic.Field(None, description="API data")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "msg": "success",
            }
        }


def get_ws_status():
    data = getWSStatus()
    return BaseResponse(data=data)

async def ws_connect(uri):
    print(f"Connecting to: {uri}")
    global audio_ws_on, ws_connection
    async with websockets.connect(uri) as ws:
        ws_connection = ws
        print("Connected")
        # await ws_connection.send(f"say hi")
        try:
            while audio_ws_on:
                msg = await ws_connection.recv()
                print(msg)
                wsServerSendMsg(msg)
        except websockets.exceptions.ConnectionClosedOK as e:
            print(f"Disconnected! {e}")

def start_audio_ws_client(server_uri):
    global audio_ws_loop
    try:
        audio_ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(audio_ws_loop)
        audio_ws_loop.run_until_complete(ws_connect(server_uri))
    except RuntimeError as e:
        print(f"start_audio_ws_client_async RuntimeError(manually stop speech ws client) : {e}")

def start_audio_ws_api( speech_server_uri: str = Body("", description="set remote speech server uri")):
    start_audio_ws(speech_server_uri)

def start_audio_ws(speech_server_uri: str = ""):
    global audio_ws_loop, ws_connection, audio_ws_on
    if audio_ws_on ==  True:
        msg = "OK"
        data = "Audio is on. No need to atart it again!"
    else:
        audio_ws_on = True
        msg = "OK"
        data = "Start Audio Successfully!"
        server_uri = cfg.SPEECH_REALTIME_SERVER_URI
        if speech_server_uri is not None or speech_server_uri != "":
            server_uri = speech_server_uri
        if server_uri is None or server_uri == "":
            server_uri = "ws://localhost:7890"

        # loop = asyncio.get_event_loop()
        # loop.create_task(open_audio())
        print(f"connect to speech server: {server_uri}")
        try:
            # start audio
            myAudioServ.openAudio(onHandleAudioCallback)

            # start websocket client to speech server
            thread = threading.Thread(target=start_audio_ws_client, args=(server_uri,))
            thread.start()

        except RuntimeError as e:
            msg = "ERROR"
            data = f"start_audio_ws RuntimeError: {e}"
            print(data)
            audio_ws_loop.close()

    return BaseResponse(msg=msg, data=data)

async def stop_audio_ws_async():
    global ws_connection, audio_ws_on, audio_ws_loop
    try:
        audio_ws_on = False
        # 如果开启正常的stop loop，websocket断开就不能立马执行，会延迟
        # audio_ws_loop.stop()
        # asyncio.all_tasks().clear()
        await ws_connection.close()

    except Exception as e:
        print(f"websocket client is closed! {e}")

    print("stop_audio_ws_async closed!")

def stop_audio_ws():
    global ws_connection, audio_ws_on, audio_ws_loop
    if audio_ws_on ==  False:
        msg = "OK"
        data = "Audio is off. No need to stop it again!"
    else:
        try:
            msg = "OK"
            data = "Stop Audio Successfully!"
            myAudioServ.stopAudio()
            asyncio.create_task(stop_audio_ws_async())
        except Exception as e:
            msg = "ERROR"
            data = f"stop_audio_ws exception: {e}"
            print(data)

    return BaseResponse(msg=msg, data=data)

def start_ws_localserver(port: int = Body(7890, description="websocket server port")):
    msg = "OK"
    data = f"Start websocket server on port {port} successfully"
    try:
        # WebsocketServerRun(port)
        thread = threading.Thread(target=WebsocketServerRun, args=(port, onHandleWSConnection, ))
        thread.start()
    except Exception as e:
        errMsg = f"start_ws exception {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)

async def connect_remote_speech_server(ws_uri):
    print(f"Connecting to: {ws_uri}")
    async with websockets.connect(ws_uri) as ws:
        global remote_ws_speech_connection
        remote_ws_speech_connection = ws
        print("Connected")
        while True:
            msg = await remote_ws_speech_connection.recv()
            print(msg)


def create_app():
    app = FastAPI(
        title="OCI Speech Realtime Client-Websocket Server, Cathy",
        docs_url=None, redoc_url=None
    )
    app.mount("/static", StaticFiles(directory="./static"), name="static")
    if OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.get("/",
            response_model=BaseResponse,
            summary="swagger 文档")(document)



    # app.get("/ocispeech/ws_status",
    #         tags=["ws"],
    #         summary="Check websocket status")(get_ws_status)
    #
    app.post("/ocispeech/start_audio_ws",
             tags=["audioWS"],
             summary="Start Audio and ws connect to the speech websocket server")(start_audio_ws_api)

    app.post("/ocispeech/stop_audio_ws",
             tags=["audioWS"],
             summary="Stop Audio and ws connect to the speech websocket server")(stop_audio_ws)


    return app


app = create_app()



@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        # oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )




def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(app,
                    host=host,
                    port=port,
                    ssl_keyfile=kwargs.get("ssl_keyfile"),
                    ssl_certfile=kwargs.get("ssl_certfile"),
                    )
    else:
        uvicorn.run(app, host=host, port=port)
        # uvicorn.run(app, host=host, port=port, reload=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='OCI Speech Operation REST APIs for Client',
                                     description='For client use via websocket')
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7892)
    parser.add_argument("--ws_port", type=int, default=7891)
    # 通过三种方式，优先级分别为：调用在有ws客户端连接时传过来，start_audio_ws时动态传入(不会重置config中的值)，通过启动参数--ws_uri传入，通过配置文件配置(在打包以后此方式无效)
    parser.add_argument("--ws_uri", type=str)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)

    # 初始化消息
    args = parser.parse_args()

    if args.ws_uri is not None:
        cfg.SPEECH_REALTIME_SERVER_URI = args.ws_uri

    # print(f"speech server uri is: {cfg.SPEECH_REALTIME_SERVER_URI}")

    start_ws_localserver(args.ws_port)

    try:
        run_api(host=args.host,
                port=args.port,
                ssl_keyfile=args.ssl_keyfile,
                ssl_certfile=args.ssl_certfile,
                )
    except KeyboardInterrupt as e:
        print(f"exit!")
        WebsocketServerStop()
    except Exception as e:
        print(f"run_api error: {e}")

    print("Done")