import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from dizytv.channel_health import (
    public_stream_url,interpret_http,check_channel,check_batch,BATCH_SIZE,MAX_WORKERS,
    _probe_public
)


class HealthTests(unittest.TestCase):
    def test_http_categories_distinguish_weak_evidence_and_access_limits(self):
        self.assertEqual('access-limited',interpret_http(403)[0])
        self.assertEqual('missing',interpret_http(404)[0])
        self.assertEqual('rate-limited',interpret_http(429)[0])
        self.assertEqual('provider-error',interpret_http(502)[0])
        self.assertEqual('manifest-only',interpret_http(200,'application/vnd.apple.mpegurl',b'#EXTM3U\n#EXT-X-VERSION:3')[0])
        self.assertEqual('not-a-stream',interpret_http(200,'text/html',b'<html>Login</html>')[0])
        self.assertEqual('unverified',interpret_http(200,'application/json',b'{"error":"sign in"}')[0])

    def test_local_and_private_hosts_are_not_scanned(self):
        for uri in ('http://127.0.0.1:8080','http://192.168.1.202:8000',
                    'http://localhost:6878','http://10.0.0.1',
                    'http://[::1]:7777','https://example.local/live'):
            with self.assertRaises(ValueError):
                public_stream_url(uri)
        with patch('dizytv.channel_health.socket.getaddrinfo',return_value=[
                (2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):
                public_stream_url('https://malicious.example/stream')

    def test_sample_check_is_bounded_and_does_not_report_playback_success(self):
        class Response:
            status=200
            headers={'Content-Type':'application/x-mpegURL'}
            def __init__(self,url):self.url=url
            def geturl(self):return self.url
            def read(self,length):
                self.length=length
                return b'#EXTM3U\n#EXT-X-STREAM-INF:'
            def __enter__(self):return self
            def __exit__(self,*a):pass
        opened=[]
        def opener(request,timeout):
            opened.append((request.full_url,timeout))
            return Response(request.full_url)
        public=(2,1,6,'',('8.8.8.8',443))
        with patch('dizytv.channel_health.socket.getaddrinfo',return_value=[public]):
            status=check_channel({'stream':'https://example.com/stream.m3u8?token=private'},opener=opener)
        self.assertEqual('manifest-only',status['status'])
        self.assertNotIn('private',str(status))
        self.assertEqual(4,opened[0][1])
        self.assertEqual('engine-required',check_channel(
            {'stream':'acestream://0123456789abcdef0123456789abcdef01234567'})['status'])

    def test_four_thread_batches_advance_without_losing_order_or_exposing_urls(self):
        channels=[{'id':str(i),'name':'Channel '+str(i),
                   'stream':'https://example.com/'+str(i)+'?secret=123'} for i in range(130)]
        def fake(_):return {'status':'unverified','detail':'Not a playback test'}
        first,offset=check_batch(channels,0,BATCH_SIZE,MAX_WORKERS,checker=fake)
        second,end=check_batch(channels,offset,BATCH_SIZE,checker=fake)
        self.assertEqual((40,80),(len(first),end))
        self.assertEqual('Channel 0',first[0]['name'])
        self.assertEqual('Channel 79',second[-1]['name'])
        self.assertNotIn('secret',str(first))
        with self.assertRaises(ValueError):check_batch(channels,0,100000)
        with self.assertRaises(ValueError):check_batch(channels,0,1,100000)

    def test_http_error_classification_does_not_disclose_stream_tokens(self):
        with patch('dizytv.channel_health.public_stream_url',side_effect=lambda x:x):
            def error(req,timeout):
                raise HTTPError(req.full_url,403,'Denied',{},None)
            response=check_channel({'stream':'https://test.example/stream?secret=123'},opener=error)
        self.assertEqual('access-limited',response['status'])
        self.assertNotIn('123',str(response))


    def test_dns_rebinding_cannot_change_connection_target_after_validation(self):
        # A DNS reply turns private on the second lookup. The actual socket
        # must use the first validated public IP, with no second resolution.
        class Response:
            status = 200
            def getheader(self, key, default=''):
                return 'video/mp2t' if key == 'Content-Type' else default
            def read1(self, count):
                return b'\x47' * 20

        class Connection:
            def __init__(self, hostname, port, timeout):
                self.hostname = hostname
                self.port = port
                self.timeout = timeout
            def request(self, *args, **kwargs):
                self._create_connection((self.hostname, self.port), self.timeout)
            def getresponse(self):
                return Response()
            def close(self):
                pass

        dns = [(2,1,6,'',('8.8.8.8',80))]
        with patch('dizytv.channel_health.socket.getaddrinfo', side_effect=[
                     dns, [(2,1,6,'',('127.0.0.1',80))]]) as resolve, \
             patch('dizytv.channel_health.socket.create_connection', return_value=object()) as connect, \
             patch('dizytv.channel_health.http.client.HTTPConnection', Connection):
            status, _ = _probe_public('http://rebind.example/channel', 2)
        self.assertEqual('data-response', status)
        self.assertEqual(1, resolve.call_count)
        self.assertEqual('8.8.8.8', connect.call_args.args[0][0])

    def test_private_redirect_is_never_connected(self):
        class Response:
            status = 302
            def getheader(self, name, default=''):
                return 'http://127.0.0.1/admin' if name == 'Location' else default
        class Connection:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return Response()
            def close(self):
                pass
        with patch('dizytv.channel_health.socket.getaddrinfo', return_value=[
                    (2,1,6,'',('8.8.8.8',80))]), \
             patch('dizytv.channel_health.http.client.HTTPConnection', Connection), \
             patch('dizytv.channel_health.socket.create_connection') as connect:
            with self.assertRaises(ValueError):
                _probe_public('http://public.example/redirect', 2)
        connect.assert_not_called()

    def test_health_check_has_overall_deadline_even_when_probe_stalls(self):
        def never_finishes(*_):
            time.sleep(.20)
            return ('manifest-only', 'late')
        with patch('dizytv.channel_health._probe_public', side_effect=never_finishes):
            started = time.monotonic()
            result = check_channel({'stream': 'https://example.com/live'}, timeout=.02)
            elapsed = time.monotonic() - started
        self.assertEqual('unreachable', result['status'])
        self.assertLess(elapsed, .15)



if __name__=='__main__': unittest.main()
