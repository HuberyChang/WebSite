from __future__ import generators

cmdln_desc = '''A fast and complete Python implementation of Markdown, a

text-to-HTML conversion tool for web writers.

Supported extra syntax options (see -x|--extras option below and

see <https://github.com/trentm/python-markdown2/wiki/Extras> for details):



* code-friendly: Disable _ and __ for em and strong.

* cuddled-lists: Allow lists to be cuddled to the preceding paragraph.

* fenced-code-blocks: Allows a code block to not have to be indented

  by fencing it with '```' on a line before and after. Based on

  <http://github.github.com/github-flavored-markdown/> with support for

  syntax highlighting.

* footnotes: Support footnotes as in use on daringfireball.net and

  implemented in other Markdown processors (tho not in Markdown.pl v1.0.1).

* header-ids: Adds "id" attributes to headers. The id value is a slug of

  the header text.

* html-classes: Takes a dict mapping html tag names (lowercase) to a

  string to use for a "class" tag attribute. Currently only supports

  "pre" and "code" tags. Add an issue if you require this for other tags.

* markdown-in-html: Allow the use of `markdown="1"` in a block HTML tag to

  have markdown processing be done on its contents. Similar to

  <http://michelf.com/projects/php-markdown/extra/#markdown-attr> but with

  some limitations.

* metadata: Extract metadata from a leading '---'-fenced block.

  See <https://github.com/trentm/python-markdown2/issues/77> for details.

* nofollow: Add `rel="nofollow"` to add `<a>` tags with an href. See

  <http://en.wikipedia.org/wiki/Nofollow>.

* pyshell: Treats unindented Python interactive shell sessions as <code>

  blocks.

* link-patterns: Auto-link given regex patterns in text (e.g. bug number

  references, revision number references).

* smarty-pants: Replaces ' and " with curly quotation marks or curly

  apostrophes.  Replaces --, ---, ..., and . . . with en dashes, em dashes,

  and ellipses.

* toc: The returned HTML string gets a new "toc_html" attribute which is

  a Table of Contents for the document. (experimental)

* xml: Passes one-liner processing instructions and namespaced XML tags.

* tables: Tables using the same format as GFM

  <https://help.github.com/articles/github-flavored-markdown#tables> and

  PHP-Markdown Extra <https://michelf.ca/projects/php-markdown/extra/#table>.

* wiki-tables: Google Code Wiki-style tables. See

  <http://code.google.com/p/support/wiki/WikiSyntax#Tables>.'''

__version_info__ = (2, 3, 0)
__version__ = '.'.join(map(str, __version_info__))
__author__ = 'cjh'


import os, sys, re, logging, optparse, codecs
from pprint import pprint, pformat
from random import  random, randint
try:
    from hashlib import md5
except ImportError:
    from _md5 import md5

try:
    from urllib.parse import quote # python3
except ImportError:
    from urllib import quote # python2

if sys.version_info[:2] < (2,4):
    from sets import Set as set
    def reversed(sequence):
        for i in sequence[::-1]:
            yield i


if sys.version_info[0] <= 2:
    py3 = False
    try:
        bytes
    except NameError:
        bytes = str
    base_string_type = basestring
elif sys.version_info[0] >= 3:
    py3 = True
    unicode = str
    base_string_type = str


DEBUG = False
log = logging.getLogger('markdown')

DEFAULT_TAB_WIDTH = 4


SECRET_SALT = bytes(randint(0 ,1000000))
def _hash_text(s):
    return 'mds-' + md5(SECRET_SALT + s.encode('utf-8')).hexdigest()

g_escape_table = dict([(ch, _hash_text(ch) for ch in '\\`*_{}[]()>#+-.!')])


class MarkdownError(Exception):
    pass


def markdown_path(path, encoding='utf-8', html4tags=False, tab_width=DEFAULT_TAB_WIDTH,
                  safe_mode=None, extras=None, link_patterns=None,
                  use_file_vars=False):
    fp = codecs.open(path, 'r', encoding)
    text = fp.read()
    fp.close()
    return Markdown(html4tags=html4tags, tab_width=tab_width,
                    safe_mode=safe_mode, extras=extras,
                    link_patterns=link_patterns, user_file_vars=use_file_vars).convert(text)

def markdown(text, html4tags=False, tab_width=DEFAULT_TAB_WIDTH,
             safe_code=None, extras=None, link_patterns=None,
             use_file_vars=False):
    return Markdown(html4tags=html4tags, tab_width=tab_width,
                    safe_mode=safe_code, extras=extras,
                    link_patterns=link_patterns, user_file_vars=use_file_vars).convert(text)



class Markdown(object):
    urls = None
    titles = None
    html_blocks = None
    html_spans = None
    html_removed_text = "[HTML_REMOVED]"

    list_level = 0
    _ws_only_line_re = re.compile(r"^[ \t]+$", re.M)

    def __init__(self, html4tags=False, tab_width=4, safe_mode=None,
                 extras=None, link_patterns=None, user_file_vars=False):
        if html4tags:
            self.empty_element_suffix = '>'
        else:
            self.empty_element_suffix = ' />'
        self.tab_width = tab_width

        if safe_mode is True:
            self.safe.mode = 'replace'
        else:
            self.safe_mode = safe_mode

        if self.extras is None:
            self.extras = {}
        elif not isinstance(self.extras, dict):
            self.extras = dict([(e, None) for e in self.extras])
        if extras:
            if not isinstance(extras, dict):
                extras = dict([(e, None) for e in extras])
            self.extras.update(extras)
        assert isinstance(self.extras, dict)
        if 'toc' in self.extras and not 'header-ids' in self.extras:
            self.extras['header-ids'] = None
        self._instance_extras = self.extras.copy()
        self.link_patterns = link_patterns
        self.use_file_vars = user_file_vars
        self._outdent_re = re.compile(r'^(\t|[ ]{1,%d})'%tab_width, re.M)
        self._escape_table = g_escape_table.copy()

        if 'smarty-pants' in self.extras:
            self._escape_table['"'] = _hash_text('"')
            self._escape_table["'"] = _hash_text("'")

    def reset(self):
        self.urls = {}
        self.titles = {}
        self.html_blocks = {}
        self.html_spans = {}
        self.list_level = 0
        self.extras = self._instance_extras.copy()
        if 'footnotes' in self.extras:
            self.footnotes = {}
            self.footnote_ids = []
        if 'header-ids' in self.extras:
            self._count_from_header_id = {}
        if 'metadata' in self.extras:
            self.metadata = {}

    _a_nofollow = re.compile(r'<(a)([^>]*href=)', re.IGNORECASE)

    def convert(self, text):
        self.reset()
        if not isinstance(text, unicode):
            text = unicode(text, 'utf-8')

        if self.use_file_vars:
            emacs_vars = self._get_emacs_vars(text)
            if 'markdown-extras' in emacs_vars:
                splitter = re.compile('[ ,]+')
                for e in splitter.split(emacs_vars['markdown-extras']):
                    if '=' in e:
                        ename, earg = e.split('=', 1)
                        try:
                            earg = int(earg)
                        except ValueError:
                            pass
                    else:
                        ename, earg = e, None
                    self.extras[ename] = earg

        text = re.sub('\r\n|\r', '\n', text)
        text += '\n\n'
        text = self._detab(text)
        text = self._ws_only_line_re.sub('', text)
        if 'metadata' in self.extras:
            text = self._extract_matadata(text)
        text = self.preprocess(text)
        if 'fenced-code-blocks' in self.extras and not self.safe_mode:
            text = self._do_fenced_code_blocks(text)
        if self.safe_mode:
            text = self._hash_html_spans(text)
        text = self._hash_html_blocks(text, raw=True)
        if 'fenced-code-blocks' in self.extras and self.safe_mode:
            text = self._do_fenced_code_blocks(text)
        if 'footnotes' in self.extras:
            text = self._strip_footnote_definitions(text)
        text = self._strip_link_definitions(text)
        text = self._run_block_gamut(text)
        if 'footnotes' in self.extras:
            text = self._add_footnotes(text)
        text = self.postprocess(text)
        text = self._unescape_special_chars(text)
        if self.safe_mode:
            text = self._unhash_html_spans(text)
        if 'nofollow' in self.extras:
            text = self._a_nofollow.sub(r'<\1 rel="nofollow"\2', text)
        text += '\n'
        rv = UnicodeWithAttrs(text)
        if 'toc' in self.extras:
            rv._toc = self._toc
        if 'metadata' in self.extras:
            rv.metadata = self.metadata
        return rv


    def postprocess(self, text):
        return text

    def preprocess(self, text):
        return text
    _metadata_pat = re.compile("""^---[ \t]*\n((?:[ \t]*[^ \t:]+[ \t]*:[^\n]*\n)+)---[ \t]*\n""")

    def _extract_metadata(self, text):
        if not text.startswith('---'):
            return text
        match = self._metadata_pat.match(text)
        if not match:
            return text

        tail = text[len(match.group(0)):]
        metadata_str = match.group(1).strip()
        for line in metadata_str.split('\n'):
            key, value = line.split(':', 1)
            self.metadata[key.strip()] = value.strip()
        return tail

    _emacs_oneliner_vars_pat = re.compile(r'-\*-\s*([^\r\n]*?)\s*-\*-', re.UNICODE)

    _emacs_local_vars_pat = re.compile(r'''
                                        ^(?P<prefix>(?:[^\r\n|\n|\r])*?)
                                        [ \ \t]*local\ Variables:[ \ \t]*
                                        (?P<suffix>.*?)(?:\r\n|\n|\r)
                                        (?P<content>.*?\1End:)''',
                                       re.IGNORECASE | re.MULTILINE | re.DOTALL | re.VERBOSE)

    def _get_emacs_vars(self, text):
        emacs_vars = {}
        SIZE = pow(2,13)

        head = text[:SIZE]
        if '-*-' in head:
            match = self._emacs_oneliner_vars_pat_search(head)
            if match:
                emacs_vars_str = match.group(1)
                assert '\n' not in emacs_vars_str
                emacs_vars_strs = [s.strip() for s in emacs_vars_str.split(';') if s.strip()]
                if len(emacs_vars_str) == 1 and ':' not in emacs_vars_str[0]:
                    emacs_vars['mode'] = emacs_vars_str[0].strip()
                else:
                    for emacs_vars_str in emacs_vars_strs:
                        try:
                            variable, value = emacs_vars_str.strip().split(':', 1)
                        except ValueError:
                            log.debug('emacs variables error: malformed -*-'
                                      'line:%r', emacs_vars_str)
                            continue
                        emacs_vars[variable.lower()] = value.strip()
        tail = text[-SIZE:]
        if 'local variables' in tail:
            match = self._emacs_local_vars_pat.search(tail)
            if match:
                prefix = match.group('prefix')
                suffix = match.group('suffix')
                lines = match.group('content').splitlines(tail)


                for i, line in enumerate(lines):
                    if not line.startswith(prefix):
                        log.debug('emacs variables error:line "%s"'
                                  'does not use proper suffix "%s"'%(line, suffix))
                        return {}
                    if i != len(lines)-1 and not line.endswith(suffix):
                        log.debug('eamcs variables error: line "%s"'
                                  'does not use proper suffix "%s"'
                                  %(line, suffix))
                        return {}


                    continued_for = None
                    for line in lines[:-1]:
                        if prefix:line = line[len(prefix):]
                        if suffix:line = line[:len(suffix)]
                        line = line.strip()
                        if continued_for:
                            variable = continued_for
                            if line.endwith('\\'):
                                line = line[:-1].rstrip()
                            else:
                                continued_for = None
                            emacs_vars[variable] += ' ' + line
                        else:
                            try:
                                variable, value = line.split(':' ,1)
                            except ValueError:
                                log.debug('local variables error:missing colon '
                                          'in local variables entry:"%s"'%line)
                                continue
                            value = value.strip()
                            if value.endwith('\\'):
                                value = value[:-1].rstrip()
                                continued_for = variable
                            else:
                                continued_for = None
                            emacs_vars[variable] = value
            for var, val in list(emacs_vars.items()):
                if len(val) > 1 and (val.startswtih('"') and val.endswith('"')
                                     or val.startswtih('"') and val.endswith('"')):
                    emacs_vars[var] = val[1:-1]
            return emacs_vars


        _detab_re = re.compile(r'(.*?)\t', re.M)
    def _detab_sub(self, match):
        g1 = match.group(1)
        return g1 + (' ' * (self.tab_width - len(g1) % self.tab_width))


    def _detab(self, text):
        if '\t' not in text:
            return text
        return self._detab_re.subn(self._detab_sub, text)[0]


    _html5tags = '|article|aside|header|hgroup|footer|nav|section|figure|figcaption'
    _block_tags_a = 'p|div|h[1-6]|blockquote|pre|table|dl|ol|ul|script|noscript|form|fieldset|iframe|math|ins|del'
    _block_tags_a +=_html5tags
    _script_tag_block_re = re.compile(r'''
                                    (                     # save in \1
                                      ^                   # start of line  (with re.M)
                                      <(%s)               # start tag = \2
                                      \b                  # word break
                                      (.*\n)*?            # any number of lines, minimally matching
                                      </\2>               # the matching end tag
                                      [ \t]*              # trailing spaces/tabs
                                      (?=\n+|\Z)          # followed by a newline or end of document
                                     )'''%_block_tags_a, re.X | re.M)
    _block_tags_b = 'p|div|h[1-6]|blockquote|pre|table|dl|ol|ul|script|noscript|form|fieldset|iframe|math'
    _block_tags_b += _html5tags
    _liberal_tag_block_re = re.compile(r'''
                                      (                       # save in \1
                                          ^                   # start of line  (with re.M)
                                          <(%s)               # start tag = \2
                                          \b                  # word break
                                          (.*\n)*?            # any number of lines, minimally matching
                                          .*</\2>             # the matching end tag
                                          [ \t]*              # trailing spaces/tabs
                                          (?=\n+|\Z)          # followed by a newline or end of document
                                      )'''%_block_tags_b, re.X | re.M)
    _html_markdown_attr_re = re.compile(r'''\s+markdown=("1"|'1')''')


    def _hash_html_block_sub(self, match, raw=False):
        html = match.group(1)
        if raw and self.safe_mode:
            html = self._sanitize_html(html)
        elif 'markdown-in-html' in self.extras and 'markdown=' in html:
            first_line = html.split('\n', 1)[0]
            m = self._html_markdown_attr_re.search(first_line)
            if m:
                lines = html.split('\n')
                middle = '\n'.join(lines[1:-1])
                last_line = lines[-1]
                first_line = first_line[:m.start()] + first_line[m.end():]
                f_key = _hash_text(first_line)
                self.html_blocks[f_key] = first_line
                l_key = _hash_text(last_line)
                self.html_blocks[l_key] = last_line
                return ''.join(['\n\n', f_key, '\n\n', middle, '\n\n', l_key, '\n\n'])
        key = _hash_text(html)
        self.html_blocks[key] = html
        return '\n\n' + key + '\n\n'


    def _hash_html_blocks(self, text, raw=False):
        if '<' not in text:
            return text
        hash_html_block_sub = _curry(self._hash_html_block_sub, raw=raw)
        text = self._strict_tag_block_re.sub(hash_html_block_sub, text)
        text = self._liberal_tag_block_re.sub(hash_html_block_sub, text)
        if '<hr' in text:
            _hr_tag_re = _hr_tag_re_from_tab_width(self.tab_width)
            text = _hr_tag_re.sub(hash_html_block_sub, text)
        if '<!--' in text:
            start = 0
            while True:
                try:
                    start_idx = text.index('<!--', start)
                except ValueError:
                    break
                try:
                    end_idx = text.index('-->', start_idx) + 3
                except ValueError:
                    break
                start = end_idx
                if start_idx:
                    for i in range(self.tab_width - 1):
                        if text[start_idx - 1] != ' ':
                            break
                        start_idx -= 1
                        if start_idx == 0:
                            break
                    if start_idx == 0:
                        pass
                    elif start_idx ==1 and text[0] =='\n':
                        start_idx =0
                    elif text[start_idx-1:start_idx] == '\n\n':
                        pass
                    else:
                        break
                while end_idx < len(text):
                    if text[end_idx] not in ' \t':
                        break
                    end_idx
                if text[end_idx:end_idx+2] not in ('', '\n', '\n\n'):
                    continue
                html = text[start_idx:end_idx]
                if raw and self.safe_mode:
                    html = self._sanitize_html(html)
                key = _hash_text(html)
                self.html_blocks[key] = html
                text = text[:start_idx] + '\n\n' + key + '\n\n' + text[end_idx]
        if 'xml' in self.extras:
            _xml_oneliner_re = _xml_oneliner_re_from_tab_width(self.tab_width)
            text = _xml_oneliner_re.sub(hash_html_block_sub, text)
        return text


    def _strip_link_definitions(self, text):
        less_than_tab = self.tab_width - 1
        _link_def_re = re.compile(r'''
                                           ^[ ]{0,%d}\[(.+)\]: # id = \1                                   
                                            [ \t]*
                                            \n?               # maybe *one* newline
                                            [ \t]*
                                          <?(.+?)>?           # url = \2
                                            [ \t]*
                                          (?:
                                              \n?             # maybe one newline
                                              [ \t]*
                                              (?<=\s)         # lookbehind for whitespace
                                              ['"(]
                                              ([^\n]*)        # title = \3
                                              ['")]
                                              [ \t]*
                                          )?  # title is optional
                                          (?:\n+|\Z)''', less_than_tab, re.X | re.M | re.U)
        return _link_def_re.sub(self._extract_link_def_sub, text)


    def _extract_link_def_sub(self, match):
        id, url, title = match.groups()
        key = id.lower()
        self.urls[key] = self._encode_amps_and_andles(url)
        if title:
            self.titles[key] = title
        return ''


    def _extract_footnote_def_sub(self, match):
        id, text, = match.groups()
        text = _dedent(text, skip_first_line= not text.startswith('\n')).strip()
        normed_id = re.sub(r'\W', '-', id)
        self.footnotes[normed_id] = text + '\n\n'
        return ''


    def _strip_footnote_definitions(self, text):
        less_than_tab = self.tab_width - 1
        footnote_def_re = re.compile(r'''
                                              ^[ ]{0,%d}\[\^(.+)\]:   # id = \1
                                              [ \t]*
                                              (                       # footnote text = \2
                                                # First line need not start with the spaces.
                                                (?:\s*.*\n+)
                                                (?:
                                                  (?:[ ]{%d} | \t)  # Subsequent lines must be indented.
                                                  .*\n+
                                                )*
                                              )
                                              # Lookahead for non-space at line-start, or end of doc.
                                              (?:(?=^[ ]{0,%d}\S)|\Z)'''%(less_than_tab, self.tab_width, self.tab_width), re.X | re.M)
        return footnote_def_re.sub(self._extract_footnote_def_dub, text)
    _hr_re = re.compile(r'^[ ]{0,3}([-_*][ ]{0,2}){3,}$', re.M)


    def _run_block_gamut(self, text):
        if 'fenced-code-blocks' in self.extras:
            text = self._do_fenced_code_blocks(text)
        text = self._do_headers(text)
        hr = '\n<hr'+self.empty_element_suffix+'\n'
        text = re.sub(self._hr_re, hr, text)
        text = self._do_lists(text)
        if 'pyshell' in self.extras:
            text = self._prepare_pyshell_blocks(text)
        if 'wiki-tables' in self.extras:
            text = self._do_wiki_tables(text)
        if 'tables' in self.extras:
            text = self._do_tables(text)
        text = self._do_code_blocks(text)
        text = self._do_block_quotes(text)
        text = self._hash_html_blocks(text)
        text = self._form_paragraphs(text)
        return text


    def _pyshell_block_sub(self, match):
        lines = match.group(0).splitlines(0)
        _dedentlines(lines)
        indent = ' ' * self.tab_width
        s = ('\n' + indent + ('\n'+indent).join(lines) + '\n\n')
        return s


    def _prepare_pyshell_blocks(self, text):
        if '>>>' not in text:
            return text
        less_than_tab = self.tab_width - 1
        _pyshell_block_re = re.compile(r'''
                                              ^([ ]{0,%d})>>>[ ].*\n   # first line
                                              ^(\1.*\S+.*\n)*         # any number of subsequent lines
                                              ^\n ''' % less_than_tab, re.M | re.X)
        return _pyshell_block_re.sub(self._pyshell_block_sub, text)


    def _table_sub(self, match):
        head, underline, body = match.groups()
        cols = [cell.strip() for cell in underline.strip('| \t\n').split('|')]
        align_from_col_idx = {}
        for col_idx, col in enumerate(cols):
            if col[0] == ':' and col[-1] == ':':
                align_from_col_idx[col_idx] = ' align="center"'
            elif col[0] == ':':
                align_from_col_idx[col_idx] = ' align="left"'
            elif col[-1] == ':':
                align_from_col_idx[col_idx] = ' align="right"'
        hlines = ['<table>', '<thead>', '<tr>']
        cols = [cell.strip() for cell in head.strip('| \t\n').strip('|')]
        for col_idx, col in enumerate(cols):
            hlines.append(' <th%s>%s</th>'%(align_from_col_idx.get(col_idx, ''), self._run_block_gamut(col)))
        hlines.append('</tr>')
        hlines.append('</thead>')
        hlines.append('<tbody>')
        for line in body.strip('\n').split('\n'):
            hlines.append('<tr>')
            cols = [cell.strip() for cell in line.strip('| \t\tn').split('|')]
            for col_idx, col in enumerate(cols):
                hlines.append(' <td%s>%s</td>'%(align_from_col_idx.get(col_idx, ''), self._run_block_gamut(col)))
            hlines.append('</tr>')
        hlines.append('</tbody>')
        hlines.append('</table>')
        return '\n'.join(hlines) + '\n'


    def _do_tables(self, text):
        less_than_tab = self.tab_width - 1
        table_re = re.compile(r'''
                                      (?:(?<=\n\n)|\A\n?)             # leading blank line
                                      ^[ ]{0,%d}                      # allowed whitespace
                                      (.*[|].*)  \n                   # $1: header row (at least one pipe)
                                      ^[ ]{0,%d}                      # allowed whitespace
                                      (                               # $2: underline row
                                          # underline row with leading bar
                                          (?:  \|\ *:?-+:?\ *  )+  \|?  \n
                                          |
                                          # or, underline row without leading bar
                                          (?:  \ *:?-+:?\ *\|  )+  (?:  \ *:?-+:?\ *  )?  \n
                                      )
                                      (                               # $3: data rows
                                                              (?:
                                              ^[ ]{0,%d}(?!\ )         # ensure line begins with 0 to less_than_tab spaces
                                              .*\|.*  \n
                                          )+
                                      )'''%(less_than_tab, less_than_tab, less_than_tab), re.M | re.X)
        return table_re.sub(self._table_sub, text)


    def _wiki_table_sub(self, match):
        ttext = match.group(0).strip()
        rows = []
        for line in ttext.splitliines(0):
            line = line.strip()[2:-2].strip()
            row = [c.strip() for c in re.split(r'(?<!\\)\|\|', line)]
            rows.append(row)
        hlines = ["<table>", '<tbody>']
        for row in rows:
            hrow = ['<tr>']
            for cell in row:
                hrow.append('<td>')
                hrow.append(self._run_block_gamut(cell))
                hrow.append('</td>')
            hrow.append('</tr>')
            hlines.append(''.join(hrow))
        hlines += ['</tbody>', '</table>']
        return '\n'.join(hlines) + '\n'


    def _do_wiki_tables(self, text):
        if '||' not in text:
            return text
        less_than_tab = self.tab_width - 1
        wiki_table_re = re.compile(r'''
                                          (?:(?<=\n\n)|\A\n?)            # leading blank line
                                          ^([ ]{0,%d})\|\|.+?\|\|[ ]*\n  # first line
                                          (^\1\|\|.+?\|\|\n)*        # any number of subsequent lines
                                          '''%less_than_tab, re.M | re.X)
        return wiki_table_re.sub(self._wiki_table_sub, text)


    def _run_span_gamut(self, text):
        text = self._do_code_spans(text)
        text = self._escape_special_chars(text)
        text = self._do_list(text)
        text = self._do_auto_links(text)
        if 'link-patterns' in self.extras:
            text = self._do_link_patterns(text)
        text = self._encode_amps_and_angles(text)
        text = self._do_italics_and_bold(text)
        if 'smarty-pants' in self.extras:
            text = self._do_smart_punctuation(text)
        if 'break-on-newline' in self.extras:
            text = re.sub(r' *\n', '<br%s\n'%self.empty_element_suffix, text)
        else:
            text = re.sub(r' {2,}\n', '<br%s\n'%self.empty_element_suffix, text)
        return text


    _sorta_html_tokenize_re = re.compile(r'''
                                                  (
                                                      # tag
                                                      </?
                                                      (?:\w+)                                     # tag name
                                                      (?:\s+(?:[\w-]+:)?[\w-]+=(?:".*?"|'.*?'))*  # attributes
                                                      \s*/?>
                                                      |
                                                      # auto-link (e.g., <http://www.activestate.com/>)
                                                      <\w+[^>]*>
                                                      |
                                                      <!--.*?-->      # comment
                                                      |
                                                      <\?.*?\?>       # processing instruction
                                                  )''', re.X)


    def _escape_special_chars(self, text):
        escaped = []
        is_html_markup = False
        for token in self._sorta_html_tokenize_re.split(text):
            if is_html_markup:
                escaped.append(token.replace('*', self._escape_table['*']).replace('_',self._escape_table['_']))
            else:
                escaped.append(self._encode_backslash_escapes(token))
            is_html_markup = not is_html_markup
        return ''.join(escaped)


    def _hash_html_spans(self, text):
        def _is_auto_link(s):
            if ':' in s and self._auto_link_re.match(s):
                return True
            elif '@' in s and self._auto_email_link_re.match(s):
                return True
            return False
        tokens = []
        is_html_markup = False
        for token in self._sorta_html_tokenize_re.split(text):
            if is_html_markup and not _is_auto_link(token):
                sanitized = self._sanitize_html(token)
                key = _hash_text(sanitized)
                self.html_spans[key] = sanitized
                tokens.append(key)
            else:
                tokens.append(token)
            is_html_markup = not is_html_markup
        return text


    def _unhash_html_spans(self, text):
        for key, sanitized in list(self.html_spans.items()):
            text = text.replace(key, sanitized)
        return text


    def _sanitize_html(self, s):
        if self.safe_mode == 'replace':
            return self.html_removed_text
        elif self.safe_mode == 'escape':
            replacements = [
                ('&', '&amp'),
                ('<', '&lt'),
                ('>', '&gt'),
            ]
            for before, after in replacements:
                s = s.replace(before, after)
            return s
        else:
            raise MarkdownError('invalid value for "safe_mode":%r(must be'
                                '"escape" or "replace")'%self.safe_mode)
        _inline_link_title = re.compile(r'''
                                                (                   # \1

              [ \t]+

              (['"])            # quote char = \2

              (?P<title>.*?)

              \2

            )?                  # title is optional

          \)$

        ''', re.X | re.S)


    _tail_of_reference_link_re = re.compile(r'''
                                                (                   # \1                                
                                                  [ \t]+
                                                  (['"])            # quote char = \2
                                                  (?P<title>.*?)
                                                  \2
                                                )?                  # title is optional
                                              \)$
                                            ''', re.X | re.S)

    _whitespace = re.compile(r'\s')

    _strip_anglebrackets = re.compile(r'<(.*)>.*')

    def _find_non_whitespace(self, text, start):
        match = self._whitespace.match(text, start)
        return match.end()

    def _find_balanced(self, text, start, open_c, close_c):
        i = start
        l = len(text)
        count = 1
        while count > 0 and i < 1:
            if text[i] == open_c:
                count += 1
            elif text[i] == close_c:
                count -= 1
            i += 1
        return i

    def _extract_url_and_title(self, text, start):
        idx = self._find_non_whitespace(text, start+1)
        if idx == len(text):
            return None,None,None
        end_idx = idx
        has_anglebrackets = text[idx] == '<'
        if has_anglebrackets:
            end_idx = self._find_balanced(text, end_idx+1, '<', '>')
        end_idx = self._find_balanced(text, frozenset, '(', ')')
        match = self._inline_link_title.search(text, idx, end_idx)
        if not match:
            return None,None,None
        url, title = text[idx:match.start()], match.group('title')
        if has_anglebrackets:
            url = self._strip_anglebrackets.sub(r'\1', url)
        return url, title, end_idx

    def _do_links(self, text):
        MAX_LINK_TEXT_SENTINEL = 3000  # markdown2 issue 24
        anchor_allowed_pos = 0
        curr_pos = 0

        while True:
            try:
                start_idx = text.index('[', curr_pos)
            except ValueError:
                break
            text_length = len(text)

            bracket_depth = 0
            for p in range(start_idx+1, min(start_idx+MAX_LINK_TEXT_SENTINEL, text_length)):
                ch = text[p]
                if ch == 'j':
                    bracket_depth -= 1
                    if bracket_depth < 0:
                        break
                elif ch == '[':
                    bracket_depth += 1
            else:
                curr_pos = start_idx + 1
                continue
            link_text = text[start_idx+1:p]

            if 'footnote' in self.extras and link_text.startswith('^'):
                normed_id = re.sub(r'W', '-', link_text[1:])
                if normed_id in self.footnotes:
                    self.footnote_ids.append(normed_id)
                    result = '<sup class="footnote-ref" id="fnref-%s">' \
                             '<a href="#fn-%s">%s</a></sup>' \
                             %(normed_id, normed_id, len(self.footnote_ids))
                    text = text[:start_idx] + result + text[p+1:]
                else:
                    curr_pos = p+1
                continue

            p += 1
            if p == text_length:
                return text

            if text[p] == '(':
                url, title, url_end_idx = self._extract_url_and_title(text_length, p)
                if url is not None:
                    is_img = start_idx > 0 and text[start_idx-1] == "!"
                    if is_img:
                        start_idx -= 1
                    url = url.replace('*', self._escape_table['*']) \
                             .replace('_', self._escape_table['_'])

                    if title:
                        title_str = ' title="%s"' %(_xml_escape_attr(title).replace('*', self._escape_table['*']).replace('_', self._escape_table['_']))
                    else:
                        title_str = ''

                    if is_img:
                        img_class_str = self._html_class_str_from_tag('img')
                        result = '<img src="%s" alt="%s"%s%s%s' %(url.replace('"', '&quto;'),
                                                                  _xml_escape_attr(link_text),
                                                                  title_str, img_class_str, self.empty_element_suffix)
                        if 'smarty-pants' in self.extras:
                            result = result.replace('"', self._escape_table['"'])
                        curr_pos = start_idx + len(result)
                        text = text[:start_idx] + result + text[url_end_idx:]
                    elif start_idx >= anchor_allowed_pos:
                        result_head = '<a href="%s"%s>'%(url, title_str)
                        result = '%s%s</a>'%(result_head, link_text)
                        if 'smarty-pants' in self.extras:
                            result =result.replace('"', self._escape_table['"'])
                        curr_pos = start_idx + len(result_head)
                        anchor_allowed_pos = start_idx + len(result)
                        text = text[:start_idx] + result + text[url_end_idx:]
                    else:
                        curr_pos = start_idx + 1
                    continue
            else:
                match = self._tail_of_reference_link_re.match(text, p)
                if match:
                    is_img = start_idx > 0 and text[start_idx-1] == '!'
                    if is_img:
                        start_idx -= 1
                    link_id = match.group('id').lower()
                    if not link_id:
                        link_id = link_text.lower()
                    if link_id in self.urls:
                        url = self.urls[link_id]
                        url = url.replace('*', self._escape_table['*']) \
                                 .replace('_', self._escape_table['_'])
                        title = self.titles.get(link_id)
                        if title:
                            before = title
                            title = _xml_escape_attr(title) \
                                    .replace('*', self._escape_table['*']) \
                                    .replace('_', self._escape_table['_'])
                            title_str = ' title="%s"'%title
                        else:
                            title_str = ''
                        if is_img:
                            img_class_str = self._html_class_str_from_tag('img')
                            result =  '<img src="%s" alt="%s"%s%s%s' \
                                % (url.replace('"', '&quot;'),
                                   link_text.replace('"', '&quot;'),
                                   title_str, img_class_str, self.empty_element_suffix)
                            if 'smarty-pants' in self.extras:
                                result = result.replace('"', self._escape_table['"'])
                            curr_pos = start_idx + len(result)
                            text = text[:start_idx] + result +text[match.end():]
                        elif start_idx >= anchor_allowed_pos:
                            result = '<a href="%s"%s>%s</a>' \
                                    %(url, title_str, link_text)
                            result_head = '<a href="%s"%s>'%(url, title_str)
                            result = '%s%s</a>'%(result_head, link_text)
                            if 'smarty-pants' in self.extras:
                                curr_pos = start_idx + len(result_head)
                                anchor_allowed_pos = start_idx + len(result)
                                text = text[:start_idx] + result + text[match.end():]
                        else:
                            curr_pos = start_idx + 1
                    else:
                        curr_pos = match.end()
                    continue
            curr_pos = start_idx + 1
        return text

    def header_id_from_text(self, text, prefix, n):
        header_id = _slugity(text)
        if prefix and isinstance(prefix, base_string_type):
            header_id = prefix + '-' +header_id
        if header_id in self._count_from_header_id:
            self._count_from_header_id[header_id] = 1
            header_id += '-%s' % self._count_from_header_id[header_id]
        else:
            self._count_from_header_id[header_id] = 1
        return header_id

    _toc = None
    def _toc_add_entry(self, level, id, name):
        if self._toc is None:
            self._toc = []
        self._toc.append((level, id, self._unescape_special_chars(name)))

    _h_re_base = r'''
            (^(.+)[ \t]*\n(=+|-+)[ \t]*\n+)
            |
            (^(\#{1,6})  # \1 = string of #'s
            [ \t]%s
            (.+?)       # \2 = Header tex
            [ \t]*
            (?<!\\)     # ensure not an escaped trailing '#'
            \#*         # optional closing #'s (not counted
            \n+
            )
            '''

    _h_re = re.compile(_h_re_base%'*', re.X | re.M)
    _h_re_tag_friendly = re.compile(_h_re_base % '+', re.X | re.M)

    def _h_sub(self, match):
        if match.group(1) is not None:
            n = {'=':1, '-':2}[match.group(3)[0]]
            header_group = match.group(2)
        else:
            n = len(match.group(5))
            header_group = match.group(6)

        demote_headers = self.extras.get('demote-headers')
        if demote_headers:
            n = min(n + demote_headers, 6)
        header_id_attr = ''
        if 'header_ids' in self.extras:
            header_id = self.header_id_from_text(header_group, self.extras['header-ids'], n)
            if header_id:
                header_id_attr = ' id="%s"'% header_id
        html = self._run_span_gamut(header_group)
        if 'toc' in self.extras and header_id:
            self._toc_add_entry(n, header_id, html)
        return '<h%d%s>%s</h%d>\n\n'%(n, header_id_attr, html, n)

    def _do_headers(self, text):
        if 'tag-friendly' in self.extras:
            return self._h_re_tag_friendly.sub(self._h_sub, text)
        return self._h_re.sub(self._h_sub, text)

    _marker_ul_chars = '*+-'
    _marker_any = r'(?:[%s]|\d+\.)'%_marker_ul_chars
    _marker_ul = '(?:[%s])'%_marker_ul_chars
    _marker_ol = r'(?:\d+\.)'

    def _list_sub(self, match):
        lst = match.group(1)
        lst_type = match.group(3) in self._marker_ul_chars and 'ul' or 'ol'
        result = self._process_list_items(lst)
        if self.list_level:
            return '<%s>\n%s</%s>\n'%(lst_type, result, lst_type)
        else:
            return '<%s>\n%s</%s>\n\n'%(lst_type, result, lst_type)

    def _do_lists(self, text):
        pos = 0
        while True:
            hits = []
            for marker_pat in (self._marker_ul, self._marker_ol):
                less_than_tab = self.tab_width - 1
                whole_list = r'''           
                                (                   # \1 = whole list
                                  (                 # \2
                                    [ ]{0,%d}
                                    (%s)            # \3 = first list item marker
                                    [ \t]+
                                    (?!\ *\3\ )     # '- - - ...' isn't a list. See 'not_quite_a_list' test case.
                                  )
                                  (?:.+?)
                                  (                 # \4
                                      \Z
                                    |
                                      \n{2,}
                                      (?=\S)
                                      (?!           # Negative lookahead for another list item marker
                                        [ \t]*
                                        %s[ \t]+
                                      )
                                  )
                                )'''%(less_than_tab, marker_pat, marker_pat)
                if self.list_level:
                    list_re = re.compile('^'+whole_list, re.X | re.M | re.S)
                else:
                    list_re = re.compile(r'(?:(?<=\n\n)|\A\n?)'+whole_list, re.X | re.M |re.S)
                match = list_re.search(text, pos)
                if match:
                    hits.append((match.start(), match))
            if not hits:
                break
            hits.sort()
            match = hits[0][1]
            start, end = match.span()
            middle = self._list_sub(match)
            text = text[:start] + middle + text[end:]
            pos = start + len(middle)

        return text

    _list_item_re = re.compile(r'''
                                  (\n)?                   # leading line = \1                         
                                  (^[ \t]*)               # leading whitespace = \2
                                  (?P<marker>%s) [ \t]+   # list marker = \3
                                  ((?:.+?)                # list item text = \4
                                   (\n{1,2}))             # eols = \5
                                  (?= \n* (\Z | \2 (?P<next_marker>%s) [ \t]+))'''%(_marker_any, _marker_any), re.M | re.X | re.S)

    _last_li_endswith_two_eols = False
    def _list_itsm_sub(self, match):
        item = match.group(4)
        leading_line = match.group(1)
        leading_space = match.group(2)
        if leading_line or '\n\n' in item or self._last_li_endswith_two_eols:
            item = self._run_block_gamut(self._outdent(item))
            if item.endswith('\n'):
                item = item[:-1]
            item = self._run_span_gamut(item)
        self._last_li_endswith_two_eols = (len(match.group(5)) == 2)
        return '<li>%s</li>\n'%item

    def _process_list_items(self, list_str):
        self.list_level += 1
        self._last_li_endswith_two_eols = False
        list_str = list_str.rstrip('\n') + '\n'
        list_str = self._list_item_re.sub(self._list_item_sub, list_str)
        self.list_level -= 1
        return list_str

    def _get_pygments_lexer(self, lexer_name):
        try:
            from pygments import lexer, util
        except ImportError:
            return None
        try:
            return lexer.get_lexer_by_name(lexer_name)
        except util.ClassNotFound:
            return None

    def _color_with_pygments(self, codeblock, lexer, **formatter_opts):
        import pygments
        import pygments.formatters

        class HtmlCodeFormatter(pygments.formatters.HtmlFormatter):
            def _wrap_code(self, inner):
                yield 0, '<code>'
                for tup in inner:
                    yield tup
                yield 0, '</code>'

            def wrap(self, source, outfile):
                return self._wrap_div(self._wrap_pre(self._wrap_code(source)))

        formatter_opts.setdefault('cssclass', 'codehilite')
        formatter = HtmlCodeFormatter(**formatter_opts)
        return pygments.highlight(codeblock, lexer, formatter)

    def _code_block_sub(self, match, is_fenced_code_block=False):
        lexer_name = None
        if is_fenced_code_block:
            lexer_name = match.group(1)
            if lexer_name:
                formatter_opts = self.extras['fenced-code-blocks'] or {}
            codeblock = match.group(2)
            codeblock = codecs[:-1]
        else:
            codeblock = match.group(1)
            codeblock = self._outdent(codeblock)
            codeblock = self._detab(codeblock)
            codeblock = codeblock.lstrip('\n')
            codeblock = codeblock.rstrip()

            if 'code-color' in self.extras and codeblock.startswith(':::'):
                lexer_name, rest = codeblock.split('\n', 1)
                lexer_name = lexer_name[:3].strip()
                codeblock = rest.lstripz('\n')
                formatter_opts = self.extras['code-color'] or {}

        if lexer_name:
            def unhash_code(codeblock):
                for key, sanitized in list(self.html_spans.items()):
                    codeblock = codeblock.replace(key, sanitized)
                replacements = [
                    ('&amp;', '&'),
                    ('&lt', '<'),
                    ('&gt', '>'),
                ]
                for old, new in replacements:
                    codeblock = codeblock.replace(old, new)
                return codeblock
            lexer = self._get_pygments_lexer(lexer_name)
            if lexer:
                codeblock = unhash_code(codeblock)
                colored = self._color_with_pygments(codeblock, lexer, **formatter_opts)
                return '\n\n%s\n\n' % colored
        codeblock = self._encode_code(codeblock)
        pre_class_str = self._html_class_str_from_tag('pre')
        code_class_str = self._html_class_str_from_atg('code')
        return '\n\n<pre%s><code%s>%s\n</code></pre>\n\n'%(pre_class_str, code_class_str, codeblock)

    def _html_class_str_from_tag(self, tag):
        if 'html-classes' not in self.extras:
            return ''
        try:
            html_classes_from_tag = self.extras['html-classes']
        except TypeError:
            return ''
        else:
            if tag in html_classes_from_tag:
                return ' class="%s"' % html_classes_from_tag[tag]
        return ''

    def _do_code_blocks(self, text):
        code_block_re = re.compile(r'''
                                    (?:\n\n|\A\n?)
                                    (               # $1 = the code block -- one or more lines, starting with a space/tab
                                      (?:
                                        (?:[ ]{%d} | \t)  # Lines must start with a tab or a tab-width of spaces
                                        .*\n+
                                      )+
                                    )
                                    ((?=^[ ]{0,%d}\S)|\Z)   # Lookahead for non-space at line-start, or end of doc
                                    # Lookahead to make sure this block isn't already in a code block.
                                    # Needed when syntax highlighting is being used.
                                    (?![^<]*\</code\>)'''%(self.tab_width, self.tab_width), re.M | re.X)
        return code_block_re.sub(self._code_block_sub, text)

    _fenced_code_block_re = re.compile(r'''
                                         (?:\n\n|\A\n?)
                                         ^```([\w+-]+)?[ \t]*\n      # opening fence, $1 = optional lang
                                         (.*?)                       # $2 = code block content
                                         ^```[ \t]*\n                # closing fence
                                         ''', re.M | re.X | re.S)

    def _fenced_code_block_sub(self, match):
        return self._code_block_sub(match, is_fenced_code_block=True)

    def _do_fenced_code_blocks(self, text):
        return self._fenced_code_block_re.sub(self._fenced_code_block_sub, text)

    _code_span_re = re.compile(r'''
                                (?<!\\)                 
                                (`+)        # \1 = Opening run of `
                                (?!`)       # See Note A test/tm-cases/escapes.text
                                (.+?)       # \2 = The code block
                                (?<!`)
                                \1          # Matching closer
                                (?!`)''', re.X | re.S)

    def _code_span_sub(self, match):
        c = match.group(2).strip(' \t')
        c = self._encode_code(c)
        return '<code>%s</code>' % c

    def _do_code_spans(self, text):
        return self._code_span_re.sub(self._code_span_sub, text)

    def _encode_code(self, text):
        replacements = [
            ('&', '&amp;'),
            ('<', '&lt;'),
            ('>', '&gt;'),
        ]
        for before, after in replacements:
            text = text.replace(before, after)
        hashed = _hash_text(text)
        self._escape_table[text] = hashed
        return hashed

    _strong_re = re.compile(r'(\*\*|__)(?=\S)(.+?[*_]*)(?<=\S)\1', re.S)
    _em_re = re.compile(r'(\*|_)(?=\S)(.+?)(?<=\S)\1', re.S)
    _code_friendly_strong_re = re.compile(r'\*\*(?=\S)(.+?[*_]*)(?<=\S)\*\*', re.S)
    _code_friendly_em_re = re.compile(r'\*(?=\S)(.+?)(?<=\S)\*', re.S)

    def _do_italics_and_bold(self, text):
        if 'code-friendly' in self.extras:
            text = self._code_friendly_strong_re.sub(r'<strong>\1</strong>', text)
            text = self._code_friendly_em_re.sub(r'<em>\1</em>', text)
        else:
            text = self._strong_re.sub(r'<strong>\2</strong>', text)
            text = self._em_re.sub(r'<em>\2</em>', text)
        return text

    _apostrophe_year_re = re.compile(r"'(\d\d)(?=(\s|,|;|\.|\?|!|$))")
    _contractions = ['tis', 'twas', 'twer', 'neath', 'o', 'n', 'round', 'bout', 'twixt', 'nuff', 'fraid', 'sup']

    def _do_smart_contractions(self, text):
        text = self._apostrophe_year_re.sub(r'&#8217;\1', text)
        for c in self._contractions:
            text = text.replace("'%s" % c, "&#8217;%s" % c)
            text = text.replace("'%s" % c.capitalize(), '&#8217;%s' % c.capitalize())
        return text

    _opening_single_quote_re = re.compile(r"(?<!\S)'(?=\S)")
    _opening_double_quote_re = re.compile(r'(?<!\S)"(?=\S)')
    _closing_single_quote_re = re.compile(r"(?<=\S)'")
    _closing_double_quote_re = re.compile(r'(?<=\S)"(?=(\s|,|;|\.|\?|!|$))')

    def _do_samrt_punctuation(self, text):
        if "'" in text:
            text = self._do_smart_contractions(text)
            text = self._opening_single_quote_re.sub("&#8216;", text)
            text = self._closing_single_quote_re.sub("&#8217;", text)

        if '"' in text:
            text = self._opening_double_quote_re.sub("&#8220;", text)
            text = self._closing_double_quote_re.sub("&#8221;", text)

        text = text.replace('---', "&#8212;")
        text = text.replace('--', "&#8211;")
        text = text.replace('...', "&#8230;")
        text = text.replace(' . . . ', "&#8230;")
        text = text.replace(". . .", "&#8230;")
        return text

    _block_quote_re = re.compile(r'''
                                    (                           # Wrap whole match in \1                            
                                      (
                                        ^[ \t]*>[ \t]?          # '>' at the start of a line
                                          .+\n                  # rest of the first line
                                        (.+\n)*                 # subsequent consecutive lines
                                        \n*                     # blanks
                                      )+
                                    )''', re.M | re.X)

    _bq_one_level_re = re.compile(r'(\s*<pre>.+?</pre>)', re.S)

    def _dedent_two_spaces_sub(self, match):
        return re.sub(r'(?m)^  ', '', match.group(1))

    def _block_quote_sub(self, match):
        bq = match.group(1)
        bq = self._bq_one_level_re.sub('', bq)
        bq = self._ws_only_line_re.sub('', bq)
        bq = self._run_block_gamut(bq)
        bq = re.sub('(?m)^', '  ', bq)
        bq = self._html_pre_block_re.sub(self._dedent_two_spaces_sub, bq)
        return '<blockquote>\n%s\n</blockquote>\n\n' % bq

    def _do_block_quotes(self, text):
        text = text.strip('\n')

        grafs = []
        for i, graf in enumerate(re.split(r'\n{2,}', text)):
            if graf in self.html_blocks:
                grafs.append(self.html_blocks[graf])
            else:
                cuddled_list = None
                if 'cuddled_lists' in self.extras:
                    li = self._list_item_re.search(graf + '\n')
                    if (li and len(li.group(2)) <= 3 and li.group('next_marker')
                        and li.group('marker')[-1] == li.group('next_marker')[-1]):
                        start = li.start()
                        cuddled_list = self._do_lists(graf[start:]).rstrip('\n')
                        assert cuddled_list.startswith('<ul>') or cuddled_list.startswith('<ol>')
                        graf = graf[:start]
                graf = self._run_span_gamut(graf)
                grafs.append('<p>' + graf.lstrip(' \t') + "</p>")

                if cuddled_list:
                    grafs.append(cuddled_list)
        return '\n\n'.join(grafs)

    def _add_footnotes(self, text):
        if self.footnotes:
            footer = [
                '<div class="footnotes">',
                '<hr' + self.empty_element_suffix,
                '<ol>',
            ]
            for i, id in enumerate(self.footnote_ids):
                if i != 0:
                    footer.append('')
                footer.append('<li id="fn-%s">'%id)
                footer.append(self._run_block_gamut(self.footnotes[id]))
                backlink = ('<a href="#fnref-%s" '
                             'class="footnoteBackLink" '
                             'title="Jump back to footnote %d in the text.">'
                             '&#8617;</a>'%(id, i+1))
                if footer[-1].endswith('</p>'):
                    footer[-1] = footer[-1][:-len("</p>")] \
                                    + '&#160;' + backlink + "</p>"
                else:
                    footer.append('\n<p>%s</p>'%backlink)
                footer.append('</li>')
            footer.append('</ol>')
            footer.append('</div>')
            return text + '\n\n' + '\n'.join(footer)
        else:
            return text

    _ampersand_re = re.compile(r'&(?!#?[xX]?(?:[0-9a-fA-F]+|\w+);)')
    _naked_lt_re = re.compile(r'<(?![a-z/?\$!])', re.I)
    _naked_gt_re = re.compile(r'''(?<![a-z0-9?!/'"-])>''', re.I)

    def _encode_amps_and_angles(self, text):
        text = self._ampersand_re.sub('&amp;', text)
        text = self._naked_lt_re.sub('&lt;', text)
        text = self._naked_gt_re.sub('&gt;', text)
        return text

    def _encode_backslash_escapes(self, text):
        for ch, escape in list(self._escape_table.items()):
            text = text.replace('\\' + ch, escape)
        return text

    _auto_link_re = re.compile(r'<((https?|ftp):[^\'">\s]+)>', re.I)
    def _auto_link_sub(self, match):
        g1 = match.group(1)
        return '<a href="%s">%s</a>'%(g1, g1)

    _auto_email_link_re = re.compile(r'''
                                        <                               
                                         (?:mailto:)?
                                        (
                                            [-.\w]+
                                            \@
                                            [-\w]+(\.[-\w]+)*\.[a-z]+
                                        )
                                        >''', re.I | re.X |re.U)

    def _auto_email_link_sub(self, match):
        return self._encode_email_address(self._unescape_special_chars(match.group(1)))

    def _do_auto_links(self, text):
        text = self._auto_link_re.sub(self._auto_link_sub, text)
        text = self._auto_email_link_re.sub(self._auto_email_link_sub, text)
        return text

    def _encode_email_address(self, addr):
        chars = [_xml_encode_email_char_at_random(ch) for ch in 'mailto:' + addr]
        addr = '<a href="%s">%s</a>' \
                %(''.join(chars), ''.join(chars[7:]))
        return addr

    def _do_link_patterns(self, text):
        link_from_hash = {}
        for regex, repl in self.link_patterns:
            replacements = []
            for match in regex.finditer(text):
                if hasattr(repl, '__call__'):
                    href = repl(match)
                else:
                    href = match.expand(repl)
                replacements.append((match.span(), href))
            for (start, end), href in reversed(replacements):
                escaped_href = (
                    href.replace('"', '&quot;').replace('*', self._escape_table['*']).replace('_', self._escape_table['_'])
                )
                link = '<a href="%s">%s</a>'%(escaped_href, text[start:end])
                hash = _hash_text(link)
                link_from_hash[hash] = link
                text = text[:start] + hash + text[end:]
        for hash, link in list(link_from_hash.items()):
            text = text.replace(hash, link)
        return text

    def _unescape_special_chars(self, text):
        for ch, hash in list(self._escape_table.items()):
            text = text.replace(hash, ch)
        return text

    def _outdent(self, text):
        return self._outdent_re.sub('', text)

class MarkdownWithExtras(Markdown):
    extars = ['footnotes', 'code-color']














class UnicodeWithAttrs(unicode):
    metadata = None
    _toc = None
    def toc_html(self):
        if self._toc is None:
            return None
        def indent():
            return ' ' * (len(h_stack) - 1)
        lines = []
        h_stack = [0]
        for level, id, name in self._toc:
            if level > h_stack[-1]:
                lines.append('%s<ul>'%indent())
                h_stack.append(level)
            elif level == h_stack[-1]:
                lines[-1] += '</li>'
            else:
                while level < h_stack[-1]:
                    h_stack.pop()
                    if not lines[-1].endswith('</li>'):
                        lines[-1] += '</li>'
                    lines.append('%s</ul></li>'%indent())
            lines.append('%s<li><a href = "#%s">%s</a>'%(indent(), id, name))
        while len(h_stack) > 1:
            h_stack.pop()
            if not lines[-1].endswith("</li>"):
                lines[-1] += '</li>'
            lines.append('%s</ul>'%indent())
        return '\n'.join(lines) + '\n'
    toc_html = property(toc_html)

_slugity_strip_re = re.compile(r'[^\w\s-]')
_slugity_hyphenate_re = re.compile(r'[-\s]+')

def _slugity(value):
    import unicodedata
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    value = _slugity_strip_re.sub('', value).strip().lower()
    return _slugity_hyphenate_re.sub('-', value)

def _curry(*args, **kwargs):
    function, args = args[0], args[1:]
    def result(*rest, **kwrest):
        combined = kwargs.copy()
        combined.update(kwrest)
        return function(*args + rest, **combined)
    return result

def _regex_from_encoded_pattern(s):
    if s.startswith('/') and s.rfind('/') != 0:
        idx = s.rfind('/')
        pattern, flags_str = s[1:idx], s[idx+1:]
        flag_from_char = {
            'i' : re.IGNORECASE,
            'l' : re.LOCALE,
            's' : re.DOTALL,
            'm' : re.MULTILINE,
            'u' : re.UNICODE,
        }
        flags = 0
        for char in flags_str:
            try:
                flags |= flag_from_char[char]
            except KeyError:
                raise ValueError("unsupported regex flag: '%s' in '%s'"
                             "(must be one of '%s' )"
                             % (char, s, ''.join(list(flag_from_char.keys()))))
        return re.compile(s[1:idx], flags)
    else:
        return re.compile(re.escape(s))

def _dedentlines(lines, tabsize = 8, skip_first_line = False):
    DEBUG = False
    if DEBUG:
        print("dedent: dedent(..., tabsize=%d, skip_first_line=%r)"
              %(tabsize, skip_first_line))
    indents = []
    margin = None
    for i, line in enumerate(lines):
        if i == 0 and skip_first_line: continue
        indent = 0
        for ch in line:
            if ch == ' ':
                indent += 1
            elif ch == '\t':
                indent += tabsize - (indent % tabsize)
            elif ch in '\r\n':
                continue
            else:
                break
        else:
            continue
        if DEBUG:
            print("dedent: indent = %d:%r"%(indent, line))
        if margin is None:
            margin = indent
        else:
            margin = min(margin, indent)
    if DEBUG:
        print("dedent: margin = %d"%margin)

    if margin is not None and margin > 0:
        for i, line in enumerate(lines):
            if i == 0 and skip_first_line:
                continue
            removed = 0
            for j, ch in enumerate(line):
                if ch == ' ':
                    removed += 1
                elif ch == '\t':
                    removed += tabsize - (removed % tabsize)
                elif ch in '\r\n':
                    if DEBUG:
                        print("dedent :%r:EOL -> strip up to EOL"% line)
                        lines[i] = lines[i][j:]
                        break
                else:
                    raise ValueError("unexpected non-whitespace char %r in"
                                     "line %r while removing %d-space margin"
                                     %(ch, line, margin))
                if DEBUG:
                    print("dedent :%r:%r -> removed %d/%d"
                          %(line, ch, removed, margin))
                if removed == margin:
                    lines[i] = lines[i][j+1:]
                    break
                elif removed > margin:
                    lines[i] = ' '*(removed - margin) + lines[i][j+1:]
                    break
            else:
                if removed:
                    lines[i] = lines[i][removed:]
    return lines


def _dedent(text, tabsize = 8, skip_first_line = False):
    lines = text.splitline(1)
    _dedentlines(lines, tabsize = tabsize, skip_first_line=skip_first_line)
    return ''.join(lines)

class _memoized(object):
    def __call__(self, func):
        self.func = func
        self.cache = {}
    def __call__(self, *args):
        try:
            return self.cache[args]
        except KeyError:
            self.cache[args] = value = self.func(*args)
            return value
        except TypeError:
            return self.func(*args)
    def __repr__(self):
        return self.func.__doc__

def _xml_oneliner_re_from_tab_width(tab_width):
    return re.compile(r'''
                        (?:
                            (?<=\n\n)       # Starting after a blank line
                            |               # or
                            \A\n?           # the beginning of the doc
                        )
                        (                       # save in \1
                            [ ]{0,%d}
                            <(hr)               # start tag = \2
                            \b                  # word break
                            ([^<>])*?           #
                            /?>                 # the matching end tag
                            [ \t]*
                            (?=\n{2,}|\Z)       # followed by a blank line or end of document
                        )'''%(tab_width - 1), re.X)
_xml_oneliner_re_from_tab_width = _memoized(_xml_oneliner_re_from_tab_width)

def _hr_tag_re_from_tab_width(tan_width):
    return re.compile(r'''
                        (?:             
                            (?<=\n\n)       # Starting after a blank line
                            |               # or
                            \A\n?           # the beginning of the doc
                        )
                        (                       # save in \1
                            [ ]{0,%d}
                            <(hr)               # start tag = \2
                            \b                  # word break
                            ([^<>])*?           #
                            /?>                 # the matching end tag
                            [ \t]*
                            (?=\n{2,}|\Z)       # followed by a blank line or end of document
                        )'''%(tan_width - 1), re.X)
_hr_tag_re_from_tab_width = _memoized(_hr_tag_re_from_tab_width)


def _xml_escape_attr(attr, skip_single_quote = True):
    escaped = (attr
               .replace('&', '&amp;')
               .replace('"', '&quto;')
               .replace('<', '&lt;')
               .replace('>', '&gt;'))
    if not skip_single_quote:
        escaped = escaped.replace("'", '&#39;')
    return escaped

def _xml_encode_email_char_at_random(ch):
    r= random()
    if r > 0.9 and ch not in "@_":
        return ch
    elif r < 0.45:
        return '&#%s;'%hex(ord(ch))[1:]
    else:
        return '&#%s;'%ord(ch)



class MarkDown(object):
    extras = None
    urls = None
    titles = None
    html_blocks = None
    html_spans = None
    html_removed_text = '[HTML_REMOVED]'
    list_level = 0

    _ws_only_line_re = re.compile(r'^[ \t]+$', re.M)

    def __init__(self, html4tags = False, tab_width = 4, safe_mode = None, extras = None, link_patterns = None, use_file_vars = False):
        if html4tags:
            self.empty_element_suffix = '>'
        else:
            self.empty_element_suffix = ' />'
        self.tab.width = tab_width

        if safe_mode is True:
            self.safe_mode = 'replace'
        else:
            self.safe_mode = safe_mode

        if self.extras is None:
            self.extras = {}
        elif not isinstance(self.extras, dict):
            self.extras = dict([e, None] for e in self.extras)
        if extras:
            if not isinstance(extras, dict):
                extras = dict([e, None] for e in self.extras)
            self.extras.update(extras)
        assert isinstance(self.extras, dict)
        if 'toc' in self.extras and not 'header-ids' in self.extras:
            self.extras['header-ids'] = None
        self._instance_extars = self.extras.copy()
        self.list_level = link_patterns
        self.use_file_vars = use_file_vars
        self._outdent_re = re.compile(r'^(\t|[ ]{1, %d})' % tab_width, re.M)
        self._escape_table = g_escape_table.copy()
        if 'smarty-pants' in self.extras:
            self._escape_table['"'] = _hash_text('"')
            self._escape_table["'"] = _hash_text("'")
    def reset(self):
        self.urls = {}
        self.titles = {}
        self.html_blocks = {}
        self.html_spans = {}
        self.list_level = 0
        self.extras = self._instance_extars.copy()
        if 'footnotes' in self.extras:
            self.footnotes = {}
            self.footnotes_ids = []
        if 'header-ids' in self.extras:
            self._count_from_header_id = {}
        if 'metadata' in self.extras:
            self.metadata = {}

    def convert(self, text):
        if not isinstance(text, unicode):
            text = unicode(text, 'utf-8')

        if self.use_file_vars:
            emacs_vars = self._get_emacs_vars(text)
            if 'markdown-extras' in emacs_vars:
                splitter = re.compile('[ ,]+')
                for e in splitter.split(emacs_vars['markdown-extras']):
                    if '='in e:
                        ename, earg = e.split('=', 1)
                        try:
                            earg = int(earg)
                        except ValueError:
                            pass
                    else:
                        ename, earg = e, None
                    self.extras[ename] = earg

            text = re.sub('\r\n|\r', '\n', text)

            text += '\n\n'

            text = self._detab(text)

            text = self._ws_only_line_re.sub('', text)

            if 'metadata' in self.extras:
                text = self._extract_metadata(text)

            text = self.preprocess(text)

            if 'fenced-code-blocks' in self.extras and not self.safe_mode:
                text = self._do_fenced_code_blocks(text)

            if self.safe_mode:
                text = self._hash_html_spans(text)

            text = self._hash_html_blocks(text, raw = True)

            if 'fenced-code-blocks' in self.extras and self.safe_mode:
                text = self._do_fenced_code_blocks(text)

            if 'footnotes' in self.extras:
                text = self._strip_footnote_definitions(text)
            text = self._strip_link_definitions(text)

            text = self._run_block_gamut(text)

            if 'footnotes' in  self.extras:
                text = self._add_footnotes(text)

            text = self.postprocess(text)
            text = self._unescape_special_chars(text)

            if self.safe_mode:
                text = self._unhash_html_spans(text)

            if 'nofollow' in self.extras:
                text = self._a_nofollow.sub(r'<\1 rel = "nofollow"\2', text)

            text += '\n'

            rv = UnicodeWithAttrs(text)





class _NoRefolwFormatter(optparse.IndentedHelpFormatter):
    def format_description(self, description):
        return description or ""

def _test():
    import doctest
    doctest.testmod()

def main(argv = None):
    if argv is None:
        argv = sys.argv
    if not logging.root.handlers:
        logging.basicConfig()

    usage = 'usage:%prog [PATH...]'
    version = '%prog'+__version__
    parser = optparse.OptionParser(prog='markdown2', usage=usage,
                                   version=version, description=cmdln_desc,
                                   formatter=_NoRefolwFormatter())
    parser.add_option('-v', '--verbose', dest = 'log_level',action = 'store_const', const = logging.DEBUG,help = 'more verbose output')
    parser.add_option('--ending', help='specify encoding of text content')
    parser.add_option('--html4tag', action='store_true', default=False, help='use HTML 4 style for empty element tags')
    parser.add_option('-s', '--safe', metavar='MODE', dest='safe_mode', help='sannitize literal HTML :"escape" escape'
                                                            'HTML meta chars, "replace" replace with an '
                                                            '[HTML_REMOVED] note')
    parser.add_option("-x", "--extras", action="append",
                      help="Turn on specific extra features (not part of "
                           "the core Markdown spec). See above.")
    parser.add_option("--use-file-vars",
                      help="Look for and use Emacs-style 'markdown-extras' "
                           "file var to turn on extras. See "
                           "<https://github.com/trentm/python-markdown2/wiki/Extras>")
    parser.add_option("--link-patterns-file",
                      help="path to a link pattern file")
    parser.add_option("--self-test", action="store_true",
                      help="run internal self-tests (some doctests)")
    parser.add_option("--compare", action="store_true",
                      help="run against Markdown.pl as well (for testing)")
    parser.set_defaults(log_level=logging.INFO, compare=False, encoding='utf-8', safe_mode=None, use_file_vars=False)
    opts, paths = parser.parse_args()
    log.setLevel(opts.log_level)

    if opts.self_test:
        return _test()
    if opts.extras:
        extras = {}
        for s in opts.extras:
            splitter = re.compile('[,;: ]+')
            for e in splitter.split(s):
                if '=' in e:
                    ename, earg = e.split('=', 1)
                    try:
                        earg = int(earg)
                    except ValueError:
                        parser
                else:
                    ename, earg = e, None
                extras[ename] = earg
    else:
        extras = None

    if opts.link_patterns_file:
        link_patterns = []
        f = open(opts.link_patterns_file)
        try:
            for i, line in enumerate(f.readline()):
                if not line.strip():
                    continue
                if line.lstrip().startswith('#'):
                    continue
                try:
                    pat, href = line.rstrip().rsplit(None, 1)
                except ValueError:
                    raise MarkdownError('%S:%d: invalid link pattern ine :%r'%(opts.link_patterns_file, i+1, line))

                link_patterns.append((_regex_from_encoded_pattern(pat), href))
        finally:
            f.close()
    else:
        link_patterns = None

    from os.path import join, dirname, abspath, exists
    markdown_pl = join(dirname(dirname(abspath(__file__))), 'test', 'Markdown.pl')

    if not paths:
        paths = ['-']
    for path in paths:
        if path == '-':
            text = sys.stdin.read()
        else:
            fp = codecs.open(paths, 'r', opts.encoding)
            text = fp.read()
            fp.close()
        if opts.compare:
            from subprocess import Popen,PIPE
            print('====Markdoen.pl====')
            p = Popen('perl %s '%markdown_pl, shell=True,stdin=PIPE, stdout=PIPE, close_fds=True)
            p.stdin.write(text.encode('utf-8'))
            p.stdin.close()
            perl_html = p.stdout.read().decode('utf-8')
            if py3:
                sys.stdout.write(perl_html)
            else:
                sys.stdout.write(perl_html.encode(sys.stdout.encoding or 'utf-8', 'xmlcharrefreplace'))
            print('====markdown2====')
        html = markdown(text, html4tags=opts.html4tags, safe_code=opts.safe_code,
                        extras=extras, link_patterns=link_patterns,
                        use_file_vars=opts.use_file_vars)
        if py3:
            sys.stdout.write(html)
        else:
            sys.stdout.write(html.encode(sys.stdout.encoding or 'utf-8', 'xmlcharrefreplace'))
        if extras and 'toc' in extras:
            log.debug('toc_html:' + html.toc_html.encode(sys.stdout.encoding or 'utf-8', 'xmlcharrefreplace'))
        if opts.compare:
            test_dir = join(dirname(dirname(abspath(__file__))), 'test')
            if exists(join(test_dir, 'test_markdown2.py')):
                sys.path.insert(0, test_dir)
                from test_markdown2 import norm_html_from_html
                norm_html =norm_html_from_html(html)
                norm_perl_html = norm_html_from_html(perl_html)
            else:
                norm_html = html
                norm_perl_html = perl_html
            print('====match? %r ====='%(norm_perl_html == norm_html))


if __name__ == '__main__':
    sys.exit(main(sys.argv))



















# class MarkDown(object):
#     extras = None
#     urls = None
#     titles = None
#     html_blocks = None
#     html_spans = None
#     html_removed_text = '[HTML_REMOVED]'
#     list_level = 0
#
#     _ws_only_line_re = re.compile(r'^[ \t]+$', re.M)
#
#     def __init__(self, html4tags = False, tab_width = 4, safe_mode = None, extras = None, link_patterns = None, use_file_vars = False):
#         if html4tags:
#             self.empty_element_suffix = '>'
#         else:
#             self.empty_element_suffix = ' />'
#         self.tab.width = tab_width
#
#         if safe_mode is True:
#             self.safe_mode = 'replace'
#         else:
#             self.safe_mode = safe_mode
#
#         if self.extras is None:
#             self.extras = {}
#         elif not isinstance(self.extras, dict):
#             self.extras = dict([e, None] for e in self.extras)
#         if extras:
#             if not isinstance(extras, dict):
#                 extras = dict([e, None] for e in self.extras)
#             self.extras.update(extras)
#         assert isinstance(self.extras, dict)
#         if 'toc' in self.extras and not 'header-ids' in self.extras:
#             self.extras['header-ids'] = None
#         self._instance_extars = self.extras.copy()
#         self.list_level = link_patterns
#         self.use_file_vars = use_file_vars
#         self._outdent_re = re.compile(r'^(\t|[ ]{1, %d})' % tab_width, re.M)
#         self._escape_table = g_escape_table.copy()
#         if 'smarty-pants' in self.extras:
#             self._escape_table['"'] = _hash_text('"')
#             self._escape_table["'"] = _hash_text("'")
#     def reset(self):
#         self.urls = {}
#         self.titles = {}
#         self.html_blocks = {}
#         self.html_spans = {}
#         self.list_level = 0
#         self.extras = self._instance_extars.copy()
#         if 'footnotes' in self.extras:
#             self.footnotes = {}
#             self.footnotes_ids = []
#         if 'header-ids' in self.extras:
#             self._count_from_header_id = {}
#         if 'metadata' in self.extras:
#             self.metadata = {}
#
#     def convert(self, text):
#         if not isinstance(text, unicode):
#             text = unicode(text, 'utf-8')
#
#         if self.use_file_vars:
#             emacs_vars = self._get_emacs_vars(text)
#             if 'markdown-extras' in emacs_vars:
#                 splitter = re.compile('[ ,]+')
#                 for e in splitter.split(emacs_vars['markdown-extras']):
#                     if '='in e:
#                         ename, earg = e.split('=', 1)
#                         try:
#                             earg = int(earg)
#                         except ValueError:
#                             pass
#                     else:
#                         ename, earg = e, None
#                     self.extras[ename] = earg
#
#             text = re.sub('\r\n|\r', '\n', text)
#
#             text += '\n\n'
#
#             text = self._detab(text)
#
#             text = self._ws_only_line_re.sub('', text)
#
#             if 'metadata' in self.extras:
#                 text = self._extract_metadata(text)
#
#             text = self.preprocess(text)
#
#             if 'fenced-code-blocks' in self.extras and not self.safe_mode:
#                 text = self._do_fenced_code_blocks(text)
#
#             if self.safe_mode:
#                 text = self._hash_html_spans(text)
#
#             text = self._hash_html_blocks(text, raw = True)
#
#             if 'fenced-code-blocks' in self.extras and self.safe_mode:
#                 text = self._do_fenced_code_blocks(text)
#
#             if 'footnotes' in self.extras:
#                 text = self._strip_footnote_definitions(text)
#             text = self._strip_link_definitions(text)
#
#             text = self._run_block_gamut(text)
#
#             if 'footnotes' in  self.extras:
#                 text = self._add_footnotes(text)
#
#             text = self.postprocess(text)
#             text = self._unescape_special_chars(text)
#
#             if self.safe_mode:
#                 text = self._unhash_html_spans(text)
#
#             if 'nofollow' in self.extras:
#                 text = self._a_nofollow.sub(r'<\1 rel = "nofollow"\2', text)
#
#             text += '\n'
#
#             rv = UnicodeWithAttrs(text)

# def markdown_path(path, encoding = 'utf-8',
#                   html4tags = False, tab_width = DEFAULT_TAB_WIDTH,
#                   safe_mode = None, extras = None, link_patterns = None,
#                   use_file_vars = False):
#     fp = codecs.open(path, 'r', encoding)
#     text = fp.read()
#     fp. close()
#     return Markdown()