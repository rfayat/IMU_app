"""
Start an acquisition of chunks of videos using a state file.

By default the output video last 3000 frames and are saved in the current
working directory.

Author: Romain Fayat, January 2021
"""
import cv2
import argparse
import ctypes as C
import tisgrabber as IC
from IC_trigger.camera import Camera
from IC_trigger.video import Video
from dotenv_connector import DotEnvConnector
from pathlib import Path
import time

# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("pathCamParam",
                    help="Path to the state file of the camera")
parser.add_argument("-n", "--nframes", type=int, default=3000,
                    help="Number of frames per video chunk",
                    dest="nframes_per_chunk")
parser.add_argument("-o", "--output",
                    help="Path to the output video folder.",
                    dest="pathVideoFolder", default=".")
parser.add_argument("-L", "--live", const=1, default=0,
                    dest="showLive", action="store_const",
                    help="Show the live video.")
parser.add_argument("-W", "--writeText", const=True, default=False,
                    dest="writeText", action="store_const",
                    help="Write information about the frame on each of them.")
parser.add_argument("-a", "--autoCorrect", const=True, default=False,
                    help="Share the frame count across multiple cameras to make the synchronisation more robust",
                    dest="autoCorrect", action="store_const")
parser.add_argument("-f", "--frameRate",
                    help="Frequency to use for the output video (default: use the camera's properties).",
                    type=float, default=None, dest="videoFrameRate")

args = parser.parse_args()

nframes_per_chunk = args.nframes_per_chunk
pathCamParam = args.pathCamParam
showLive = args.showLive
writeText = args.writeText
autoCorrect = args.autoCorrect
videoFrameRate = args.videoFrameRate

pathVideoFolder = Path(args.pathVideoFolder).absolute()
pathVideo = pathVideoFolder.joinpath("000000.avi")

timestamps = []
timestamps_file_path = pathVideoFolder.joinpath(".timestamps")


if autoCorrect:
    # Create / Connect to the shared file
    shared_status_folder = pathVideoFolder.parent
    shared_status_path = shared_status_folder.joinpath(".current_frame")
    shared_status = DotEnvConnector(str(shared_status_path))
    # Initiate the ground truth frame count
    if "frame" not in shared_status:
        shared_status["frame"] = "0"

    # Create the log file and list for skipped frames
    duplicated_frames = []
    log_file_path = pathVideoFolder.joinpath(".missing_frames")

def loop():
    "Wait for any user interaction with the preview window"
    while True:
        cv2.waitKey(1)


class CallbackUserdata(C.Structure):
    "Pass user data to the callback function."

    def __init__(self, camera):
        self.camera = camera  # Reference to the camera object
        self.video = []  # Reference to the video objects
        self.counter = -1

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
    # Write the current time to the timestamps list
    timestamps.append(time.time())

    # Increment the frame counter and preallocate frame duplication variables
    pData.counter += 1
    n_frames_to_write = 1
    is_duplicated = False

    # Grab the frame
    cvMat = pData.camera.GetImageEx()
    cvMat = cv2.flip(cvMat, 0)

    # If we reached the end of a chunk, end the video and create a new one
    # WARNING: Potential issue if a frame is missed exactly at the boundary
    if pData.counter % nframes_per_chunk == 0:
        global vid
        print("+++++++++++++ NEW VIDEO +++++++++++++")
        if pData.counter != 0:
            pData.video[pData.counter // nframes_per_chunk - 1].release()
        time.sleep(1e-5)
        pathVideo = pathVideoFolder.joinpath(f"{pData.counter:06d}.avi")
        vid = Video(str(pathVideo), videoFrameRate, width, height)
        pData.video.append(vid)
        time.sleep(1e-3)

    if autoCorrect:
        # Grab the shared frame number to compare it to the frame counter
        try:
            shared_frame_number = int(shared_status.get("frame"))
        except TypeError:  # The shared frame number was being overwritten
            print("%%%%%%%% error reading the shared frame number %%%%%%%%")
            shared_frame_number = pData.counter

        # The camera is the first one to reach this frame number
        if shared_frame_number < pData.counter:
            shared_status["frame"] = str(pData.counter)
        # The camera is late vs. at least one of the others
        elif shared_frame_number > pData.counter:
            # Write the current frame twice
            is_duplicated = True
            n_frames_to_write += 1
            pData.counter += 1
            duplicated_frames.append(pData.counter)
            print(f"############### CORRECTION BY 1 FRAME ###############")

    if writeText:
        cvMat = write_text_on_frame(cvMat,
                                    frame_number=pData.counter,
                                    is_duplicated=is_duplicated)

    print(f"Frame number {pData.counter:06d}")
    # Duplicate the frame if needed
    for i in range(n_frames_to_write):
        # Write the image to the video
        pData.video[pData.counter // nframes_per_chunk].write(cvMat)



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


    # Set the callback function
    Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(Callback)
    Userdata = CallbackUserdata(camera=cam)
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
        # Write the timestamp of each frame
        with timestamps_file_path.open("w") as f:
            f.writelines([str(i) + "\n" for i in timestamps])
        # Write the duplicated frames
        if autoCorrect:
            with log_file_path.open("w") as f:
                f.writelines([str(i) + "\n" for i in duplicated_frames])
