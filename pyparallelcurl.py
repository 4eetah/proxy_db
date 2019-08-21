import sys
import pycurl
import cStringIO
import time
from progressbar import ProgressBar
from logger import logger
from random import randint

try:
    import signal
    from signal import SIGPIPE, SIG_IGN
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass

reqtimeout = 10
conntimeout = 3

class ParallelCurl:

    max_requests = 10
    options = {}
    default_options = {
        pycurl.SSL_VERIFYPEER: False,
        pycurl.SSL_VERIFYHOST: False,
        pycurl.USERAGENT: 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/533.2 (KHTML, like Gecko) Chrome/5.0.342.3 Safari/533.2',
        pycurl.FOLLOWLOCATION: True,
        pycurl.CONNECTTIMEOUT: conntimeout,
        pycurl.TIMEOUT: reqtimeout,
        pycurl.BUFFERSIZE: 1024*1024,
        pycurl.ENCODING: 'gzip,deflate',
        pycurl.HEADER: False,
        pycurl.FRESH_CONNECT: False,
        #pycurl.TCP_KEEPALIVE: True,
        #pycurl.TCP_KEEPIDLE: 120,
        #pycurl.TCP_KEEPINTVL: 60,
    }

    outstanding_requests = {}
    multi_handle = None

    def __init__(self, in_max_requests = 10, in_options = default_options):
        self.max_requests = in_max_requests
        self.options = in_options

        self.outstanding_requests = {}
        self.multi_handle = pycurl.CurlMulti()

    # Ensure all the requests finish nicely
    def __del__(self):
        #print 'self.max_requests='+str(self.max_requests)
        self.finishallrequests()

    # Sets how many requests can be outstanding at once before we block and wait for one to
    # finish before starting the next one
    def setmaxrequests(self, in_max_requests):
        self.max_requests = in_max_requests

    # Sets the options to pass to curl, using the format of curl_setopt_array()
    def setoptions(self, in_options):
        self.options = in_options

    def getoptions(self):
        return self.options

    def resetoptions(self):
        self.options = self.default_options

    # Start a fetch from the 'url' address, calling the 'callback' function passing the optional
    # 'user_data' value. The callback should accept 3 arguments, the url, curl handle and user
    # data, eg on_request_done(url, ch, user_data)
    def startrequest(self, url, callback, user_data = {}, post_fields=None):

        if self.max_requests > 0:
            self.waitforoutstandingrequeststodropbelow(self.max_requests)

        ch = pycurl.Curl()
        for option, value in self.options.items():
            ch.setopt(option, value)
        ch.setopt(pycurl.URL, url)
        result_buffer = cStringIO.StringIO()
        ch.setopt(pycurl.WRITEFUNCTION, result_buffer.write)

        if post_fields is not None:
            ch.setopt(pycurl.POST, True)
            ch.setopt(pycurl.POSTFIELDS, post_fields)

        self.multi_handle.add_handle(ch)

        self.outstanding_requests[ch] = {
            'handle': ch,
            'result_buffer': result_buffer,
            'url': url,
            'callback': callback,
            'user_data':user_data
        }

        self.checkforcompletedrequests()

    # You *MUST* call this function at the end of your script. It waits for any running requests
    # to complete, and calls their callback functions
    def finishallrequests(self):
        self.waitforoutstandingrequeststodropbelow(1)

    # Checks to see if any of the outstanding requests have finished
    def checkforcompletedrequests(self):

        # Call select to see if anything is waiting for us
        if self.multi_handle.select(1.0) == -1:
            return;

        # Since something's waiting, give curl a chance to process it
        while True:
            ret, num_handles = self.multi_handle.perform()
            if ret != pycurl.E_CALL_MULTI_PERFORM:
                break

        # Now grab the information about the completed requests
        while True:
            num_q, ok_list, err_list = self.multi_handle.info_read()
            for ch in ok_list:
                if ch not in self.outstanding_requests:
                    raise RuntimeError("Error - handle wasn't found in requests: '"+str(ch)+"' in "
                        +str(self.outstanding_requests))

                request = self.outstanding_requests[ch]

                url = request['url']
                content = request['result_buffer'].getvalue()
                callback = request['callback']
                user_data = request['user_data']

                callback(content, url, ch, user_data)

                self.multi_handle.remove_handle(ch)

                del self.outstanding_requests[ch]

            for ch, errno, errmsg in err_list:

                if ch not in self.outstanding_requests:
                    raise RuntimeError("Error - handle wasn't found in requests: '"+str(ch)+"' in "
                        +str(self.outstanding_requests))

                request = self.outstanding_requests[ch]

                url = request['url']
                content = None
                callback = request['callback']
                user_data = request['user_data']

                callback(content, url, ch, user_data)

                self.multi_handle.remove_handle(ch)

                del self.outstanding_requests[ch]

            if num_q < 1:
                break

    # Blocks until there's less than the specified number of requests outstanding
    def waitforoutstandingrequeststodropbelow(self, max):
        while True:
            self.checkforcompletedrequests()
            if len(self.outstanding_requests) < max:
                break

            time.sleep(0.01)

    def getcontent(self, urls, progress=False):
        if isinstance(urls, basestring):
            urls = [urls]
        if not len(urls):
            return {}

        def on_page_recv(content, url, ch, user_data):
            user_data[url] = content

        if progress:
            bar = ProgressBar()
        else:
            def bar(vec):
                return vec

        result = {}
        for url in bar(urls):
            self.startrequest(url, on_page_recv, result)
        self.finishallrequests()

        return result



class Proxy(object):
    '''
    the file format for steroids is:
    ip port type
    '''
    enough = 50
    def __init__(self, proxy_file='steroids.txt'):
        with open(proxy_file) as f:
            lines = f.read().splitlines()
        if not len(lines):
            raise NoSteroidsFoundException('no steroids found')
        if len(lines) < self.enough:
            raise NoSteroidsFoundException('not enough steroids, need > %s' % str(self.enough))
        self.proxies = []
        for p in lines:
            ll = p.split(',')
            ip = ll[0]
            port = ll[1]
            ptype = ll[2]
            record = {}
            record['ip'] = ip
            record['port'] = int(port)
            record['type'] = ptype
            self.proxies.append(record)
        self.cnt = randint(0, len(self.proxies)-1)
        self.proxytypes = {\
                'socks4': pycurl.PROXYTYPE_SOCKS4,
                'socks5': pycurl.PROXYTYPE_SOCKS5,
                'http': pycurl.PROXYTYPE_HTTP,
                'https': pycurl.PROXYTYPE_HTTP,
                }

    def next(self):
        next_proxy = self.proxies[self.cnt % len(self.proxies)]
        self.cnt += 1
        return next_proxy

    def proxy_rotate(self, ch):
        next_proxy = self.next()
        ch.setopt(pycurl.PROXYTYPE, self.proxytypes[next_proxy['type']])
        ch.setopt(pycurl.PROXY, next_proxy['ip'])
        ch.setopt(pycurl.PROXYPORT, next_proxy['port'])
        logger.debug('Using proxy: %s://%s:%s' % (next_proxy['type'], next_proxy['ip'], next_proxy['port']))
        return next_proxy

    def rotate(self, pcurl):
        opts = pcurl.getoptions()
        next_proxy = self.next()
        opts[pycurl.PROXYTYPE] = self.proxytypes[next_proxy['type']]
        opts[pycurl.PROXY] = next_proxy['ip']
        opts[pycurl.PROXYPORT] = next_proxy['port']
        pcurl.setoptions(opts)
        logger.debug('Using proxy: %s://%s:%s' % (next_proxy['type'], next_proxy['ip'], next_proxy['port']))
        return next_proxy

    def __len__(self):
        return len(self.proxies)

    def __iter__(self):
        return iter(self.proxies)


class UserAgent(object):
    def __init__(self, agents_file='user-agents.txt'):
        with open(agents_file) as f:
            self.agents = f.read().splitlines()
        if not len(self.agents):
            raise NoUserAgentsFoundException('no user agents found')

    def next(self):
        n = randint(0, len(self.agents)-1)
        return self.agents[n]

    def agent_rotate(self, ch):
        next_agent = self.next()
        ch.setopt(pycurl.USERAGENT, next_agent)
        logger.debug('Using User-Agent: %s' % next_agent)
        return next_agent

    def rotate(self, pcurl):
        opts = pcurl.getoptions()
        next_agent = self.next()
        opts[pycurl.USERAGENT] = next_agent
        pcurl.setoptions(opts)
        logger.debug('Using User-Agent: %s' % next_agent)
        return next_agent

    @staticmethod
    def set_user_agent(pcurl, agent):
        opts = pcurl.getoptions()
        opts[pycurl.USERAGENT] = agent
        pcurl.setoptions(opts)
        logger.debug('Using User-Agent: %s' % agent)
        return agent


class NoUserAgentsFoundException(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg

class NoSteroidsFoundException(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return self.msg
