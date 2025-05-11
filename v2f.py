from argparse import ArgumentParser
import cv2, numpy as np
from tqdm import tqdm
from pytube import YouTube

parser = ArgumentParser("Video to frames converter")
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--video_name", "-v", required=True, type=str)
parser.add_argument("--youtube", "-y", type=str)
parser.add_argument("--n_frame", "-n", type=int)
args = parser.parse_args()

v_fname = args.source_path + '/' + args.video_name

if args.youtube:
    yt = YouTube(args.youtube)
    video = yt.streams.get_highest_resolution()
    video.download(filename=v_fname)

vidcap = cv2.VideoCapture(v_fname)
success,image = vidcap.read()

est_tot_frames = vidcap.get(cv2.CAP_PROP_FRAME_COUNT)

if not args.n_frame:
    fps = vidcap.get(cv2.CAP_PROP_FPS)
    n = fps // 5
else: n = args.n_frame 

if est_tot_frames // n > 570:
    if args.n_frame: print("To many frames!")
    n = est_tot_frames // 500
    print(f"Set N to optimal: {n}...")

desired_frames = np.arange(0, est_tot_frames, n)

print(f"Convert video to {est_tot_frames // n} files...")

for i in tqdm(desired_frames):
    vidcap.set(1,i-1)                      
    success,image = vidcap.read(1) 
    frameId = vidcap.get(1)   
    video_name = args.video_name.replace('.'+args.video_name.split('.')[-1],'')
    cv2.imwrite(f"{args.source_path}/input/{video_name}-{frameId}.jpg", image)
    
vidcap.release()

print("Done.")