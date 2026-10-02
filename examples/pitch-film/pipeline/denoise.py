import torch, numpy as np, subprocess, soundfile as sf
from df.enhance import init_df, enhance
torch.set_num_threads(2)
model, st, _ = init_df(model_base_dir="models/DeepFilterNet3", post_filter=False, log_level="error")
sr = st.sr()
for n in "AB":
    d = subprocess.run(['ffmpeg','-v','error','-i',f'audio/{n}_raw.wav','-ar',str(sr),'-ac','1','-f','f32le','-'],capture_output=True).stdout
    x = torch.from_numpy(np.frombuffer(d,np.float32).copy())[None]
    # atten_lim_db keeps some room tone -> natural, not "underwater"
    y = enhance(model, st, x, atten_lim_db=18)
    sf.write(f'audio/{n}_df.wav', y[0].numpy(), sr, subtype='PCM_24'); print(n, 'ok', sr)
