"""
Start a video acquisition using a state file.

By default the output video is saved as test.avi in the current working
directory.

Author: Romain Fayat, November 2020
"""
import cv2
import argparse
import ctypes as C
import tisgrabber as IC
from IC_trigger.camera import Camera
from IC_trigger.video import Video


# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("pathCamParam",
                    help="Path to the state file of the camera")
parser.add_argument("-o", "--output",
                    help="Path to the output video file.",
                    dest="pathVideo", default="test.avi")
parser.add_argument("-L", "--live", const=1, default=0,
                    dest="showLive", action="store_const",
                    help="Show the live video.")
args = parser.parse_args()

pathCamParam = args.pathCamParam
pathVideo = args.pathVideo
showLive = args.showLive


def loop():
    "Wait for any user interaction with the preview window"
    while True:
        cv2.waitKey(1)


class CallbackUserdata(C.Structure):
    "Pass user data to the callback function."

    def __init__(self, camera, video):
        self.camera = camera  # Reference to the camera object
        self.video = video  # Reference to the video object


def Callback(hGrabber, pBuffer, framenumber, pData: CallbackUserdata):
    """Save the last camera frame to the video

    :param: hGrabber: Real pointer to the grabber object. Do not use.
    :param: pBuffer : Pointer to the first pixel's first byte
    :param: framenumber : Number of the frame since the stream started
    :param: pData : Pointer to additional user data structure
    """
    print(f"Callback called frame: {framenumber}")
    # Get the used image from our camera object
    cvMat = pData.camera.GetImageEx()
    cvMat = cv2.flip(cvMat, 0)

    # Write the image to the video
    pData.video.write(cvMat)


if __name__ == "__main__":
    # Initiate the camera
    cam = Camera.from_file(pathCamParam)
    cam.SetContinuousMode(0)  # Handle each incoming frame automatically

    # Initiate the video using the camera's properties
    width = cam.get_video_format_width()
    height = cam.get_video_format_height()
    framerate = cam.GetFrameRate()
    vid = Video(pathVideo, framerate, width, height)

    # Set the callback function
    Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(Callback)
    Userdata = CallbackUserdata(camera=cam, video=vid)
    cam.SetFrameReadyCallback(Callbackfunc, Userdata)

    try:
        # Start the camera
        print("Ctrl-C to interrupt")
        cam.StartLive(showLive)
        loop()
    except KeyboardInterrupt:
        print("Interrupted by the user")
    finally:
        cam.StopLive()
        vid.release()
