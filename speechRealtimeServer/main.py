import time

from fastapi import FastAPI, Body
import argparse, uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import (
    get_swagger_ui_html,
)
from fastapi.middleware.cors import CORSMiddleware
from oci.ai_speech_realtime import RealtimeClientListener
from starlette.responses import RedirectResponse
from pydantic import BaseModel
import pydantic
from typing import Any
import threading
import asyncio

import websockets
from myWebSocketServer import WebsocketServerRun, WebsocketServerStop, sendMsg, getWSStatus, \
    connections as wsClientConnections
from MySpeechService import mySpeechServ

# app = FastAPI()

## allow cors
OPEN_CROSS_DOMAIN = True


# queue = asyncio.Queue()

class onHandleSpeechResult(RealtimeClientListener):
    def on_result(self, result):
        if result["transcriptions"][0]["isFinal"]:
            print(
                f"Received final results: {result['transcriptions'][0]['transcription']}"
            )
            thread = threading.Thread(target=sendMsg, args=(result['transcriptions'][0]['transcription'],))
            thread.start()
        else:
            print(
                f"Received partial results: {result['transcriptions'][0]['transcription']}"
            )

    def on_ack_message(self, ackmessage):
        print(f"!!! onHandleSpeechResult: on_ack_message")
        return super().on_ack_message(ackmessage)

    def on_connect(self):
        # print(f"!!! onHandleSpeechResult: on_connect")
        return super().on_connect()

    def on_connect_message(self, connectmessage):
        # print(f"!!! onHandleSpeechResult: on_connect_message")
        return super().on_connect_message(connectmessage)

    def on_network_event(self, ackmessage):
        print(f"!!! onHandleSpeechResult: on_network_event")

        return super().on_network_event(ackmessage)

    def on_error(self, error):
        print(f"!!! onHandleSpeechResult: on_error: {error}")
        stop_speech()
        start_speech()
        return super().on_error(error)


async def onHandleWSConnection(websocket, path):
    # 处理新的 WebSocket 连接
    print("New WebSocket client connected")
    await asyncio.sleep(1)
    wsClientConnections.add(websocket)
    try:
        # 循环接收客户端消息并处理
        async for message in websocket:
            mySpeechServ.set_audio(message)
    except websockets.exceptions.ConnectionClosed:
        # connections.remove(websocket)
        wsClientConnections.discard(websocket)
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
    except RuntimeError as e:
        print(f"Connection RuntimeError: {e}")
    except Exception as e:
        print(f"Connection Exception: {e}")
    finally:
        # pass
        wsClientConnections.discard(websocket)
        # 处理完毕，关闭 WebSocket 连接
    print("WebSocket connection closed")


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


def start_ws(port: int = Body(7890, description="websocket server port")):
    msg = "OK"
    data = f"Start websocket server on port {port} successfully"
    try:
        # WebsocketServerRun(port)
        thread = threading.Thread(target=WebsocketServerRun, args=(port, onHandleWSConnection,))
        thread.start()
    except Exception as e:
        errMsg = f"start_ws exception {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


def speech_status():
    msg = "OK"
    data = f"False"
    try:
        data = f"{mySpeechServ.isRunning}"
    except Exception as e:
        errMsg = f"speech_status exception {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


def get_speech_parameters():
    msg = "OK"
    try:
        para = {
            "language_code": mySpeechServ.realtime_speech_parameters.language_code,
            "model_domain": mySpeechServ.realtime_speech_parameters.model_domain,
            "partial_silence_threshold_in_ms": mySpeechServ.realtime_speech_parameters.partial_silence_threshold_in_ms,
            "final_silence_threshold_in_ms": mySpeechServ.realtime_speech_parameters.final_silence_threshold_in_ms,
            "should_ignore_invalid_customizations": mySpeechServ.realtime_speech_parameters.should_ignore_invalid_customizations
        }
        print(f"OCI Speech Realtime parameters is : {para}")
        data = para
    except Exception as e:
        errMsg = f"get_speech_parameters exception: {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


# class speechConfigItems(BaseModel):
#     region: str = ""
#     language: str = ""
#     realtime_speech_url: str = ""
#     compartment_id: str = ""
#     tenancy: str = ""
#     user: str = "ocid1.user.oc1.....offya"
#     fingerprint: str = "32:...2:00"
#     pass_phrase: str = ""
#     private_key_content: str = "-----BEGIN PRIVATE KEY-----\nMIIE...RK97sw\ngvxuX1EW...9w0\nCtxr...K/1/\nTUh4...lMMBBF+cn\n-----END PRIVATE KEY-----"
#
# def speech_config(speechConfig: speechConfigItems):
#     msg = "OK"
#     try:
#         data = speechConfig.json()
#         print(data)
#         mySpeechServ.setSpeechConfig(data)
#     except Exception as e:
#         errMsg = f"speech_parameters exception: {e}"
#         print(errMsg)
#         msg = "ERROR"
#         data = errMsg
#
#     return BaseResponse(msg=msg, data=data)

def speech_parameters(
        language_code: str = Body("en-US", description="set speech parameters - language_code", examples=["en-US"]),
        model_domain: str = Body("GENERIC", description="set speech parameters -language_code", examples=["GENERIC"]),
        partial_silence_threshold_in_ms: int = Body(0, description='partial silence threshold in ms', examples=[0]),
        final_silence_threshold_in_ms: int = Body(2000, description='final silence threshold in ms', examples=[1000]),
        should_ignore_invalid_customizations: bool = Body(False, description='should ignore invalid customizations',
                                                          examples=[False])):
    msg = "OK"
    try:
        new_para = {
            "language_code": language_code,
            "model_domain": model_domain,
            "partial_silence_threshold_in_ms": partial_silence_threshold_in_ms,
            "final_silence_threshold_in_ms": final_silence_threshold_in_ms,
            "should_ignore_invalid_customizations": should_ignore_invalid_customizations
        }
        print(f"new speech realtime parameters is : {new_para}")
        mySpeechServ.setRTSpeechParameters(new_para)
        data = new_para
    except Exception as e:
        errMsg = f"speech_parameters exception: {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


def start_speech():
    msg = "OK"
    data = f"Start speech client server successfully"
    try:
        if mySpeechServ.isRunning == False:
            # print(f"start_speech: thread id: {threading.current_thread().ident} ")
            # print(f"loop id: {id(asyncio.get_event_loop())}, thread id: {threading.get_native_id()} ")
            thread = threading.Thread(target=mySpeechServ.openRealtime, args=(onHandleSpeechResult,))
            thread.start()

            print("done starting speech...")
        else:
            errMsg = f"No need to start speech client server again!"
            print(errMsg)
            msg = "ERROR"
            data = errMsg

    except Exception as e:
        errMsg = f"start_speech exception: {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


def stop_speech():
    msg = "OK"
    data = f"Stop speech client server successfully"
    try:
        if mySpeechServ.isRunning == True:
            mySpeechServ.closeRealtime()
            print("done stopping speech...")
        else:
            errMsg = f"Not running at all!"
            print(errMsg)
            msg = "ERROR"
            data = errMsg

    except Exception as e:
        errMsg = f"stop_speech exception: {e}"
        print(errMsg)
        msg = "ERROR"
        data = errMsg

    return BaseResponse(msg=msg, data=data)


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

    app.get("/ocispeech/ws_status",
            tags=["websocket"],
            summary="Check websocket status")(get_ws_status)

    app.get("/ocispeech/speech_status",
            tags=["speech"],
            summary="Check OCI Speech realtime server status. True is running; False is down")(speech_status)

    app.post("/ocispeech/start_speech",
             tags=["speech"],
             summary="Start OCI Speech realtime server")(start_speech)

    app.post("/ocispeech/stop_speech",
             tags=["speech"],
             summary="Stop OCI Speech realtime server")(stop_speech)

    # app.post("/ocispeech/speech_config",
    #         tags=["speech"],
    #         summary="Include OCI Auth and realtime url...")(speech_config)

    app.post("/ocispeech/speech_parameters",
             tags=["speech"],
             summary="Set OCI Speech realtime server parameters")(speech_parameters)

    app.get("/ocispeech/speech_parameters",
            tags=["speech"],
            summary="Get OCI Speech realtime server parameters")(get_speech_parameters)

    # app.get("/ocispeech/ws_status",
    #         tags=["ws"],
    #         summary="Check websocket status")(get_ws_status)
    #
    # app.post("/ocispeech/start_ws",
    #          tags=["ws"],
    #          summary="Start Websocket server on port")(start_ws)

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
    parser = argparse.ArgumentParser(prog='OCI Speech Operation REST APIs for Server',
                                     description='For Server use. Audio transfer from client via ws')
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7899)
    parser.add_argument("--ws_port", type=int, default=7890)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    # 初始化消息
    args = parser.parse_args()

    start_ws(args.ws_port)

    time.sleep(2)

    start_speech()

    try:
        run_api(host=args.host,
                port=args.port,
                ssl_keyfile=args.ssl_keyfile,
                ssl_certfile=args.ssl_certfile,
                )
    except KeyboardInterrupt as e:
        print(f"exit!")
    except Exception as e:
        print(f"run_api error: {e}")

    stop_speech()
    WebsocketServerStop()
    print("Done")