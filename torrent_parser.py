def get_info(l):
    def check(p):
        if p[0] in ty:
            return ty[p[0]](p[1:])
        else:
            return None
    def this(o):
        c = check(o)
        if c:
            return c
        n = ""
        i = 0
        try:
            while o[i] != ':':
                n += o[i]
                i += 1
        except IndexError:
            pass
        return o[i + 1 :int(n) + i + 1], o[int(n) + i + 1:]
    def check_list(n):
        l = []
        try:
            while n[0] != 'e':
                w, n = this(n)
                l.append(w)
        except IndexError:
            pass
        return l, n[1:]
    def check_dict(n):
        d = {}
        k = None
        try:
            while n[0] != 'e':
                w, n = this(n)
                if not k:
                    k = w
                else:
                    d[k] = w
                    k = None
        except IndexError:
            pass
        return d, n[1:]
    def check_int(o):
        n = ""
        i = 0
        try:
            while o[i] != 'e':
                n += o[i]
                i += 1
        except IndexError:
            pass
        return int(n), o[i + 1:]
    ty = {'l': check_list,
        'd': check_dict,
        'i': check_int}
    c = check(l)
    if c:
        return c[0]
    else:
        return None
    
def parse_files(tor):
    g = get_info(tor)
    if g and 'info' in g:
        info = get_info(tor)['info']
    else:
        return None
    if 'files' in info:
        files = []
        c = 1
        size = 0
        for i in info['files']:
            files.append({'id': c, 'file': i['path'][0], 'size': i['length']})
            size += i['length']
            c += 1
        return {'size': size, 'folder': info['name'], 'files': files}
    elif 'name' in info and 'length' in info:
        return {'size': info['length'], 'file': info['name']}

