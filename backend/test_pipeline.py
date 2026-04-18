import requests, time, glob, os
videos = glob.glob('uploads/*.mp4')
v = videos[-1]
filename = os.path.basename(v)
with open(v, 'rb') as f:
    r = requests.post('http://127.0.0.1:8000/api/upload', files={'file': (filename, f, 'video/mp4')})
job_id = r.json()['job_id']
print('job_id:', job_id)
for i in range(40):
    time.sleep(3)
    s = requests.get(f'http://127.0.0.1:8000/api/status/{job_id}').json()
    err = str(s.get('error') or '')[:150]
    trace = str(s.get('trace') or '')[-300:]
    print(i*3, s.get('status'), s.get('step'), err)
    if s.get('status') in ('done', 'failed'):
        print('TRACE:', trace)
        break
