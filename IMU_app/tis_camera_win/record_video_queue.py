"""
Start a video acquisition using a state file.

By default the output video is saved as 0.avi in the current working directory.
directory.

Author: Romain Fayat, November 2020
"""
import cv2
import argparse
import ctypes as C
import tisgrabber as IC
from IC_trigger.camera import Camera
from IC_trigger.video import Video
from pathlib import Path
import time
import collections

# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("pathCamParam",
                    help="Path to the state file of the camera")
parser.add_argument("-o", "--output",
                    help="Path to the output video folder.",
                    dest="pathVideoFolder", default=".")
parser.add_argument("-L", "--live", const=1, default=0,
                    dest="showLive", action="store_const",
                    help="Show the live video.")
parser.add_argument("-W", "--writeText", const=True, default=False,
                    dest="writeText", action="store_const",
                    help="Write information about the frame on each of them.")
parser.add_argument("-f", "--frameRate",
                    help="Frequency to use for the output video (default: use the camera's properties).",
                    type=float, default=None, dest="videoFrameRate")

args = parser.parse_args()

pathCamParam = args.pathCamParam
showLive = args.showLive
writeText = args.writeText
videoFrameRate = args.videoFrameRate

pathVideoFolder = Path(args.pathVideoFolder).absolute()
pathVideo = pathVideoFolder.joinpath(f"{0:06d}.avi")

timestamps = []
timestamps_file_path = pathVideoFolder.joinpath(".timestamps")

def loop(pData):
    "Check if a frame needs to be written and write it"
    while True:
        if len(pData.write_queue) > 0:
            # Grab the frame to write and remove it from the queue
            cvMat = pData.write_queue.popleft()
            # Write the image to the video
            pData.video.write(cvMat)
            pData.written_counter += 1
            print(" " * 20 + f"Wrote frame {pData.written_counter:06d} to disk")
        else:
            time.sleep(1e-4)



class CallbackUserdata(C.Structure):
    "Pass user data to the callback function."

    def __init__(self, camera, video):
        self.camera = camera  # Reference to the camera object
        self.video = video  # Reference to the video object
        self.write_queue = collections.deque([])
        self.queue_counter = -1
        self.written_counter = -1

def write_text_on_frame(frame, frame_number, is_duplicated=False):
    "Write additional information (frame #...) on a frame"
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_to_add = f"Frame: {frame_number:06d}"
    # Write if the frame was originally not captured and is just a placeholder
    if is_duplicated:
        text_to_add += "*"

    # Add the text to the frame
    cv2.putText(frame, text_to_add,
                (50, 50), font, 1,
                (0, 255, 255), 2, cv2.LINE_4)
    return frame


def Callback(hGrabber, pBuffer, framenumber, pData: CallbackUserdata):
    """Save the last camera frame to the video

    :param: hGrabber: Real pointer to the grabber object. Do not use.
    :param: pBuffer : Pointer to the first pixel's first byte
    :param: framenumber : Number of the frame since the stream started
    :param: pData : Pointer to additional user data structure
    """
    timestamps.append(time.time())

    pData.queue_counter += 1
    cvMat = pData.camera.GetImageEx()
    cvMat = cv2.flip(cvMat, 0)

    if writeText:
        cvMat = write_text_on_frame(cvMat,
                                    frame_number=pData.queue_counter,
                                    is_duplicated=is_duplicated)

    # Send the frame to the queue
    pData.write_queue.append(cvMat)
    print(f"Frame number {pData.queue_counter:06d} sent to queue")



if __name__ == "__main__":
    # Initiate the camera
    cam = Camera.from_file(pathCamParam)
    cam.SetContinuousMode(0)  # Handle each incoming frame automatically

    # Initiate the video using the camera's properties
    width = cam.get_video_format_width()
    height = cam.get_video_format_height()
    # Grab the framerate from the camera properties if it was not provided
    if videoFrameRate is None:
        videoFrameRate = cam.GetFrameRate()

    vid = Video(str(pathVideo), videoFrameRate, width, height)

    # Set the callback function
    Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(Callback)
    Userdata = CallbackUserdata(camera=cam, video=vid)
    cam.SetFrameReadyCallback(Callbackfunc, Userdata)

    try:
        # Start the camera
        print("Ctrl-C to interrupt")
        cam.StartLive(showLive)
        loop(Userdata)
    except KeyboardInterrupt:
        print("Interrupted by the user")
    finally:
        cam.StopLive()
        vid.release()
        # Write the timestamp of each frame
        with timestamps_file_path.open("w") as f:
            f.writelines([str(i) + "\n" for i in timestamps])
