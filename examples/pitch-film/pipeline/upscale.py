import torch, numpy as np, subprocess, sys, time
from srvgg import load
torch.set_num_threads(4)
m=load(0.6).to(memory_format=torch.channels_last)
import torch.nn.functional as F
for name in sys.argv[1:]:
    W,H=848,478
    dec=subprocess.Popen(['ffmpeg','-v','error','-i',f'plate{name}_src.mkv','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-c:v','libx264','-preset','medium','-crf','8','-pix_fmt','yuv444p',f'plate{name}_up.mkv'],stdin=subprocess.PIPE)
    i=0; t0=time.time()
    while True:
        buf=dec.stdout.read(W*H*3)
        if len(buf)<W*H*3: break
        x=torch.frombuffer(bytearray(buf),dtype=torch.uint8).view(H,W,3).permute(2,0,1).float().div(255)[None].contiguous(memory_format=torch.channels_last)
        with torch.inference_mode(), torch.autocast('cpu',dtype=torch.bfloat16):
            y=m(x).float()
        y=F.interpolate(y,size=(1082,1920),mode='bicubic',antialias=True,align_corners=False)[:,:,1:1081]
        enc.stdin.write((y[0].clamp(0,1).permute(1,2,0).mul(255).round().byte().contiguous().numpy()).tobytes())
        i+=1
        if i%100==0: print(name,i,f'{(time.time()-t0)/i:.2f}s/f',flush=True)
    enc.stdin.close(); enc.wait(); print(name,'done',i,flush=True)
