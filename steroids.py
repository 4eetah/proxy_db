from lxml import html as xhtml
import re
import logger
from logger import logger as log
from pyparallelcurl import ParallelCurl, Proxy
import pycurl
from StringIO import StringIO

bad_steroids='bad_steroids.txt'
good_steroids='steroids.txt'
check_url = 'https://example.com'
keyword = 'Example Domain'
options = {
    pycurl.SSL_VERIFYPEER: False,
    pycurl.SSL_VERIFYHOST: False,
    pycurl.USERAGENT: 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11',
    pycurl.FOLLOWLOCATION: True,
    pycurl.CONNECTTIMEOUT: 5,
    pycurl.TIMEOUT: 10,
}

class MyCurl(object):
    def __init__(self, opts=options):
        self.opts = opts
    def get(self, url):
        ch = pycurl.Curl()
        for op, val in self.opts.items():
            ch.setopt(op, val)
        ch.setopt(pycurl.URL, url)
        try:
            buf = StringIO()
            ch.setopt(pycurl.WRITEDATA, buf)
            ch.perform()
            page = buf.getvalue()
        except Exception, e:
            log.warn(str(e) + ' , url: ' + url)
            page = None
        buf.close()
        ch.close()
        return page

def check_proxy_str(fields, d):
    proxyStringGood = True
    for field in fields:
        if not d.get(field):
            proxyStringGood = False
            break
    return proxyStringGood


def http_free_proxy(url):
    proxylist = []
    try:
        page = MyCurl().get(url)
        if not page:
            raise Exception()
    except Exception, e:
        log.critical(str(e) + ', unable to fetch proxylist page: ' + url)
        return proxylist

    xtree = xhtml.fromstring(page)
    rows = xtree.xpath('//table//tbody//tr')
    fields = ['ip', 'port', 'code', 'country', 'anonymity', 'google', 'https', 'last_checked']
    records = []
    for tr in rows:
        td = tr.xpath('.//td/text()')
        r = dict(zip(fields, td))

        if not check_proxy_str(fields, r):
            continue

        if r['https'] == 'yes':
            r['type'] = 'https'
        else:
            r['type'] = 'http'
        records.append(r)
    return records


def socks_free_proxy(url):
    proxylist = []
    try:
        page = MyCurl().get(url)
        if not page:
            raise Exception()
    except Exception, e:
        log.critical(str(e) + ', unable to fetch proxylist page: ' + url)
        return proxylist

    xtree = xhtml.fromstring(page)
    rows = xtree.xpath('//table//tbody//tr')
    fields = ['ip', 'port', 'code', 'country', 'version', 'anonimity', 'https', 'last_checked']
    records = []
    for tr in rows:
        td = tr.xpath('.//td/text()')
        r = dict(zip(fields, td))
        r['type'] = r['version'].lower() #socks4 or socks5

        if not check_proxy_str(fields, r):
            continue

        records.append(r)
    return records

steroids = {
    'https://free-proxy-list.net': http_free_proxy,
    'https://www.socks-proxy.net': socks_free_proxy,
}

def make_bad():
    records = []
    for url, handle in steroids.items():
        r = handle(url)
        records.extend(r)
    return records

def on_page_recv(content, url, ch, user_data):
    proxy = user_data['proxy']
    code = ch.getinfo(pycurl.RESPONSE_CODE)
    if content and code == 200:
        result = user_data['result']
        if re.search('(%s)' % keyword, content):
            log.info('Good proxy: %s://%s:%s, response code: %s, keyword match: %s' % (proxy['type'], proxy['ip'], proxy['port'], str(code), keyword))
            result.append(proxy)
            return
    log.info('Bad proxy: %s://%s:%s' % (proxy['type'], proxy['ip'], proxy['port']))

def make_good():
    pcurl = ParallelCurl(100)
    proxy = Proxy(proxy_file=bad_steroids)
    records = []
    for p in proxy:
        prx = proxy.rotate(pcurl)
        pcurl.startrequest(check_url, on_page_recv, {'result':records, 'proxy':prx})
    return records

def make_steroids():
    records = make_bad()
    with open(bad_steroids, 'wb') as f:
        for r in records:
            l = [r['ip'], r['port'], r['type']]
            row = ' '.join(l) + '\n'
            f.write(row)
    records = make_good()
    with open(good_steroids, 'wb') as f:
        for r in records:
            l = [r['ip'], str(r['port']), r['type']]
            row = ' '.join(l) + '\n'
            f.write(row)

if __name__ == '__main__':
    print '`tail -f %s` to see progress' % logger.log_file
    make_steroids()
