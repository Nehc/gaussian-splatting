import cv2, numpy as np
from tqdm import tqdm

def split_video(v_fname, out_dir, n_frame=None, video_name="IMG.MOV"):
    vidcap = cv2.VideoCapture(v_fname)
    success,image = vidcap.read()

    est_tot_frames = vidcap.get(cv2.CAP_PROP_FRAME_COUNT)

    if not n_frame:
        fps = vidcap.get(cv2.CAP_PROP_FPS)
        n = fps // 5
    else: n = n_frame 

    if est_tot_frames // n > 570:
        if n_frame: print("To many frames!")
        n = est_tot_frames // 500
        print(f"Set N to optimal: {n}...")

    desired_frames = np.arange(0, est_tot_frames, n)

    print(f"Convert video to {est_tot_frames // n} files...")

    for i in tqdm(desired_frames):
        vidcap.set(1,i-1)                      
        success,image = vidcap.read(1) 
        frameId = vidcap.get(1)   
        video_name = video_name.replace('.'+video_name.split('.')[-1],'')
        cv2.imwrite(f"{out_dir}/{video_name}-{frameId}.jpg", image)
        
    #vidcap.release()

    print("Done.")