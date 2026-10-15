"""Pure helpers for show-marathon discovery and channel sorting.

These are *classification* rules, not evidence of valid stream playback.
Opaque stream IDs and source metadata are never rewritten by these helpers.
"""
import re
from urllib.parse import urlparse

CHANNEL_SORT_MODES = (
    'Name A–Z', 'UK Freeview style', 'Similar names / +1',
    'Country → category', 'Category → name', 'Playlist order',
)

SHOW_NAMES = (
    'south park', 'rick and morty', 'family guy', 'the simpsons',
    'os simpsons',
    'simpsons', 'brooklyn nine nine', 'brooklyn 99', 'the goldbergs',
    'big bang theory', 'young sheldon', 'friends', 'futurama',
    'king of the hill', 'american dad', 'frasier', 'cheers',
    'the office', 'seinfeld', 'everybody loves raymond', 'modern family',
    'the middle', 'scrubs', 'two and a half men', 'malcolm in the middle',
    'only fools and horses', 'fawlty towers', 'peep show', 'the inbetweeners',
    'friday night dinner', 'the young ones', 'midsomer murders',
    'murder she wrote', 'columbo', 'the twilight zone', 'the addams family',
    'degrassi', 'saved by the bell',
    'how i met your mother', 'mr bean', 'sister sister', 'corner gas',
    'classic tv comedy', 'hit sitcoms', 'tv land sitcoms',
    'pluto tv sitcoms', 'pluto tv comedy movies', 'tv comedy movies',
)
LOOP_TAG = re.compile(
    r'(?:\b24\s*/\s*7\b|\b247\b|\b24[- ]hour\b|\b24\s*7\b|'
    r'\bmarathon\b|\bbinge[- ]?watch\b|\bnon[- ]stop\b|'
    r'\bloop(?:s|ing)?\b)', re.I
)
NON_SHOW = re.compile(
    r'\b(?:news|weather|sport|sports|football|soccer|cricket|'
    r'golf|racing|business|radio|music|traffic|live[- ]event)\b', re.I
)
FREEVIEW_UK = {
    'bbc one':1, 'bbc two':2, 'itv1':3, 'itv':3, 'channel 4':4,
    'channel 5':5, 'itv2':6, 'bbc three':7, 'bbc four':9,
    'itv3':10, 'sky mix':11, 'quest':12, 'e4':13,
    'film4':14, 'really':17, 'more4':18, 'dave':19, 'drama':20,
    '5usa':21, 'itv4':25, 'yesterday':27, '5star':30,
    '4seven':47, 'bbc news':231,
}


def _name(name):
    from .core import display_channel_name
    label=display_channel_name(name).casefold()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9+ ]+', ' ', label)).strip()


def _base(name):
    return re.sub(r'\s*\+\s*1$', '', _name(name))


def _plus_one(name):
    return bool(re.search(r'\s*\+\s*1$', _name(name)))


def is_show_loop_channel(channel):
    """Prefer programme-based dedicated feeds; avoid generic 24/7 news/sports."""
    from .core import channel_kind
    if channel_kind(channel)=='Radio':
        return False
    name=_name(channel.get('name',''))
    group=str(channel.get('group','')).casefold()
    if NON_SHOW.search(name+' '+group):
        return False
    name_normal=re.sub(r'\s+', ' ',re.sub(r'[^a-z0-9 ]+',' ',name)).strip()
    def named_show(show):
        # Avoid treating generic children's titles like Garfield and Friends
        # or Ryan and Friends as the dedicated sitcom "Friends" channel.
        if show=='friends':
            return bool(name_normal=='friends' or
                        re.search(r'(?:247|24 7) friends|friends (?:tv|sitcom)',name_normal))
        return bool(re.search(r'(?<!\\w)'+re.escape(show)+r'(?!\\w)',name_normal))
    named=any(named_show(show) for show in SHOW_NAMES)
    tagged=bool(LOOP_TAG.search(name+' '+group))
    group_loop=bool(re.search(r'show[- ]loops?|sitcom[- ]marathons?|'
                              r'24\s*/\s*7\s*(?:series|tv|shows)',group,re.I))
    return named or tagged or group_loop


def channel_sort_key(ch,mode,position=0):
    from .core import channel_section
    name=_name(ch.get('name',''))
    base=_base(ch.get('name',''))
    plus=int(_plus_one(ch.get('name','')))
    country=str(ch.get('country','Unspecified'))
    section=channel_section(ch)
    if mode=='Playlist order':
        return (position,)
    if mode=='Similar names / +1':
        return (base,plus,name,position)
    if mode=='Country → category':
        return (country!='United Kingdom',country.casefold(),
                section.casefold(),base,plus,position)
    if mode=='Category → name':
        return (section.casefold(),base,plus,position)
    if mode=='UK Freeview style':
        uk=country=='United Kingdom'
        lcn=str(ch.get('chno','')).strip()
        number=int(lcn) if re.fullmatch(r'\d{1,4}',lcn) else 0
        if uk and not number:
            number=FREEVIEW_UK.get(base,0)
        return (not uk,not bool(number) if uk else True,
                number if number else 100000,base,plus,name,position)
    return (base,plus,name,position)


def stable_channel_key(url):
    """Ignore rotating Plex TV session tokens only for known Plex part paths."""
    p=urlparse(url)
    if (p.scheme=='https' and p.hostname=='epg.provider.plex.tv' and
            re.fullmatch(r'/library/parts/[0-9a-f-]{8,}/?',p.path,re.I)):
        return p._replace(query='',fragment='').geturl()
    return url
