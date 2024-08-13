import asyncio
import websockets
import threading
import datetime
import time

connections = set()
server_loop = None
ws_port = 7890

async def handle_websocket_connection(websocket, path):
    # 处理新的 WebSocket 连接
    print("New WebSocket client connected")
    await asyncio.sleep(1)
    connections.add(websocket)
    try:
        # 循环接收客户端消息并处理
        async for message in websocket:
            print(f"Received message from client: {message}")
    except websockets.exceptions.ConnectionClosed:
        # connections.remove(websocket)
        connections.discard(websocket)
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
    except RuntimeError as e:
        print(f"Connection RuntimeError: {e}")
    except Exception as e:
        print(f"Connection Exception: {e}")
    finally:
        # pass
        connections.discard(websocket)
        # 处理完毕，关闭 WebSocket 连接
    print("WebSocket connection closed")



def WebsocketServerRun(port, your_handle_websocket_connection):
    print(f"##### WebSocket server is starting on port {port}\n")
    global ws_port, server_loop
    ws_port = port
    server_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(server_loop)
    # 启动 WebSocket 服务端并等待连接
    ws_callback = handle_websocket_connection
    if your_handle_websocket_connection != None:
        ws_callback = your_handle_websocket_connection
    start_server = websockets.serve(ws_callback, "0.0.0.0", port)
    # start_server = websockets.serve(handle_websocket_connection, "localhost", port)

    try:
        server_loop.run_until_complete(start_server)
        server_loop.run_forever()
    except RuntimeError as e:
        print(f"##### Runtime error: {e}")
    finally:
        print('About to close the loop.')
        server_loop.close()

def WebsocketServerStop():
    # server_loop.stop()
    server_loop.call_soon_threadsafe(server_loop.stop)
    print('#### WebSocket Stopped.')

def getWSStatus():
    global ws_port
    data = {
        "port": ws_port,
        "connections": len(connections)
    }
    return data

async def sendMsgAsync(msg):
    for i in connections:
        await i.send(f'{msg}')
    pass

def sendMsg(msg):
    asyncio.run(sendMsgAsync(msg))

#
# if __name__ == '__main__':
#     thread = threading.Thread(target=WebsocketServerRun, args=(7890, ))
#     thread.start()
#     print(thread)
#
#     print("Done")
#
#     time.sleep(10)
#
#     thread1 = threading.Thread(target=sendMsg, args=("ass",))
#     thread1.start()
#     print(thread1)
#
#     print("Done 2")
#
#     time.sleep(4)
#     print("start stopping")
#     # for i in asyncio.all_tasks():
#     #     i.cancel()
#     server_loop.stop()
#     # server_loop.call_soon_threadsafe(server_loop.stop)
#
#
#     print("Done stopping")




