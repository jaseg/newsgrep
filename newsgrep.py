#!/usr/bin/env python3

import re
import sys
import itertools

import grequests
import humanize
import bs4

FEEDS = [
        'http://rss.sueddeutsche.de/app/service/rss/alles/index.rss?output=rss',
        'http://www.tagesschau.de/xml/rss2',
        'http://www.spiegel.de/schlagzeilen/index.rss',
        'http://newsfeed.zeit.de/all',
        'http://www.faz.net/rss/aktuell',
        'http://www.taz.de/!p4608;rss/',
        'http://www.welt.de/?service=Rss',
        'http://www.handelsblatt.com/contentexport/feed/schlagzeilen']

def cut_and_cull(text, leftmost=0, rightmost=0, tolerance=3):
    words = [w for w in text.split() if not 'http://' in w or '.html' in w] # a bit savage, but works fair enough.
    if len(words) < leftmost + rightmost + tolerance:
        return ' '.join(words)
    return ' '.join(words[:leftmost] + ['[...]'] + words[-rightmost:])

def highlight_match(searchre, text, hlext=9, tol=5, sep=['[...]']):
    text = searchre.sub('\033[93m\\g<0>\033[0m', text)

    sentences = text.split('.')
    hlstate = False
    hlstack = [[]]
    for i, st in enumerate(sentences):
        words = [':START:', *st.split(), ':END:']
        if len(words) < 3: # empty sentence
            continue
        words[-2] += '.' # fix up full stop at end of sentence
        wkeep = [False] * len(words)

        for j, w in enumerate(words):
            if '\033[93m' in w:
                hlstate = True
            wkeep[j] = hlstate
            if '\033[0m' in w:
                hlstate = False
        wkeep[-1] = False # exclude :END:
        
        groups = [ (key, len(list(group))) for key, group in itertools.groupby(wkeep) ]
        if len(groups) >= 3: # Single highlight in sentence, possibly entire sequence.
            (frontkeep, frontlen), *mid, (backkeep, backlen) = groups
            
            # reverse iterator to not clobber indices for later iterations
            for i, (keep, klen) in reversed(list(enumerate(mid, start=1))):
                if not keep: # no-keep area bounded by keep-areas on both sides
                    if klen < 2*hlext+tol:
                        groups[i][0] = True
                    else: 
                        groups = [*groups[:i], (True, hlext), (False, klen-2*hlext), (True, hlext), *groups[i+1:]]


            if frontlen < hlext+tol:
                groups[0] = (True, frontlen)
            else:
                groups = [(False, frontlen-hlext), (True, hlext), *groups[1:]]

            if backlen < hlext+tol:
                groups[-1] = (True, backlen)
            else:
                groups = [*groups[:-1], (True, hlext), (False, backlen-hlext)]
        wkeep = [ keep for keeps in ( [keep]*klen for keep, klen in groups ) for keep in keeps ]
        words, wkeep = words[1:-1], wkeep[1:-1] # cut end delims
        newgroups = [ (key, len(list(group))) for key, group in itertools.groupby(wkeep) ]

        (frontkeep, frontlen), *rest = newgroups

        if frontkeep: # if necessary, join sentence groups
            if hlstack[-1] is not sep:
                hlstack[-1] += words[:frontlen]
            else:
                hlstack.append(words[:frontlen])
        elif hlstack[-1] is not sep:
            hlstack.append(sep)
        windex = frontlen
        for keep, klen in rest:
            if keep:
                hlstack.append(words[windex:windex+klen])
            else:
                hlstack.append(sep)
            windex += klen
    if not hlstack[0]:
        hlstack = hlstack[1:]
    return ' '.join( ' '.join(s) for s in hlstack )

searchre = re.compile('|'.join(sys.argv[1:]), flags=re.IGNORECASE)
nothing_found = []
lookup_failed = []
def fail_handler(req, exception):
    lookup_failed.append(req.url.split('.')[1]) # see below.

for res in grequests.map((grequests.get(url) for url in FEEDS), exception_handler=fail_handler):

    if not res:
        continue

    soup = bs4.BeautifulSoup(res.text, 'lxml')
    found = soup(text=searchre)
    sitename = res.url.split('.')[1] # somewhat primitive, but works. more useful than the actual feed <title>s

    if not found:
        nothing_found.append(sitename)
        continue

    print('Site: \033[96m{}\033[0m'.format(sitename))
    found_dict = {}
    for element in found:
        item = element.find_parent('item')
        found_dict[item.find('guid').text] = item
    
    for link in sorted(found_dict.keys()):
        item = found_dict[link]
        ce, desc = item.find('content:encoded'), item.find('description')
        title, date = item.find('title').text, item.find('pubdate').text
        text = str(ce.text) if ce else str(desc.text)
        #HACKHACKHACK
        if 'faz' in link or  'zeit' in link: # some people just can't standards
            text = bs4.BeautifulSoup(text, 'lxml').text

        print('In:   \033[92m{}\033[0m'.format(title))
        print('Link: \033[92m{}\033[0m'.format(link))
        print('Date: \033[92m{}\033[0m'.format(humanize.naturaltime(date)))
        print(highlight_match(searchre, text))
        print()
    print()

if nothing_found:
    print('Nothing found in:\033[96m', *sorted(nothing_found), '\033[0m')

if lookup_failed:
    print('Lookup failed for:\033[91m', *sorted(lookup_failed), '\033[0m', file=sys.stderr)

