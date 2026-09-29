# Grade upscaled plates, matte with RVM (recurrent, temporally stable), write sharp/bg/fg plates.
import onnxruntime as ort, numpy as np, subprocess, sys
S=sys.argv[1]; OUT=sys.argv[2]
GRADE="curves=all='0/0.025 0.5/0.49 1/0.94',eq=contrast=1.05:saturation=1.06:gamma=0.98,colorbalance=rm=0.025:bm=-0.03:rh=0.01:bh=-0.02"
so=ort.SessionOptions(); so.intra_op_num_threads=4
s=ort.InferenceSession(f'{S}/models/rvm_resnet50_fp32.onnx',so,providers=['CPUExecutionProvider'])
W,H=1920,1080
dec=subprocess.Popen(f"ffmpeg -v error -i {S}/plateA_up.mkv -i {S}/plateB_up.mkv -filter_complex [0][1]concat=n=2:v=1,{GRADE} -f rawvideo -pix_fmt rgb24 -".split(),stdout=subprocess.PIPE)
enc=lambda args,pix: subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt',pix,'-s','1920x1080','-r','30','-i','-']+args,stdin=subprocess.PIPE)
sharp=enc(['-c:v','libx264','-crf','14','-preset','slow','-pix_fmt','yuv420p',f'{OUT}/plate.mp4'],'rgb24')
bg=enc(['-vf','gblur=sigma=20,eq=brightness=-0.02:saturation=0.9','-c:v','libx264','-crf','18','-preset','medium','-pix_fmt','yuv420p',f'{OUT}/plate_bg.mp4'],'rgb24')
fg=enc(['-c:v','prores_ks','-profile:v','4444','-pix_fmt','yuva444p10le',f'{OUT}/plate_fg.mov'],'rgba')
rec=[np.zeros([1,1,1,1],np.float32)]*4; dr=np.array([0.25],np.float32); i=0
while True:
    b=dec.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    img=np.frombuffer(b,np.uint8).reshape(H,W,3)
    if i==1806-1+1: rec=[np.zeros([1,1,1,1],np.float32)]*4  # reset state at take change
    src=(img.astype(np.float32)/255).transpose(2,0,1)[None]
    fgr,pha,*rec=s.run(None,{'src':src,'r1i':rec[0],'r2i':rec[1],'r3i':rec[2],'r4i':rec[3],'downsample_ratio':dr})
    a=np.clip((pha[0,0]-0.06)/0.9,0,1)            # slight choke kills the light halo
    f=fgr[0].transpose(1,2,0); o=src[0].transpose(1,2,0)
    m=(a>0.97)[...,None]; col=np.where(m,o,f)       # decontaminated colours on edges
    rgba=np.dstack([np.clip(col*255,0,255),a*255]).round().astype(np.uint8)
    sharp.stdin.write(img.tobytes()); bg.stdin.write(img.tobytes()); fg.stdin.write(rgba.tobytes())
    i+=1
    if i%200==0: print(i,flush=True)
for p in (sharp,bg,fg): p.stdin.close(); p.wait()
print('done',i)
