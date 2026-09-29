import sherpa_onnx, wave, numpy as np, json
P="models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/"
par=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=P+"encoder.int8.onnx",decoder=P+"decoder.int8.onnx",joiner=P+"joiner.int8.onnx",tokens=P+"tokens.txt",model_type="nemo_transducer",num_threads=4)
def load(f):
    w=wave.open(f); return np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768
res={}
for f,chunks in [("A",[(8.6,38.4),(38.4,70.0)]),("B",[(0,24.43)])]:
    x=load(f+".16k.wav"); allw=[]
    for a,b in chunks:
        s=par.create_stream(); s.accept_waveform(16000,x[int(a*16000):int(b*16000)]); par.decode_stream(s)
        r=s.result; words=[]
        for t,ts in zip(r.tokens,r.timestamps):
            if t.startswith(" ") or not words: words.append([t.strip(),a+ts])
            else: words[-1][0]+=t
        allw+= [{"w":w,"t":round(t,2)} for w,t in words]
        print(f,a,b,r.text)
    res[f]=allw
json.dump(res,open("words.json","w"),indent=1)
for f in res: print(f, " ".join(f"{w['w']}@{w['t']}" for w in res[f]))
