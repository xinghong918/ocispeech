import asyncio
import pyaudio
import json
# import threading

import config as cfg

class MyAudioService:
    # Create a FIFO queue
    queue = None
    stream = None
    myloop = None
    isOpen = False
    audioParams = { "SAMPLE_RATE": 16000, "FORMAT": pyaudio.paInt16, "CHANNELS": 1, "BUFFER_DURATION_MS": 96}

    isRunning = False

    def audio_callback(self, in_data, frame_count, time_info, status):
        # This function will be called by PyAudio when there's new audio data
        self.queue.put_nowait(in_data)
        # print(f"queue size is:{queue.qsize()}")
        return (None, pyaudio.paContinue)

    def __init__(self, audioParams = None):
        # Set audio parameters
        if audioParams is not None:
            self.audioParams = audioParams
        print(self.audioParams)


    def openAudio(self, custAudioCallback = None):
        rtn = [True, "Open Audio Successfully"]
        if self.isOpen == True:
            rtn[1] = "Audio is already on. No need to open it again"
        else:
            self.isOpen = True

            # Create a FIFO queue
            self.queue = asyncio.Queue()

            self.audioParams.get("SAMPLE_RATE")

            # Set audio parameters
            SAMPLE_RATE = self.audioParams.get("SAMPLE_RATE")
            FORMAT = self.audioParams.get("FORMAT")
            CHANNELS = self.audioParams.get("CHANNELS")
            BUFFER_DURATION_MS = self.audioParams.get("BUFFER_DURATION_MS")

            # Calculate the number of frames per buffer
            FRAMES_PER_BUFFER = int(SAMPLE_RATE * BUFFER_DURATION_MS / 1000)

            # Create a PyAudio object
            p = pyaudio.PyAudio()

            my_audio_callback = self.audio_callback
            if custAudioCallback is not None:
                my_audio_callback = custAudioCallback

            # Open the stream
            self.stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=FRAMES_PER_BUFFER,
                stream_callback=my_audio_callback,
            )

            self.stream.start_stream()

        return rtn




    def stopAudio(self):
        rtn = [True, "Stop Audio Successfully"]
        if self.isOpen == False:
            rtn[1] = "Audio is already on. No need to open it again"
        else:
            self.isOpen = False
            print(f"stream is going to close")
            if self.stream.is_active():
                self.stream.close()
            # self.queue.task_done()
        return rtn


myAudioServ = MyAudioService()

if __name__ == '__main__':
    print(myAudioServ.audioParams.get("SAMPLE_RATE"))