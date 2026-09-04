import re
from html.parser import HTMLParser

class ChecklistHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = "
 self.h1_texts = []
 self.h2_texts = []
 self.h3_texts = []
 self.current_tag = None
 self.tag_stack = []
 self.tables = [] # list of rows, each row is list of cell strings
 self.current_table = []
 self.current_row = []
 self.current_cell = []
 self.list_items = []
 self.current_li = []
 self.in_table = False
 self.in_cell = False
 self.in_li = False
 self.in_heading = False
 self.heading_text = []

 def handle_starttag(self, tag, attrs):
 self.tag_stack.append(tag)
 self.current_tag = tag
 if tag in (h1, h2, h3, title):
 self.in_heading = True
 self.heading_text = []
 elif tag == table:
 self.in_table = True
 self.current_table = []
 elif tag == tr and self.in_table:
 self.current_row = []
 elif tag in (td, th) and self.in_table:
 self.in_cell = True
 self.current_cell = []
 elif tag == li:
 self.in_li = True
 self.current_li = []

 def handle_endtag(self, tag):
 if self.tag_stack and self.tag_stack[-1] == tag:
 self.tag_stack.pop()
 self.current_tag = self.tag_stack[-1] if self.tag_stack else None

 if tag == title:
 self.title =  .join(.join(self.heading_text).split())
 self.in_heading = False
 elif tag == h1:
 self.h1_texts.append( .join(.join(self.heading_text).split()))
 self.in_heading = False
 elif tag == h2:
 self.h2_texts.append( .join(.join(self.heading_text).split()))
 self.in_heading = False
 elif tag == h3:
 self.h3_texts.append( .join(.join(self.heading_text).split()))
 self.in_heading = False
 elif tag in (td, th) and self.in_cell:
 self.in_cell = False
 cell_str =  .join(.join(self.current_cell).split())
 self.current_row.append(cell_str)
 self.current_cell = []
 elif tag == tr and self.in_table:
 if any(cell.strip() for cell in self.current_row):
 self.current_table.append(self.current_row)
 self.current_row = []
 elif tag == table and self.in_table:
 self.in_table = False
 if self.current_table:
 self.tables.append(self.current_table)
 self.current_table = []
 elif tag == li and self.in_li:
 self.in_li = False
 li_str =  .join(.join(self.current_li).split())
 if li_str:
 self.list_items.append(li_str)
 self.current_li = []

 def handle_data(self, data):
 if self.in_heading:
 self.heading_text.append(data)
 if self.in_cell:
 self.current_cell.append(data)
 elif self.in_li:
 self.current_li.append(data)

html_sample = "
<!DOCTYPE html>
<html>
<head><title>2023-24 Panini Prizm Basketball Checklist</title></head>
<body>
<h1>2023-24 Panini Prizm Basketball Checklist</h1>
<h2>Base Set Checklist</h2>
<table class=checklist>
 <thead><tr><th>Card #</th><th>Player</th><th>Team</th></tr></thead>
 <tbody>
 <tr><td>01</td><td>Victor Wembanyama RC</td><td>San Antonio Spurs</td></tr>
 <tr><td>007</td><td>Luka Dončić</td><td>Dallas Mavericks</td></tr>
 <tr><td>75</td><td>Stephen Curry</td><td>Golden State Warriors</td></tr>
 <tr><td>101</td><td>Scoot Henderson (RC)</td><td>Portland Trail Blazers</td></tr>
 <tr><td>RC-1</td><td>Brandon Miller RC</td><td>Charlotte Hornets</td></tr>
 </tbody>
</table>
<h2>Parallels Breakdown</h2>
<ul>
 <li>Silver Prizm</li>
 <li>Red Prizm /99</li>
 <li>Blue Prizm /199</li>
 <li>Gold Prizm /10</li>
</ul>
</body>
</html>
"

parser = ChecklistHTMLParser()
parser.feed(html_sample)
print(Title:, parser.title)
print(H1:, parser.h1_texts)
print(H2:, parser.h2_texts)
print(Tables count:, len(parser.tables))
print(Table rows:, len(parser.tables[0]))
for row in parser.tables[0]:
 print(  Row:, row)
print(List items:, parser.list_items)
