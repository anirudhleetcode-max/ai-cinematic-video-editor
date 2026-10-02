import sherpa_onnx, wave, numpy as np, json, sys
M="models/"
def load(f):
    w=wave.open(f); a=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768; return a
vadc=sherpa_onnx.VadModelConfig(); vadc.silero_vad.model=M+"v.onnx"; vadc.silero_vad.min_silence_duration=0.35; vadc.silero_vad.min_speech_duration=0.2; vadc.silero_vad.max_speech_duration=20; vadc.sample_rate=16000
par=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=M+"sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/encoder.int8.onnx",decoder=M+"sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/decoder.int8.onnx",joiner=M+"sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/joiner.int8.onnx",tokens=M+"sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/tokens.txt",model_type="nemo_transducer",num_threads=4)
W=M+"sherpa-onnx-whisper-medium.en/"
wh=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=W+"medium.en-encoder.int8.onnx",decoder=W+"medium.en-decoder.int8.onnx",tokens=W+"medium.en-tokens.txt",num_threads=4)
for name in ["B","A"]:
    a=load(name+".16k.wav"); vad=sherpa_onnx.VoiceActivityDetector(vadc,buffer_size_in_seconds=120)
    segs=[]; i=0
    while i<len(a):
        vad.accept_waveform(a[i:i+512]); i+=512
        while not vad.empty(): segs.append((vad.front.start, np.array(vad.front.samples))); vad.pop()
    vad.flush()
    while not vad.empty(): segs.append((vad.front.start, np.array(vad.front.samples))); vad.pop()
    out=[]
    print("=====",name)
    for st,smp in segs:
        t0=st/16000
        r={}
        for tag,rec in [("parakeet",par),("whisper",wh)]:
            s=rec.create_stream(); s.accept_waveform(16000,smp); rec.decode_stream(s); r[tag]=s.result
        toks=[(t,t0+ts) for t,ts in zip(r["parakeet"].tokens,r["parakeet"].timestamps)]
        # merge tokens to words
        words=[]
        for t,ts in toks:
            if t.startswith(" ") or t.startswith("▁") or not words: words.append([t.strip(" ▁"),ts])
            else: words[-1][0]+=t
        seg={"start":round(t0,2),"end":round(t0+len(smp)/16000,2),"whisper":r["whisper"].text.strip(),"parakeet":r["parakeet"].text.strip(),"words":[{"w":w,"t":round(t,2)} for w,t in words]}
        out.append(seg)
        print(f"[{seg['start']:6.2f}-{seg['end']:6.2f}] W: {seg['whisper']}\n                P: {seg['parakeet']}")
    json.dump(out,open(name+".asr.json","w"),indent=1)
