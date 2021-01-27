"""
Start an acquisition of chunks of videos using a state file.

By default the output video last 3000 frames and are saved in the current
working directory.

Author: Romain Fayat, January 2021
Video Writer adapted from campy: https://github.com/ksseverson57/campy
"""
from imageio_ffmpeg import write_frames
import argparse
import ctypes as C
import tisgrabber as IC
from IC_trigger.camera import Camera
from pathlib import Path
import time
import collections

# Argument parsing
parser = argparse.ArgumentParser(__doc__)
parser.add_argument("state_file_path",
                    help="Path to the state file of the camera")
parser.add_argument("-o", "--output",
                    help="Path to the output video folder.",
                    dest="path_video_folder", default=".")
parser.add_argument("-f", "--frameRate",
                    help="Frequency to use for the output video (default: use the camera's properties).",
                    type=float, default=None, dest="framerate")

args = parser.parse_args()

state_file_path = args.state_file_path
framerate = args.framerate

path_video_folder = Path(args.path_video_folder).absolute()

timestamps = []
timestamps_file_path = path_video_folder.joinpath(".timestamps")


def OpenWriter(size, # (W, H)
        framerate, framenumber=0,
        path_video_folder=Path("."),
        ext='.mp4',
        codec='hevc_nvenc',
        loglevel='quiet', # 'warning', 'quiet', 'info'
        pix_fmt_in="gray",
        pix_fmt_out='rgb0',  # 'rgb0' (fastest), 'yuv420p'(slower), 'bgr0' (slower)
        ):
    """Open a ffmpeg video writer with custom parameters

    Adapted from https://github.com/ksseverson57/campy
    """
    path_video = path_video_folder.joinpath(f"{framenumber:06d}{ext}")

    writer = write_frames(
                str(path_video),
                size,
                fps=framerate,
                quality=None,
                codec=codec,  # H.265 hardware accel'd (GPU) 'hevc_nvenc'; H.264 'h264_nvenc'
                pix_fmt_in=pix_fmt_in, # 'bayer_bggr8', 'gray', 'rgb24', 'bgr0', 'yuv420p'
                pix_fmt_out=pix_fmt_out, # 'rgb0' (fastest), 'yuv420p'(slower), 'bgr0' (slower)
                bitrate=None,
                ffmpeg_log_level=loglevel, # 'warning', 'quiet', 'info'
                input_params=['-an'], # '-an' no audio
                macro_block_size=8,
                output_params=[
                    '-preset', 'fast', # set to 'fast', 'llhp', or 'llhq' for h264 or hevc
                    '-qp', "19",  # To be adjusted
                    '-bf:v', "0",
                    "-r:v", str(framerate),
                    '-vsync', '0',
                    '-2pass', '0',
                    '-gpu', "0",
                    ],
                )
    writer.send(None) # Initialize the generator
    print("+++++++++++++ NEW VIDEO +++++++++++++")

    return writer


def loop(pData):
    "Check if a frame needs to be written and write it"
    while True:
        if len(pData.write_queue) > 0:
            # Grab the frame to write and remove it from the queue
            cvMat = pData.write_queue.popleft()
            # Write the image to the video
            pData.video.send(cvMat)
            pData.written_counter += 1
            print(" " * 20 + f"Wrote frame {pData.written_counter:06d} to disk")
        else:
            time.sleep(1e-4)


class CallbackUserdata(C.Structure):
    "Pass user data to the callback function."

    def __init__(self, camera, video):
        self.camera = camera  # Reference to the camera object
        self.video = video  # Reference to the video objects
        self.write_queue = collections.deque([])
        self.queue_counter = -1
        self.written_counter = -1

def Callback(hGrabber, pBuffer, framenumber, pData: CallbackUserdata):
    """Save the last camera frame to the video

    :param: hGrabber: Real pointer to the grabber object. Do not use.
    :param: pBuffer : Pointer to the first pixel's first byte
    :param: framenumber : Number of the frame since the stream started
    :param: pData : Pointer to additional user data structure
    """
    # Write the current time to the timestamps list
    timestamps.append(time.time())

    # Increment the frame queue_counter and preallocate frame duplication variables
    pData.queue_counter += 1

    # Grab the frame
    cvMat = pData.camera.GetImageEx()

    pData.write_queue.append(cvMat)
    print(f"Frame number {pData.queue_counter:06d} sent to queue")


if __name__ == "__main__":
    # Initiate the camera
    cam = Camera.from_file(state_file_path)
    cam.SetContinuousMode(0)  # Handle each incoming frame automatically

    # Initiate the video using the camera's properties
    width = cam.get_video_format_width()
    height = cam.get_video_format_height()
    # Grab the framerate from the camera properties if it was not provided
    if framerate is None:
        framerate = cam.GetFrameRate()

    # Set the callback function
    Callbackfunc = IC.TIS_GrabberDLL.FRAMEREADYCALLBACK(Callback)
    video = OpenWriter((width, height), framerate,
                     framenumber=0,
                     path_video_folder=path_video_folder)
    Userdata = CallbackUserdata(camera=cam, video=video)
    cam.SetFrameReadyCallback(Callbackfunc, Userdata)

    try:
        # Start the camera
        print("Ctrl-C to interrupt")
        cam.StartLive(0)
        loop(Userdata)
    except KeyboardInterrupt:
        print("Interrupted by the user")
    finally:
        cam.StopLive()
        Userdata.video.close()
        # Write the timestamp of each frame
        with timestamps_file_path.open("w") as f:
            f.writelines([str(i) + "\n" for i in timestamps])
