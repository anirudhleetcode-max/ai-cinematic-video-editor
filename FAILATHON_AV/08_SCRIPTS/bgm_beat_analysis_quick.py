import sys, librosa, numpy as np, csv
y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
dur = len(y)/sr
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time', tightness=100)
tempo=float(np.atleast_1d(tempo)[0])
oenv = librosa.onset.onset_strength(y=y, sr=sr)
onsets = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, units='time', backtrack=False)
# energy (RMS) per 0.5s window
hop=512; rms = librosa.feature.rms(y=y, hop_length=hop)[0]; t = librosa.times_like(rms, sr=sr, hop_length=hop)
# low-band (kick/bass) energy
S = np.abs(librosa.stft(y, hop_length=hop)); f = librosa.fft_frequencies(sr=sr)
low = S[f<150].sum(0); low/=low.max()
win = int(sr/hop*1.0)
sm = np.convolve(rms, np.ones(win)/win, 'same'); smn = sm/sm.max()
# segment boundaries
bounds = librosa.segment.agglomerative(librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop), 8)
btimes = librosa.frames_to_time(bounds, sr=sr, hop_length=hop)
# strongest onset impacts
oi = librosa.onset.onset_detect(onset_envelope=oenv, sr=sr, units='frames')
strength = oenv[oi]; top = oi[np.argsort(strength)[-15:]]
impacts = sorted(librosa.frames_to_time(top, sr=sr))
# energy jumps (drops): largest positive change of smoothed energy over 1s
d = smn[win:] - smn[:-win]; jumps=[]
for i in np.argsort(d)[::-1]:
    tt=t[i+win//2]
    if all(abs(tt-j)>4 for j in jumps): jumps.append(tt)
    if len(jumps)==5: break
print(f"duration={dur:.3f}s tempo={tempo:.2f}BPM beats={len(beats)} onsets={len(onsets)}")
print("first beats:", np.round(beats[:8],3))
print("segments:", np.round(btimes,2))
print("energy jumps (drop candidates):", np.round(sorted(jumps),2))
print("top impacts:", np.round(impacts,2))
print("energy per 2s:", " ".join(f"{i*2}:{smn[np.searchsorted(t,i*2)]:.2f}" for i in range(int(dur//2))))
# silence
quiet = t[smn<0.08]; print("quiet regions start/end:", np.round(quiet[:1],2), np.round(quiet[-1:],2) if len(quiet) else None)
with open(sys.argv[2],'w',newline='') as fh:
    w=csv.writer(fh); w.writerow(['time_s','type','beat_index','bar','beat_in_bar','energy','low_energy'])
    for k,b in enumerate(beats):
        i=np.searchsorted(t,b); i=min(i,len(t)-1)
        w.writerow([f"{b:.3f}",'downbeat' if k%4==0 else 'beat',k,k//4+1,k%4+1,f"{smn[i]:.3f}",f"{low[i]:.3f}"])
    for s in btimes: w.writerow([f"{s:.3f}",'section_boundary','','','','',''])
    for s in sorted(jumps): w.writerow([f"{s:.3f}",'energy_jump_drop_candidate','','','','',''])
    for s in impacts: w.writerow([f"{s:.3f}",'impact','','','','',''])
