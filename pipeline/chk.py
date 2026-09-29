import sherpa_onnx, numpy as np, subprocess, sys
P="models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8/"
par=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=P+"encoder.int8.onnx",decoder=P+"decoder.int8.onnx",joiner=P+"joiner.int8.onnx",tokens=P+"tokens.txt",model_type="nemo_transducer",num_threads=2)
for f in sys.argv[1:]:
    x=np.frombuffer(subprocess.run(['ffmpeg','-v','error','-i',f,'-ac','1','-ar','16000','-f','f32le','-'],capture_output=True).stdout,np.float32)
    txt=[]
    for a in range(0,len(x),16000*28):
        s=par.create_stream(); s.accept_waveform(16000,x[a:a+16000*28]); par.decode_stream(s); txt.append(s.result.text)
    print(f,':',' | '.join(txt))
