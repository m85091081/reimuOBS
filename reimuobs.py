import psutil
import os 
import time 
import subprocess
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import google.oauth2
import google
import json
import settings
import obsws_python as obs

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime,timedelta
from googleapiclient.http import MediaFileUpload
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from googleapiclient.errors import HttpError
from subprocess import DEVNULL


scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
api_service_name = "youtube"
api_version = "v3"
client_secrets_file = "client.json"
OBS = "obs"
PYTHON = "python.exe"
shoplist = settings.shopPlaylist
machinelist = settings.cabinetList
youtube = None
    
def gotyoutube():
    global youtube
    try:
        info = json.load(open('info.json'))
    except:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes)
        flow.run_local_server()
        creds = flow.credentials
        info = { 
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': creds.expiry.isoformat(),
        }
        with open('info.json', 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)

    creds = google.oauth2.credentials.Credentials( 
        token=info['token'],
        refresh_token=info['refresh_token'],
        token_uri=info['token_uri'],
        client_id=info['client_id'],
        client_secret=info['client_secret'],
        scopes=info['scopes'],
    )
                
    youtube = googleapiclient.discovery.build(api_service_name, api_version, credentials=creds)

    
def safexe(func):
    while 1 :
        try:
            resp = func.execute()
            break
        except HttpError as e:
            print('YouTube say HttpError')
            gotyoutube()
            time.sleep(10)
    return resp


def stoplBmaimai():
    global youtube
    gotyoutube()
    if settings.maiDXBool == True :
        print('[INFO] Stop 37656 maimaiDX liveBroadcasts')
        needrestartbrod = youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status",
            broadcastStatus="active",maxResults=50)   
        gotallbrod = safexe(needrestartbrod)
        needBrod = None
        for l in machinelist:
            if 'maimaiDX' in l['title']:
                try:
                    host = settings.host
                    cl = obs.ReqClient(host=host, port=l.p, timeout=5)
                    cl.stop_stream()
                except:
                    pass

        for brod in gotallbrod['items'] :
            if settings.shopStr + ' ' + 'maimaiDX' in brod['snippet']['title']:
                safexe(youtube.liveBroadcasts().transition(broadcastStatus="complete",id=brod['id'],part="snippet,status"))
    

def runkill():
    print('[INFO] Stop all liveBroadcasts and off OBS/ONE')
    killprocess()
    global youtube
    gotyoutube()
    needrestartbrod = youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status",
        broadcastStatus="active",maxResults=50)    
    gotallbrod = safexe(needrestartbrod)
    needBrod = None

    for x in machinelist:
        for brod in gotallbrod['items'] :
            if x['title'] in brod['snippet']['title'] and settings.shopStr in brod['snippet']['title']:
                safexe(youtube.liveBroadcasts().transition(broadcastStatus="complete",id=brod['id'],part="snippet,status"))

    for x in machinelist:
        request = safexe(youtube.playlistItems().list(
                part="snippet,contentDetails",
                maxResults=50,
                playlistId=x['l']
            ))
        responses = request['items']  
        for rsp in responses:
            safexe(youtube.playlistItems().delete(
                id=rsp['id']
            ))
    request = safexe(youtube.playlistItems().list(
            part="snippet,contentDetails",
            maxResults=50,
            playlistId=shoplist
        ))
    responses = request['items']  
    for rsp in responses:
        safexe(youtube.playlistItems().delete(
            id=rsp['id']
        ))
    

def killprocess():
    pidself = os.getpid()
   
    for proc in psutil.process_iter():
        try:
            if PYTHON in proc.name():
                if proc.pid != pidself:
                    try:
                        proc.kill()
                    except:
                        pass
        except:
            pass

    time.sleep(30)
    for proc in psutil.process_iter():
        try:
            if OBS in proc.name():
                try:
                    proc.kill()
                except:
                    pass
        except:
            pass

    for proc in psutil.process_iter():
        try:
            if OBS in proc.name():
                try:
                    proc.terminate()
                except:
                    pass
        except:
            pass
       
                    
def runstartBrod():
    print('[INFO] Start all liveBroadcasts')
    global youtube
    gotyoutube()
    current_time = datetime.now()
    next_time = current_time + timedelta(seconds=180)
    if current_time.hour > 12 :
        pt = '下半'
    else:
        pt = '上半'
    formatted_time = current_time.strftime('%m/%d') + pt
    for x in machinelist:
        brodgot = safexe(youtube.liveBroadcasts().insert(
            part="snippet,contentDetails,status",
            body={
                "contentDetails": {
                    "enableClosedCaptions": True,
                    "enableContentEncryption": True,
                    "enableDvr": True,
                    "enableEmbed": True,
                    "recordFromStart": True,
                    "startWithSlate": True,
                    "enableAutoStart": True,
                    "enableAutoStop": False
                    },
                "snippet": {
                    "title": '[X50MGS on-Air]['+formatted_time+']'+settings.shopStr+' '+ x['title'] + '直播',
                    "scheduledStartTime": next_time.astimezone().replace(microsecond=0).isoformat(),
                    "description": '地點(Location) : X50 Music Game Station (Taiwan, Taipei)\n時間(Time) : '+formatted_time+'\n\n請保持尊重友善包容\n\n要不然我會把你包起來',
                    },
                "status": {
                    "privacyStatus": "public"
                    }
                }
        ))
        request = youtube.liveBroadcasts().bind(
                id=brodgot['id'],
                part="snippet",
                streamId=x['key']
                )
        responses = safexe(request)
        safexe(youtube.thumbnails().set(
            videoId=responses['id'],
            media_body=MediaFileUpload(x['name']+".jpg")
            ))  
        safexe(youtube.playlistItems().insert(
                part="snippet",
                body={
                  "snippet": {
                    "playlistId": x['l'],
                    "position": 0,
                    "resourceId": {
                      "kind": "youtube#video",
                      "videoId": responses['id']
                    }
                  }
                }
            ))
        safexe(youtube.playlistItems().insert(
                part="snippet",
                body={
                  "snippet": {
                    "playlistId": shoplist,
                    "position": 0,
                    "resourceId": {
                      "kind": "youtube#video",
                      "videoId": responses['id']
                    }
                  }
                }
            )) 
        
    
def runstart():
    print('[INFO] Start all OBS+ONE')
    for batch in settings.startList:
        subprocess.Popen([batch+'.bat'],close_fds=True,shell=True,stdout=DEVNULL)
        time.sleep(10)


def run17():
    print('[INFO] REStart all LB / Restart streaming')
    killprocess()
    global youtube
    gotyoutube()
    needrestartbrod = youtube.liveBroadcasts().list(part="id,snippet,contentDetails,status",
        broadcastStatus="active",maxResults=50)    
    gotallbrod = safexe(needrestartbrod)
    needBrod = None
    for x in machinelist:
        for brod in gotallbrod['items'] :
            if x['title'] in brod['snippet']['title'] and settings.shopStr in brod['snippet']['title']:
                 safexe(youtube.liveBroadcasts().transition(broadcastStatus="complete",id=brod['id'],part="snippet,status"))
    runstartBrod()
    time.sleep(5)
    runstart()
    
    
def main():
    print('')
    print('[ReimuOBS] Startup... ver.1.1.5 ')
    executors = {
        "default": ThreadPoolExecutor(50),
    }
    job_stores = {
        'default': SQLAlchemyJobStore(url='sqlite:///sqlite.sqlite3'),
    }
    job_defaults = {'coalesce':True,'misfire_grace_time':None}
    scheduler = BackgroundScheduler(job_stores=job_stores,job_defaults=job_defaults,executors=executors)
    scheduler.start()
    print('[ReimuOBS] Automatic watchdog of OBS/ONEClick/YouTube Stream')
    print('[INFO] Worker is starting')
    
    triggerstoplBmaimai = CronTrigger(
        year="*", month="*", day="*", hour=settings.cronTrig[0][0], minute=settings.cronTrig[0][1], second=settings.cronTrig[0][2]
    )
    triggerStop = CronTrigger(
        year="*", month="*", day="*", hour=settings.cronTrig[1][0], minute=settings.cronTrig[1][1], second=settings.cronTrig[1][2]
    )
    triggerStart = CronTrigger(
        year="*", month="*", day="*", hour=settings.cronTrig[2][0], minute=settings.cronTrig[2][1], second=settings.cronTrig[2][2]
    )
    triggerStartBrod = CronTrigger(
        year="*", month="*", day="*", hour=settings.cronTrig[3][0], minute=settings.cronTrig[3][1], second=settings.cronTrig[3][2]
    )
    triggerRefresh = CronTrigger(
        year="*", month="*", day="*", hour=settings.cronTrig[4][0], minute=settings.cronTrig[4][1], second=settings.cronTrig[4][2]
    )

    scheduler.add_job(
        stoplBmaimai,
        trigger=triggerstoplBmaimai,
        args=[],
        name="dailystoplBmaimai",
    )
    scheduler.add_job(
        runkill,
        trigger=triggerStop,
        args=[],
        name="dailyStop",
    )
    scheduler.add_job(
        runstart,
        trigger=triggerStart,
        args=[],
        name="dailyStart",
    )
    scheduler.add_job(
        runstartBrod,
        trigger=triggerStartBrod,
        args=[],
        name="dailyStartBrod",
    )
    scheduler.add_job(
        run17,
        trigger=triggerRefresh,
        args=[],
        name="dailyRFBrod",
    )

    print('[INFO] Worker is ready')
    while True:
        time.sleep(5)


if __name__ == "__main__":
    gotyoutube()
    eval(settings.startup)
