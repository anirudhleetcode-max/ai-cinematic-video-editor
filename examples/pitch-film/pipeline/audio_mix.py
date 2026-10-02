import numpy as np, subprocess, soundfile as sf
SR=48000; T=87.4; N=int(T*SR); rng=np.random.default_rng(7)
def rd(f): return np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',f,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True).stdout,np.float32)
# ---- voice: A (0-60.2) + B (60.2-) with short fades, then processing chain in ffmpeg
A=rd('audio/A_df.wav'); B=rd('audio/B_df.wav'); v=np.zeros(N,np.float32)
def fade(x,a=0.02,b=0.08):
    x=x.copy(); na,nb=int(a*SR),int(b*SR); x[:na]*=np.linspace(0,1,na); x[-nb:]*=np.linspace(1,0,nb); return x
A=fade(A[:int(60.2*SR)]); B=fade(B); v[:len(A)]+=A; o=int(60.2*SR); v[o:o+len(B)]+=B[:N-o]
sf.write('audio/voice_raw.wav',v,SR,subtype='FLOAT')
chain="highpass=f=85,equalizer=f=250:t=q:w=1:g=-2.5,equalizer=f=3400:t=q:w=1.2:g=2.5,highshelf=f=9000:g=1.5,deesser=i=0.35,acompressor=threshold=-22dB:ratio=3:attack=6:release=120:makeup=3dB"
# two-pass loudnorm to -16 LUFS
m=subprocess.run(['ffmpeg','-hide_banner','-i','audio/voice_raw.wav','-af',chain+',loudnorm=I=-16:TP=-1.5:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True).stderr
import json,re; j=json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}',m).group(0))
ln=f"loudnorm=I=-16:TP=-1.5:LRA=8:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
subprocess.run(['ffmpeg','-v','error','-y','-i','audio/voice_raw.wav','-af',chain+','+ln,'-ar',str(SR),'audio/voice.wav'],check=True)
# ---- music: D-major ambient pads + soft pluck arps, sections follow the story
t=np.arange(N)/SR
def hz(n): return 440*2**((n-69)/12)
def pad(notes,a,b):
    out=np.zeros(N); s,e=int(a*SR),int(b*SR); tt=t[s:e]-a; L=e-s
    env=np.minimum(1,np.minimum(tt/1.5,(b-a-tt)/1.5)).clip(0)
    for n in notes:
        for d in (-0.07,0.07):
            f=hz(n+d)
            for k,amp in ((1,1),(2,.35),(3,.15),(4,.07)):
                out[s:e]+=amp*np.sin(2*np.pi*f*k*tt+rng.random()*6)/len(notes)
    out[s:e]*=env*(0.85+0.15*np.sin(2*np.pi*0.1*tt)); return out
prog=[((50,57,62,66,69,76),0,10),((47,54,59,62,66,71),9.8,19.5),((43,55,59,62,66,74),19.2,29),
      ((50,57,62,66,69,76),29,37.5),((43,55,59,62,67,71),37.3,45),((45,57,61,64,69,76),44.8,52.5),
      ((47,54,59,62,66,71),52.3,60.4),((43,55,59,62,66,74),60.2,68),((45,57,62,64,69,73),67.8,76),
      ((43,55,62,66,71,74),75.8,82),((50,57,62,66,69,74,78),81.8,87.4)]
mus=sum(pad(n,a,b) for n,a,b in prog)
# plucks (pentatonic, 88 bpm 8ths) from the solution onward, gentle density
pent=[62,64,66,69,71,74,76,78]; step=60/88/2; pl=np.zeros(N)
k=0; x=29.3
while x<84.5:
    if not (59.7<x<60.6) and rng.random()<(0.55 if x<72 else 0.75):
        n=pent[(k*3+ (k//4))%len(pent)]; s=int(x*SR); L=int(1.2*SR); tt=np.arange(L)/SR
        w=(np.sin(2*np.pi*hz(n)*tt)+0.3*np.sin(2*np.pi*hz(n)*2*tt))*np.exp(-tt*4.5)*np.minimum(1,tt*200)
        e=min(N,s+L); pl[s:e]+=w[:e-s]*0.22
    k+=1; x+=step
dl=int(step*3*SR); pl[dl:]+=0.35*pl[:-dl].copy()
mus=mus+pl
# low drone
mus+=0.12*np.sin(2*np.pi*hz(38)*t)*np.minimum(1,t/3)
# simple reverb: convolve with decaying noise
ir=rng.standard_normal(int(2.2*SR))*np.exp(-np.arange(int(2.2*SR))/SR*2.8); ir/=np.abs(ir).sum()/6
from numpy.fft import rfft,irfft
L2=1<<int(np.ceil(np.log2(N+len(ir)))); wet=irfft(rfft(mus,L2)*rfft(ir,L2),L2)[:N]
mus=0.6*mus+0.4*wet
mus*=np.clip(np.minimum(t/2.0,(T-t)/2.5),0,1)
mus/=np.abs(mus).max()
# ---- sfx
sfx=np.zeros(N)
def add(at,w,g):
    s=int(at*SR); e=min(N,s+len(w)); sfx[s:e]+=w[:e-s]*g
def whoosh(d=0.7):
    L=int(d*SR); n=rng.standard_normal(L); tt=np.arange(L)/L
    # sweep via one-pole lowpass with rising cutoff
    y=np.zeros(L); a=0
    for i in range(L):
        c=0.02+0.35*np.sin(np.pi*tt[i]); a+=c*(n[i]-a); y[i]=a
    return y*np.sin(np.pi*tt)**2
def tick():
    L=int(0.06*SR); tt=np.arange(L)/SR; return np.sin(2*np.pi*1800*tt)*np.exp(-tt*90)
def impact():
    L=int(1.6*SR); tt=np.arange(L)/SR; f=70*np.exp(-tt*1.5)+42
    return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-tt*2.6)
def chime():
    L=int(1.8*SR); tt=np.arange(L)/SR
    return sum(np.sin(2*np.pi*hz(n)*tt)*a for n,a in ((86,1),(93,.5),(98,.3)))*np.exp(-tt*3)*np.minimum(1,tt*300)
W=whoosh()
for at in (9.7,18.6,41.5,51.6,59.7,71.8,83.65): add(at,W,0.28)
for at in (13.5,14.25,15.35,20.15,22.08,23.2,25.45,60.75,62.25,65.5,67.3): add(at,tick(),0.05)
add(46.02,tick(),0.08)
add(28.3,whoosh(0.8)[::-1],0.2); add(29.0,impact(),0.5)
for at in (40.8,59.4,84.25): add(at,chime(),0.06)
# ---- mix with ducking (envelope follower on voice)
voice=rd('audio/voice.wav')[:N]; voice=np.pad(voice,(0,N-len(voice)))
env=np.abs(voice); k2=int(0.25*SR); env=np.convolve(env,np.ones(k2)/k2,'same'); env=env/env.max()
duck=1-0.62*np.clip(env*6,0,1)
music=mus*duck*10**(-8/20)
mix=voice+music+sfx*0.45
L=mix.copy(); R=mix.copy()
# small stereo width for music only
d=int(0.012*SR); R[d:]+= (music[:-d]-music[d:])*0 ; 
st=np.stack([voice+music*0.95+sfx*0.45, voice+np.concatenate([np.zeros(d),music[:-d]])*0.95+sfx*0.45],1)
st/=max(1,np.abs(st).max()/0.89)
sf.write('audio/mix.wav',st.astype(np.float32),SR,subtype='PCM_24')
sf.write('audio/music_stem.wav',music.astype(np.float32),SR,subtype='PCM_24'); sf.write('audio/sfx_stem.wav',sfx.astype(np.float32),SR,subtype='PCM_24')
print('ok')
