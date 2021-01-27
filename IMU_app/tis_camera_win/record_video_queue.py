"""
Start a video acquisition using a state file.

By default the output video is saved as 0.avi in the current working directory.
directory.

Author: Romain Fayat, January 2021
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

def loop(pData):
    "Handle frame writting and video creation"
    while True:
        if pData.has_frame_to_write():
            written_counter = pData.write_frame()
            print(" " * 20 + f"Wrote frame {written_counter:06d} to disk")
        else:
            time.sleep(1e-4)


class Callback_User_Data(C.Structure):
    "Object used to share data between the callback function and the main loop."

    def __init__(self, camera, video_properties, timeout):
        "Create the object and initialize its counters / lists"
        self.camera = camera  # Reference to the camera object
        self.video_properties = video_properties
        self.timeout = timeout
        self.write_queue = collections.deque([])
        self.timestamps = []
        self.queue_counter = -1
        self.written_counter = -1
        self.time_last_frame_written = None
        self.video_all = []
        # Create a new video for the first frame
        self.create_video(close_previous=False)

    def has_frame_to_write(self):
        "Return a boolean indicating if a frame is waiting to be written"
        return len(self.write_queue) > 0

    def write_frame(self):
        """Write the first frame of the queue to the video object.

        Return the total number of frames written since the stream started.
        """
        # Create a new video if the last frame was received more than timeout
        # seconds before (self.timeout_was_reached takes values False for the
        # first frame of the stream or if no timeout was provided).
        if self.timeout_was_reached():
            self.create_video()
        # Grab the frame to write and remove it from the queue
        frame = self.write_queue.popleft()
        # Write the image to the video
        self.video.write(frame)
        self.written_counter += 1
        self.time_last_frame_written = time.time()
        return self.written_counter

    def create_video(self, close_previous=True):
        """Create a new video named based on the frame counter

        If close_previous is set to True, close the video stored as self.video
        before creating a new one.
        """
        print("################## NEW VIDEO ##################")
        # Compute the path to the new video
        video_name = f"{self.written_counter + 1 :06d}.avi"
        path_video = video_properties["path_video_folder"].joinpath(video_name)

        # Create the video and store it as self.video
        framerate = video_properties["framerate"]
        width = video_properties["width"]
        height = video_properties["height"]

        if close_previous:
            self.video.release()
            time.sleep(1e-3)
        self.video_all.append(Video(str(path_video), framerate, width, height))
        time.sleep(1e-3)

    @property
    def video(self):
        "Grab the video being currently written"
        return self.video_all[-1]

    def timeout_was_reached(self):
        """Return True if the timeout was reached.

        In this case, a new video needs to be created.
        """
        # No timesout or first frame of the stream
        if self.timeout is None or self.time_last_frame_written is None:
            return False
        # Compare the elapsed time since the last frame and timeout
        time_since_last_frame = time.time() - self.time_last_frame_written
        return time_since_last_frame > self.timeout


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


def Callback(hGrabber, pBuffer, framenumber, pData: Callback_User_Data):
    """Save the last camera frame to the video

    :param: hGrabber: Real pointer to the grabber object. Do not use.
    :param: pBuffer : Pointer to the first pixel's first byte
    :param: framenumber : Number of the frame since the stream started
    :param: pData : Pointer to additional user data structure
    """
    pData.timestamps.append(time.time())

    pData.queue_counter += 1
    cvMat = pData.camera.GetImageEx()
    cvMat = cv2.flip(cvMat, 0)

    if write_text:
        cvMat = write_text_on_frame(cvMat,
                                    frame_number=pData.queue_counter,
                                    is_duplicated=is_duplicated)

    # Send the frame to the queue
    pData.write_queue.append(cvMat)
    print(f"Frame number {pData.queue_counter:06d} sent to queue")


# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("path_state_file",
                    help="Path to the state file of the camera")
parser.add_argument("-o", "--output",
                    help="Path to the output video folder.",
                    dest="path_video_folder", default=".")
parser.add_argument("-L", "--live", const=1, default=0,
                    dest="show_live", action="store_const",
                    help="Show the live video.")
parser.add_argument("-W", "--write_text", const=True, default=False,
                    dest="write_text", action="store_const",
                    help="Write information about the frame on each of them.")
parser.add_argument("-f", "--framerate",
                    help="Frequency to use for the output video (default: use the camera's properties).",
                    type=float, default=None, dest="framerate")
parser.add_argument("-t", "--timeout",
                    help="Delay spent waiting for a new frame before creating a new video in seconds (default: store the frames in one video).",  # noqa E501
                    type=float, default=None, dest="timeout")

args = parser.parse_args()
path_state_file = args.path_state_file
show_live = args.show_live
write_text = args.write_text
framerate = args.framerate
timeout = args.timeout
path_video_folder = Path(args.path_video_folder).absolute()

timestamps = []
timestamps_file_path = path_video_folder.joinpath(".timestamps")

if __name__ == "__main__":
    # Initiate the camera
    cam = Camera.from_file(path_state_file)
    cam.SetContinuousMode(0)  # Handle each incoming frame automatically

    #  Pass the video properties to user_data
    width = cam.get_video_format_width()
    height = cam.get_video_format_height()
    if framerate is None:  # framerate not provided
        # Use the camera properties in this case
        framerate = cam.GetFrameRate()
    video_properties = {"path_video_folder": path_video_folder,
                        "framerate": framerate,
                        "width": width,
                        "height": height}

    # Set the callback function
    Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(Callback)
    user_data = Callback_User_Data(camera=cam,
                                   video_properties=video_properties,
                                   timeout=timeout)
    cam.SetFrameReadyCallback(Callbackfunc, user_data)

    try:
        # Start the camera
        print("Ctrl-C to interrupt")
        cam.StartLive(show_live)
        loop(user_data)
    except KeyboardInterrupt:
        print("Interrupted by the user")
    finally:
        cam.StopLive()
        user_data.video.release()
        # Write the timestamp of each frame
        with timestamps_file_path.open("w") as f:
            f.writelines([str(i) + "\n" for i in user_data.timestamps])
