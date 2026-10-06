#!/usr/bin/env python3
"""Build the FAILATHON AV project inside DaVinci Resolve and export a genuine .drp.

Run AFTER failathon_autoedit.py (it reads 03_RESOLVE/edit_plan.json).

How to run (Resolve must be open; Resolve Studio or free 18+):
  * From a terminal:   python FAILATHON_AV_RESOLVE_SCRIPT.py  [--render]
    (Preferences > System > General > "External scripting using" = Local)
  * or copy this file to
      %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility\\
    and run it from Workspace > Scripts > Utility.

What it builds:
  bins     01_SOURCE / 02_AUDIO (BGM, SFX) / 03_SELECTS (graded shots) / 04_GRAPHICS (TITLES) /
           05_SFX / 06_TIMELINES / 07_EXPORTS
  timeline FAILATHON_MASTER   1080p30: V1 graded beat-cut shots (= the MP4), V3 titles,
                              A1 BGM, A2 SFX, markers on drops / downbeats / hits / titles
  timeline FAILATHON_SOURCE_CUT  same cut built from the untouched camera originals (for regrading)
  saves the project, exports 03_RESOLVE/FAILATHON_AV_FINAL.drp plus a versioned backup,
  re-imports the .drp as a scratch project to validate it, then deletes the scratch copy.
  --render also renders FAILATHON_AV_FINAL_RESOLVE.mp4 from the timeline.
"""
import json, os, sys, time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parent
PLAN = WS / '03_RESOLVE' / 'edit_plan.json'
PROJECT = 'FAILATHON_AV'


def get_resolve():
    try:
        return resolve  # noqa: F821  (defined when run from Resolve's Scripts menu)
    except NameError:
        pass
    mods = [os.environ.get('RESOLVE_SCRIPT_API', ''),
            os.path.expandvars(r'%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting'),
            '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting',
            '/opt/resolve/Developer/Scripting']
    for m in mods:
        if m and Path(m, 'Modules').exists():
            sys.path.append(str(Path(m, 'Modules')))
    if sys.platform == 'win32' and not os.environ.get('RESOLVE_SCRIPT_LIB'):
        lib = Path(os.environ.get('PROGRAMFILES', r'C:\Program Files'), 'Blackmagic Design', 'DaVinci Resolve', 'fusionscript.dll')
        if lib.exists():
            os.environ['RESOLVE_SCRIPT_LIB'] = str(lib)
    import DaVinciResolveScript as dvr
    r = dvr.scriptapp('Resolve')
    if not r:
        sys.exit('Could not connect to DaVinci Resolve. Is it running, with external scripting set to Local?')
    return r


def step(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)


def main():
    render = '--render' in sys.argv
    plan = json.loads(PLAN.read_text())
    fps = plan['fps']
    r = get_resolve()
    step(f"Connected to {r.GetProductName()} {r.GetVersionString()}")
    pm = r.GetProjectManager()

    name = PROJECT
    n = 1
    while not pm.CreateProject(name):
        n += 1
        name = f'{PROJECT}_v{n:02d}'
        if n > 50:
            sys.exit('could not create project')
    project = pm.GetCurrentProject()
    step(f'Project created: {name}')
    for k, v in {'timelineFrameRate': str(fps), 'timelinePlaybackFrameRate': str(fps),
                 'timelineResolutionWidth': str(plan['width']), 'timelineResolutionHeight': str(plan['height']),
                 'videoMonitorFormat': f"HD 1080p {fps}"}.items():
        project.SetSetting(k, v)

    mp = project.GetMediaPool()
    root = mp.GetRootFolder()
    bins = {}
    for b in ['01_SOURCE', '02_AUDIO', '03_SELECTS', '04_GRAPHICS', '05_SFX', '06_TIMELINES', '07_EXPORTS']:
        bins[b] = mp.AddSubFolder(root, b)
    bins['BGM'] = mp.AddSubFolder(bins['02_AUDIO'], 'BGM')
    bins['TITLES'] = mp.AddSubFolder(bins['04_GRAPHICS'], 'TITLES')

    def imp(folder, paths):
        mp.SetCurrentFolder(folder)
        uniq = list(dict.fromkeys(p for p in paths if Path(p).exists()))
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            print('  MISSING:', *missing[:10], sep='\n   ')
        items = mp.ImportMedia(uniq) or []
        by = {}
        for it in items:
            fp = it.GetClipProperty('File Path')
            by[os.path.normcase(os.path.abspath(fp))] = it
        return by

    key = lambda p: os.path.normcase(os.path.abspath(p))
    shots = imp(bins['03_SELECTS'], [s['file'] for s in plan['shots']])
    src = imp(bins['01_SOURCE'], sorted({s['source'] for s in plan['shots']}))
    bgm = imp(bins['BGM'], [plan['bgm']])
    titles = imp(bins['TITLES'], [t['file'] for t in plan['titles']])
    sfx = imp(bins['05_SFX'], sorted({e['file'] for e in plan['sfx']}))
    step(f'Imported {len(shots)} shots, {len(src)} source clips, {len(titles)} titles, {len(sfx)} SFX, BGM={bool(bgm)}')

    def build(tl_name, use_source):
        mp.SetCurrentFolder(bins['06_TIMELINES'])
        tl = mp.CreateEmptyTimeline(tl_name)
        project.SetCurrentTimeline(tl)
        while tl.GetTrackCount('video') < 5:
            tl.AddTrack('video')
        while tl.GetTrackCount('audio') < 4:
            tl.AddTrack('audio', 'stereo')
        for i, nm in enumerate(['V1 Main footage', 'V2 Secondary', 'V3 Graphics', 'V4 Titles', 'V5 Effects'], 1):
            tl.SetTrackName('video', i, nm)
        for i, nm in enumerate(['A1 BGM', 'A2 SFX', 'A3 Ambience', 'A4 Original audio'], 1):
            tl.SetTrackName('audio', i, nm)
        t0 = tl.GetStartFrame()
        rec = 0
        clips = []
        for s in plan['shots']:
            if use_source:
                it = src.get(key(s['source']))
                sfps = float(it.GetClipProperty('FPS') or fps) if it else fps
                a = 0 if s['source_kind'] == 'image' else int(round(s['source_in'] * sfps))
                b = a + (s['frames'] if s['source_kind'] == 'image' else max(1, int(round(min(s['source_len'], s['frames'] / fps) * sfps))))
            else:
                it = shots.get(key(s['file']))
                a, b = 0, s['frames']
            if it:
                clips.append({'mediaPoolItem': it, 'startFrame': a, 'endFrame': b - 1, 'trackIndex': 1,
                              'recordFrame': t0 + rec, 'mediaType': 1})
            rec += s['frames']
        placed = mp.AppendToTimeline(clips) or []
        b = next(iter(bgm.values()), None)
        if b:
            mp.AppendToTimeline([{'mediaPoolItem': b, 'startFrame': 0, 'endFrame': int(plan['duration'] * fps) - 1,
                                  'trackIndex': 1, 'recordFrame': t0, 'mediaType': 2}])
        for t in plan['titles']:
            it = titles.get(key(t['file']))
            if it:
                mp.AppendToTimeline([{'mediaPoolItem': it, 'startFrame': 0, 'endFrame': int(round(t['dur'] * fps)) - 1,
                                      'trackIndex': 4, 'recordFrame': t0 + int(round(t['at'] * fps)), 'mediaType': 1}])
        for e in plan['sfx']:
            it = sfx.get(key(e['file']))
            if it:
                ln = int(float(it.GetClipProperty('Frames') or fps))
                mp.AppendToTimeline([{'mediaPoolItem': it, 'startFrame': 0, 'endFrame': ln - 1, 'trackIndex': 2,
                                      'recordFrame': t0 + int(round(e['at'] * fps)), 'mediaType': 2}])
        # SFX gain (dB) where the API allows it
        for ti in tl.GetItemListInTrack('audio', 2) or []:
            try:
                ti.SetProperty('Volume', -9.0)
            except Exception:
                pass
        # markers
        f = lambda sec: int(round(sec * fps))
        for x in plan['drops']:
            tl.AddMarker(f(x), 'Red', 'DROP', 'Major energy jump: cut + flash + shake + impact SFX', 1)
        for x in plan['hits']:
            if all(abs(x - d) > 0.2 for d in plan['drops']):
                tl.AddMarker(f(x), 'Yellow', 'HIT', 'Strong percussive hit', 1)
        for t in plan['titles']:
            tl.AddMarker(f(t['at']) + 1, 'Blue', f"TITLE {t['text']}", t['name'], 1)
        prev = None
        rec = 0
        for s in plan['shots']:
            if s['section'] != prev:
                tl.AddMarker(rec + 2, 'Green', s['section'].upper(), 'Section start', 1)
                prev = s['section']
            rec += s['frames']
        for i, x in enumerate(plan['downbeats']):
            if i % 4 == 0:
                tl.AddMarker(f(x) + 3, 'Cyan', f'BAR {i + 1}', 'Phrase (4 bars)', 1)
        n_v1 = len(tl.GetItemListInTrack('video', 1) or [])
        step(f'{tl_name}: V1 {n_v1}/{len(plan["shots"])} clips, V4 {len(tl.GetItemListInTrack("video", 4) or [])} titles, '
             f'A1 {len(tl.GetItemListInTrack("audio", 1) or [])} BGM, A2 {len(tl.GetItemListInTrack("audio", 2) or [])} SFX')
        return tl, n_v1

    src_tl, _ = build('FAILATHON_SOURCE_CUT', True)
    master, n_v1 = build('FAILATHON_MASTER', False)
    project.SetCurrentTimeline(master)
    pm.SaveProject()
    step('Project saved')

    out_dir = WS / '03_RESOLVE'
    drp = out_dir / 'FAILATHON_AV_FINAL.drp'
    if drp.exists():
        drp.rename(WS / '10_BACKUPS' / f'FAILATHON_AV_FINAL_{datetime.now():%Y%m%d_%H%M%S}.drp')
    ok = pm.ExportProject(name, str(drp), True)
    step(f'ExportProject -> {drp} : {ok}')
    if ok:
        bk = WS / '10_BACKUPS' / f'FAILATHON_AV_v{datetime.now():%Y%m%d_%H%M%S}.drp'
        bk.write_bytes(drp.read_bytes())

    # validation: re-import the .drp as a scratch project and inspect it
    report = [f'# Resolve validation ({datetime.now():%Y-%m-%d %H:%M})', '',
              f'- Resolve: {r.GetProductName()} {r.GetVersionString()}', f'- Project: {name}',
              f'- .drp exported: {ok} ({drp.stat().st_size if drp.exists() else 0} bytes)']
    if ok:
        test = f'{name}_DRP_VALIDATE'
        if pm.ImportProject(str(drp), test):
            p2 = pm.LoadProject(test)
            tls = [p2.GetTimelineByIndex(i + 1).GetName() for i in range(p2.GetTimelineCount())]
            t = next((p2.GetTimelineByIndex(i + 1) for i in range(p2.GetTimelineCount())
                      if p2.GetTimelineByIndex(i + 1).GetName() == 'FAILATHON_MASTER'), None)
            v1 = len(t.GetItemListInTrack('video', 1) or []) if t else 0
            a1 = len(t.GetItemListInTrack('audio', 1) or []) if t else 0
            v4 = len(t.GetItemListInTrack('video', 4) or []) if t else 0
            offline = sum(1 for it in (t.GetItemListInTrack('video', 1) or []) if not it.GetMediaPoolItem()) if t else -1
            report += [f'- Re-imported as `{test}`: timelines {tls}',
                       f'- FAILATHON_MASTER: V1 {v1} clips, V4 {v4} titles, A1 {a1} BGM, items without media {offline}',
                       f'- Validation: **{"PASS" if t and v1 == len(plan["shots"]) and a1 == 1 else "CHECK"}**']
            pm.CloseProject(p2)
            pm.LoadProject(name)
            pm.DeleteProject(test)
        else:
            report.append('- Re-import of the .drp FAILED')
    if render:
        project = pm.GetCurrentProject()
        project.SetCurrentTimeline(master)
        project.SetCurrentRenderFormatAndCodec('mp4', 'H264')
        project.SetRenderSettings({'SelectAllFrames': True, 'TargetDir': str(WS / '07_EXPORTS'),
                                   'CustomName': 'FAILATHON_AV_FINAL_RESOLVE', 'FormatWidth': plan['width'],
                                   'FormatHeight': plan['height'], 'FrameRate': str(fps), 'AudioCodec': 'aac',
                                   'AudioBitDepth': 24, 'AudioSampleRate': 48000})
        job = project.AddRenderJob()
        project.StartRendering(job)
        step('Rendering from Resolve...')
        while project.IsRenderingInProgress():
            time.sleep(2)
        st = project.GetRenderJobStatus(job)
        report.append(f'- Resolve render: {st}')
        step(f'Render: {st}')
    (WS / '09_REPORTS' / 'RESOLVE_VALIDATION.md').write_text('\n'.join(report) + '\n')
    print('\n'.join(report))


if __name__ == '__main__':
    main()
