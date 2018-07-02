from aiohttp import web
from torrent_parser import parse_files
from threading import Thread
import string
import os
import signal
import shutil
import subprocess
import json
import sys
import re

max_storage_size = 450000000 #In bytes
aria2 = 'aria2c' #Executor command or path to programm
temp_path = 'temps' #Path to save temp files #MUST BE CREATED
path = 'downloads' #Path to save files #MUST BE CREATED

if not path in os.listdir(): os.mkdir(path)
if not temp_path in os.listdir(): os.mkdir(temp_path)

status = {}

def run_aria(torrent, ids, info_after):
    params = [aria2, torrent, '--seed-time=0', '--dir=' + temp_path, '--summary-interval=1', '--stderr']
    if ids: params.extend(['--select-file=' + ','.join(ids), '--bt-remove-unselected-file'])
    def run_(args, info):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        pid = str(process.pid)
        status[pid] = {}
        status[pid]['downloading'] = True
        prev = b''
        for i in process.stdout:
            try:
                if b'FILE:' == i[:5]:
                    fname = re.search(r'FILE: temps/(.*)\\n', str(i)).group(1)
                    if b'DL' in prev:
                        if b'ETA' in prev:
                            m = re.search(r'([0-9A-Za-z.]+)\/([0-9A-Za-z.]+)\(([0-9]+)\%\).*DL\:([0-9A-Za-z.]+) ETA:([a-z0-9]+)', str(prev))
                            status[pid]['file'] = {'name': fname, 'downloaded': m.group(1), 'size': m.group(2), 'percent': m.group(3), 'speed': m.group(4), 'lasts': m.group(5)}
                        else:
                            m = re.search(r'([0-9A-Za-z.]+)\/([0-9A-Za-z.]+)\(([0-9]+)\%\).*DL\:([0-9A-Za-z.]+)', str(prev))
                            status[pid]['file'] = {'name': fname, 'downloaded': m.group(1), 'size': m.group(2), 'percent': m.group(3), 'speed': m.group(4)}
                    else:
                        status[pid]['file'] = {'name': fname}
                else:
                    prev = i
            except:
                pass
        status[pid]['downloading'] = False
        status[pid]['errors'] = []
        if not process.stderr:
            for f in info['files']:
                try:
                    os.rename(os.path.join(temp_path, f), os.path.join(path, f))
                except FileExistsError:
                    os.remove(os.path.join(temp_path, f))
                    status[pid]['errors'].append('File was already downloaded')
                except FileNotFoundError:
                    status[pid]['errors'].append('File was removed')
        else:
            status[pid]['errors'].append('Was error while downloading!!! Try to clear cache after all downloads')
            for f in info['files']:
                try:
                    os.remove(os.path.join(temp_path, f))
                except:
                    pass     
        try:
            os.remove(info['torrent'])
        except:
            pass
    Thread(target=run_, args=(params, info_after)).start()

def get_all_files(path_):
    for i in os.walk(path_):
        for f in i[2]:
            yield os.path.join(i[0], f)

def get_path_size(path_):
    return sum(os.path.getsize(os.path.join(path_, f)) for f in os.listdir(path_) if os.path.isfile(os.path.join(path_, f))) + sum(get_path_size(os.path.join(path_, f)) for f in os.listdir(path_) if os.path.isdir(os.path.join(path_, f)))

def is_enough(size):
    return size + get_path_size(path) + get_path_size(temp_path) < max_storage_size

routes = web.RouteTableDef()

@routes.get('/')
async def hello(request):
    return web.Response(text='Go away')

@routes.post('/save')
async def save(request):
    post = await request.post()
    if 'torrent' in post:
        file = post['torrent'].file.read()
        cont = parse_files(file.decode('UTF-8', 'ignore'))
        if cont:
            nums = None
            if 'id' in request.query and 'files' in cont:
                ids = request.query['id'].split(',')
                size = 0
                nums = []
                urls = []
                files = []
                for i in ids:
                    if i in string.digits and int(i) > 0 and int(i) <= len(cont['files']):
                        this = cont['files'][int(i) - 1]
                        size += this['size']
                        files.append(os.path.join(cont['folder'], this['file']))
                        urls.append(request.host + '/download/' + cont['folder'] + '/' + this['file'])
                        nums.append(i)
            elif 'files' in cont:
                size = cont['size']
                urls = [request.host + '/download/' + cont['folder'] + '/' + i['file'] for i in cont['files']]
                files = [os.path.join(cont['folder'], i['file']) for i in cont['files']]
            else:
                size = cont['size']
                urls = [request.host + '/download/' + cont['file']]
                files = [cont['file']]
            if is_enough(size):
                torrent = os.path.join(temp_path, post['torrent'].filename)
                f = open(torrent, 'wb')
                f.write(file)
                f.close()
                info_after = {'files': files, 'torrent': torrent, 'url': urls}
                if 'folder' in cont:
                      info_after['folder'] = cont['folder']
                if 'uri' in request.query:
                      info_after['uri'] = request.query['uri']
                run_aria(torrent, nums, info_after)
                return web.json_response({'ok': True, 'urls': urls, 'size': size, 'files': files})
            else:
                return web.json_response({'ok': False, 'error': 'Is not enough memory'})  
    return web.json_response({'ok': False, 'error': 'Something wrong with torrent'})

@routes.get('/download/{path:.*}')
async def download(request):
    path_ = os.path.join(path, request.match_info.get('path'))
    if os.path.isfile(path_):
        return web.FileResponse(path_)
    else:
        return web.Response(status=404)

@routes.get('/status')
async def stats(request):
    st = dict(status)
    for i in [i for i in status if not status[i]['downloading']]: del status[i]
    return web.json_response(st)

@routes.get('/clear')
async def clear(request):
    if 'ok' in request.query and request.query['ok'] == 'ok':
        try:
            shutil.rmtree(temp_path)
            os.mkdir(temp_path)
            return web.json_response({'ok': True})
        except:
            if not temp_path in os.listdir():
                os.mkdir(temp_path)
            return web.json_response({'ok': False})
    else:
        return web.json_response({'ok': False, 'error': 'You are not sure?'})
    
@routes.get('/delete/{path:.*}')
async def dele(request):
    if 'ok' in request.query and request.query['ok'] == 'ok':
        path_ = os.path.join(path, request.match_info.get('path'))
        space_dir = len(path) + 1
        if os.path.isfile(path_) and path_ in [f for f in get_all_files(path)]:
              os.remove(path_)
              return web.json_response({'ok': True})
        else:
              return web.json_response({'ok': False, 'error': 'There is no file'})
    else:
        return web.json_response({'ok': False, 'error': 'You are not sure?'})

@routes.get('/files')
async def files(request):
    space_dir = len(path) + 1
    return web.json_response({'files': [{'url': request.host + '/download/' + f[space_dir:], 'path': f[space_dir:], 'delete': request.host + '/delete/' + f[space_dir:] + '?ok=ok'} for f in get_all_files(path)]})  

@routes.get('/storage')
async def mem(request):
    temp_s = get_path_size(temp_path)
    path_s = get_path_size(path)
    return web.json_response({'max': max_storage_size, 'now': temp_s + path_s, 'left': max_storage_size - (temp_s + path_s), 'temp_path': temp_s, 'download_path': path_s})

@routes.post('/content')
async def get_content(request):
    post = await request.post()
    if 'torrent' in post:
        cont = parse_files(post['torrent'].file.read().decode('UTF-8', 'ignore'))
        if cont:
            return web.json_response(cont)
    return web.json_response({'ok': False, 'error': 'Something wrong with torrent'})

@routes.get('/kill')
async def clear(request):
    if 'ok' in request.query and request.query['ok'] == 'ok':
        if 'pid' in request.query:
            for pd in request.query['pid'].split(','):
                if pd in status and status[pd]['downloading']:
                    os.kill(int(pd), signal.SIGTERM)
        else:
            for pd in status:
                os.kill(int(pd), signal.SIGTERM)
        return web.json_response({'ok': True})
    else:
        return web.json_response({'ok': False, 'error': 'You are not sure?'})

async def web_app():
    app = web.Application()
    app.add_routes(routes)
    return app

if __name__ == '__main__':
    app = web_app()
    web.run_app(app)
