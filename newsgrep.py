#!/usr/bin/env python3

import re
import sys

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

def highlight_match(searchre, text):
	highlight = lambda s: '\033[93m'+s+'\033[0m'
	for par in text.split('\n\n'):
		par = par.strip()
		positions = [ m.span() for m in searchre.finditer(par) ]
		if positions:
			(first, _1), (lastm, last) = positions[0], positions[-1]
			yield cut_and_cull(par[:first], rightmost=5)
			yield '\033[91m<1>\033[0m'
			if len(positions)>1: # handle intervals between matches
				for (matchs,left),(right,_2) in zip(positions[:-1], positions[1:]):
					yield '\033[91m<2>\033[0m'
					yield highlight(par[matchs:left])
					yield '\033[91m<3>\033[0m'
					yield cut_and_cull(par[left:right], leftmost=5, rightmost=5)
			yield '\033[91m<4>\033[0m'
			yield highlight(par[lastm:last])
			yield '\033[91m<5>\033[0m'
			yield cut_and_cull(par[last:], leftmost=5)
			yield '\033[91m<6>\033[0m'

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
	
	for link, item in found_dict.items():
		ce, desc = item.find('content:encoded'), item.find('description')
		title, date = item.find('title').text, item.find('pubdate').text
		text = str(ce.text) if ce else str(desc.text)
		print('In:   \033[92m{}\033[0m'.format(title))
		print('Link: \033[92m{}\033[0m'.format(link))
		print('Date: \033[92m{}\033[0m'.format(humanize.naturaltime(date)))
		for m in highlight_match(searchre, text):
			print(m, end='')
		print()
	print()

if nothing_found:
	print('Nothing found in:\033[96m', *nothing_found, '\033[0m')

if lookup_failed:
	print('Lookup failed for:\033[91m', *lookup_failed, '\033[0m', file=sys.stderr)

