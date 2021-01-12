from bs4 import BeautifulSoup, NavigableString
text = (
    '<ul><li>West Germanic: '
    '<span class="Latinx" lang="gmw-pro"><a href="/wiki/Germanic/raud" title="Germanic/raud">*raud</a></span>'
    '<ul><li>Old English: '
    '<span class="Latinx" lang="ang"><a href="/wiki/read#Old_English" title="read">rēad</a></span>'
    '<ul><li>Middle English: '
    '<span class="Latn" lang="enm"><a href="/wiki/read#Middle_English" title="read">read</a></span>'
    '<style data-mw-deduplicate="TemplateStyles:r54857417">.mw-parser-output .desc-arr[title]{cursor:help}.mw-parser-output .desc-arr[title="uncertain"]{font-size:.7em;vertical-align:super}</style>, '
    '<span class="Latn" lang="enm"><a href="/wiki/rede#Middle_English" title="rede">rede</a></span>, '
    '<span class="Latn" lang="enm"><a href="/wiki/red#Middle_English" title="red">red</a></span>'
    '<ul><li>English: <span class="Latn" lang="en"><a href="/wiki/red#English" title="red">red</a></span>'
    '<link rel="mw-deduplicated-inline-style" href="mw-data:TemplateStyles:r54857417"/></li></li></li></ul>'
)

soup = BeautifulSoup(text)

list_items = soup.findAll('li')
first_list = soup.find('li')
text = soup.li.find(text=True)

test_string = ''
for i in first_list.contents:
    if (i.name == 'ul'):
        continue
    if (isinstance(i, NavigableString)):
        test_string += i
    else:
        test_string += i.text

test2 = test_string
