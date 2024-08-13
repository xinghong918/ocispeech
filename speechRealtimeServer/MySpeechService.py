import asyncio

# import threading
from oci.config import from_file
import oci
from oci.ai_speech_realtime import (
    RealtimeClient,
    RealtimeClientListener,
    RealtimeParameters,
)
import websockets
import config as cfg



class MyListener(RealtimeClientListener):
    def on_result(self, result):
        if result["transcriptions"][0]["isFinal"]:
            print(
                f"Received final results: {result['transcriptions'][0]['transcription']}"
            )
        else:
            print(
                f"Received partial results: {result['transcriptions'][0]['transcription']}"
            )

    def on_ack_message(self, ackmessage):
        return super().on_ack_message(ackmessage)

    def on_connect(self):
        return super().on_connect()

    def on_connect_message(self, connectmessage):
        return super().on_connect_message(connectmessage)

    def on_network_event(self, ackmessage):
        return super().on_network_event(ackmessage)

    def on_error(self, error):
        return super().on_error(error)


class MyRealtimeClient(RealtimeClient):
    async def connect(self):
        print(f"Connecting to: {self.uri}")
        async with websockets.connect(self.uri, extra_headers = {"Content-Type": self.realtime_speech_parameters.encoding}, ping_interval=None) as ws:
            self.connection = ws
            print("MyRealtimeClient Opened")
            self.listener.on_connect()
            await self._send_credentials(ws)
            await self._handle_messages(ws)

class MySpeechService:
    config: object = None
    queue: object = None
    realtime_speech_parameters: RealtimeParameters = RealtimeParameters()
    realtime_speech_url = (
        # "ws://realtime.aiservice-preprod.us-phoenix-1.oci.oracleiaas.com"
        # "wss://realtime.aiservice.us-phoenix-1.oci.oraclecloud.com/ws/transcribe/stream"
        cfg.OCI_REALTIME_SPEECH_URl
    )
    stream: object = None
    client: object = None
    myloop: object = None

    isRunning = False
    speech_listener = MyListener()

    def __init__(self, speechRealtime_config):
        # self.config = speechRealtime_config

        print("########## oci.config.DEFAULT_PROFILE: ", oci.config.DEFAULT_PROFILE)

        # Run the event loop

        self.realtime_speech_parameters.language_code = "en-US"
        self.realtime_speech_parameters.model_domain = "GENERIC"
        self.realtime_speech_parameters.partial_silence_threshold_in_ms = 0
        self.realtime_speech_parameters.final_silence_threshold_in_ms = 1000
        self.realtime_speech_parameters.should_ignore_invalid_customizations = False


    def setRTSpeechParameters(self, new_para):
        self.realtime_speech_parameters.language_code = new_para["language_code"]
        self.realtime_speech_parameters.model_domain = new_para["model_domain"]
        self.realtime_speech_parameters.partial_silence_threshold_in_ms = new_para["partial_silence_threshold_in_ms"]
        self.realtime_speech_parameters.final_silence_threshold_in_ms = new_para["final_silence_threshold_in_ms"]
        self.realtime_speech_parameters.should_ignore_invalid_customizations = new_para["should_ignore_invalid_customizations"]



    def openRealtime(self, custListner = None):
        if self.isRunning == True:
            print("Server is running...")
            return

        # Create a FIFO queue
        self.queue = asyncio.Queue()
        self.config = from_file()

        def message_callback(message):
            print(f"Received message: {message}")

        if custListner is not None:
            self.speech_listener = custListner()

        self.client = MyRealtimeClient(
            config=from_file(),
            realtime_speech_parameters=self.realtime_speech_parameters,
            listener=self.speech_listener, #MyListener(),
            service_endpoint=self.realtime_speech_url,
            signer=self.authenticator(),
            compartment_id=cfg.OCI_COMPARTENT_ID,
        )


        try:
            self.isRunning = True
            self.myloop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.myloop)
            # print(f"myloop is : {id(self.myloop)}")
            self.myloop.create_task(self.send_audio())
            self.myloop.run_until_complete(self.client.connect())
            # self.myloop.run_forever()
        except RuntimeError as e:
            print(f"openRealtime event loop RuntimeError {e}")
        finally:
            # print('openRealtime - About to close the loop.')
            # self.myloop.close()
            self.isRunning = False

    def closeRealtime(self):
        if self.isRunning == True:
            self.client.close()
            if not self.queue.empty():
                self.queue.task_done()
            self.myloop.stop()
            # self.myloop.close()
            self.isRunning = False
            print("Closed now")
        else:
            print("Not running at all")

    # def closeRT(self):
    #     closeRealtime()
        # asyncio.run(self.closeRealtime())

    def setSpeechConfig(self, speech_config):
        self.config = speech_config
        self.realtime_speech_url = (speech_config.realtime_speech_url)

    def authenticator(self):
        config_file = from_file(cfg.OCI_AUTH_FILE_LOCATION, cfg.OCI_AUTH_PROFILE_NAME)

        signer = oci.signer.Signer(
            tenancy=config_file["tenancy"],
            user=config_file["user"],
            fingerprint=config_file["fingerprint"],
            private_key_file_location=config_file.get("key_file"),
            pass_phrase=oci.config.get_config_value_or_default(config_file, "pass_phrase"),
            private_key_content=config_file.get("key_content")
        )
        return signer

    def set_audio(self, in_data):
        self.queue.put_nowait(in_data)


    async def send_audio(self):
        i = 0
        # loop = asyncio.get_running_loop()
        while True:
            data = await self.queue.get()
            # print("data",data)
            # Send it over the websocket
            await self.client.send_data(data)
            i += 1

class MySpeechConfig:
    config_json = {
        "region": "us-phoenix-1",
        "language":"en"
    }

    def __init__(self, config = None):
        if config is None:
            pass
        else:
            self.config_json = config




mySpeechServ = MySpeechService(MySpeechConfig())

# def startTest(speech):
#     print("start sleep...")
#     time.sleep(10)
#     print("end sleep")
#     speech.closeRT()

# if __name__ == '__main__':
    # thread_ws = threading.Thread(target=WebsocketServerRun, args=(7890,))
    # thread_ws.start()
    # print("Done starting websocket...")
    #
    # # cfg = MySpeechConfig()
    # # speech = MySpeechService(cfg)
    # print(mySpeechServ.config.config_json)
    #
    # thread_speech = threading.Thread(target=startTest, args=(mySpeechServ,))
    # thread_speech.start()
    #
    # mySpeechServ.openRealtime()
    #
    # print("done starting...")
    #
    # asyncio.get_event_loop().close()
    #
    # WebsocketServerStop()
    #
    # print("done2")
    # speech.closeRealtime()