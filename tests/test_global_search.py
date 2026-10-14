import time
import unittest
from dizytv.global_search import find_global

class GlobalSearchTests(unittest.TestCase):
    def test_search_all_2200_channels_and_programmes_without_cap(self):
        now=int(time.time())
        channels=[{'id':str(i),'name':f'Ace Channel {i}','group':'Ace',
                   'country':'GB','genre':'News','transport':'Ace Stream'} for i in range(2200)]
        channels.append({'id':'f','name':'Freeview News','country':'GB'})
        p={'channel':'space','title':'Solar News Forecast','start':now+3600,'end':now+4400}
        old={'channel':'space','title':'Solar News Forecast','start':now-5000,'end':now-4000}
        epg={'space':[p,old]}
        mapping={'f':'space'}
        channels_found=find_global(channels,epg,mapping,'aCe ChANnel',now)
        self.assertEqual(2200,len(channels_found))
        self.assertEqual('channel',channels_found[0][0])
        programme_hits=find_global(channels,epg,mapping,'solar',now)
        self.assertEqual([('programme','f')],[(x[0],x[1]['id']) for x in programme_hits])
        self.assertEqual([],find_global(channels,epg,mapping,'',now))
    def test_no_epg_channels_remain_searchable(self):
        ch=[{'id':'x','name':'BBC Radio 2','group':'Radio','country':'UK'}]
        self.assertEqual('x',find_global(ch,{}, {},'radio')[0][1]['id'])
    def test_two_regions_map_to_one_epg_programme(self):
        now=int(time.time())
        chans=[{'id':'north','name':'ITV North'},{'id':'south','name':'ITV South'}]
        epg={'itv':[{'title':'The Evening Bulletin','start':now,'end':now+300}]}
        result=find_global(chans,epg,{'north':'itv','south':'itv'},'bulletin',now)
        self.assertEqual({'north','south'},{x[1]['id'] for x in result})
