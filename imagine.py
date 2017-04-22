#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-- Candidates:
# o grace (ie gracebat, the batchmode variant; indirect mode?)
#   script files are pretty big.  Perhaps indirectly.  It supports a batch mode
#   via `gracebat`, which symlinks to the real binary executable.
#
# o gri http://gri.sourceforge.net/gridoc/html/
#
# o tizk, needs convert since eps wont go into pdflatex ..

# Notes:
# - need to check if Imagine cleanly removes itself from codeblock attributes
#   if it returns some kind of (ascii art) codeblock itself.  Otherwise
#   converting to markdown and processing that again with --filter Imagine
#   might be somewhat unpredictable..
# - to avoid work, a hash of the entire codeblock is used and a check is done
#   for the intended output file.  That doesn't work well if usage is indirect
#   where the codeblock points to a file.  So howto elegantly pick up on changes
#   to a datafile?
# - perhaps add an option to specify if a tool requires its input as
#   -- an input file,
#   -- on stdin or
#   -- on its commandline?
#   -- via redirect (ie codeblock=input filename)
# - perhaps add ability to specify some globals via YAML in a document?
#   -- like images subdir, instead of 'pd-images'
#   -- verbosity level of output (or as codeblock option enable targetted
#   debugging for a specific codeblock).

#-- __doc__

'''Imagine
  A pandoc filter that turns fenced codeblocks into graphics or ascii art by
  wrapping some external command line utilities, such as:

    %(cmds)s

Installation

  1. Put `imagine.py` anywhere along $PATH (pandoc's search path for filters).
  2. %% sudo pip install (mandatory):
       - pandocfilters
  3. %% sudo apt-get install (1 or more of):
       - graphviz,      http://graphviz.org
       - plantuml,      http://plantuml.com
       - ditaa,         http://ditaa.sourceforge.net
       - figlet,        http://www.figlet.org
       - boxes,         http://boxes.thomasjensen.com
       - plotutils,     https://www.gnu.org/software/plotutils/
       - gnuplot,       http://www.gnuplot.info/
       - asymptote,     http://asymptote.sourceforge.net/
       - pyxplot,       http://pyxplot.org.uk/
       - ploticus,      http://ploticus.sourceforge.net/doc/welcome.html
       - flydraw,       http://manpages.ubuntu.com/manpages/precise/man1/flydraw.1.html
       - gle-graphics,  http://glx.sourceforge.net/

     %% sudo pip install:
       - blockdiag,  http://blockdiag.com
       - phantomjs,  http://phantomjs.org/ (for mermaid)

     %% git clone
       - protocol,   https://github.com/luismartingarcia/protocol.git

     %% npm install:
       - -g mermaid, https://knsv.github.io/mermaid (and pip install phantomjs)


Pandoc usage

    %% pandoc --filter imagine.py document.md -o document.pdf


Markdown usage

               or                                 or
  ```cmd       |   ```{.cmd options="extras"}     |   ```{prog=cmd}
  source       |   source                         |   source
  ```          |   ```                            |   ```
  simple           with `options`                     with `prog`

  Imagine understands/consumes these fenced codeblock key,val-attributes:
  - `options` used to feed extra arguments to the external command
  - `prog`    used when cmd is not an appropiate document class
  - `keep`    if True, keeps a reconstructued copy of the original CodeBlock

  Notes:
  - if `cmd` is not found, the codeblock is kept as-is.
  - input/output filenames are generated from a hash of the fenced codeblock.
  - subdir `pd-images` is used to store any input/output files
  - if an output filename exists, it is not regenerated but simply linked to.
  - `packetdiag` & `sfdp`s underlying libraries seem to have some problems.


How Imagine works

  The general format for an external command looks something like:

     %% cmd <options> <inputfile> <outputfile>

  Input/Output filenames are generated using `pandocfilters.get_filename4code`
  supplying both the codeblock and its attributes as a string for hashing. If
  the input file doesn't exist it is generated by writing the code in the fenced
  codeblock. Hence, if you change the code and/or the attributes, new files will
  result.

  Imagine does no clean up so, after a while, you might want to clear the
  `pd-images` subdirectory.

  Some commands are Imagine's aliases for system commands.  Examples are
  `graphviz` which is an alias for `dot` and `pic` which is an alias for
  `pic2plot`.  Mainly because that allows the alias names to be used as a cmd
  for a fenced codeblock (ie. ```graphviz to get ```dot)

  Some commands like `figlet` or `boxes` produce output on stdout.  This text is
  captured and used to replace the code in the fenced code block.

  Some commands like `plot` interpret the code in the fenced code block as an
  input filename to convert to some other output format.

  If a command fails for some reason, the fenced codeblock is kept as is.  In
  that case, the output produced by Imagine on stderr hopefully provides some
  usefull info.


Security

  Imagine just wraps some commands and provides no checks.

  So use it with care and make sure you understand the fenced codeblocks before
  running it through the filter.


Imagine command

  Finally, a quick way to read this help text again, is to include a fenced
  codeblock in your markdown document as follows:

    ```imagine
    ```

  That's it, enjoy!
'''

__version__ = 0.5

import os
import sys
from subprocess import Popen, check_output, CalledProcessError, STDOUT, PIPE

import pandocfilters as pf

#-- globs
IMG_BASEDIR = 'pd'

# Notes:
# - if walker does not return anything, the element is kept
# - if walker returns a block element, it'll replace current element
# - block element = {'c': <value>, 't': <block_type>}

class HandlerMeta(type):
    def __init__(cls, name, bases, dct):
        'register worker classes by codecs handled'
        for klass in dct.get('codecs', {}):
            cls.workers[klass.lower()] = cls

class Handler(object):
    'baseclass for image/ascii art generators'
    severity  = 'error warn note info debug'.split()
    workers = {}    # dispatch mapping for Handler
    klass = None    # assigned when worker is dispatched
    __metaclass__ = HandlerMeta

    codecs = {}     # worker subclass must override, klass -> cli-program
    level = 2       # log severity level, see above
    outfmt = 'png'  # default output format for a worker

    def __call__(self, codec):
        'Return worker class or self (Handler keeps CodeBlock unaltered)'
        # A worker class with codecs={'': cmd} replaces Handler as default
        # CodeBlock's value = [(Identity, [classes], [(key, val)]), code]
        self.msg(4, 'Handler __call__ codec', codec[0])
        try:
            _, klasses, keyvals = codec[0]
        except Exception as e:
            self.msg(0, 'Invalid codec passed in', codec)
            raise e

        # try dispatching by class attribute first
        for klass in klasses:
            worker = self.workers.get(klass.lower(), None)
            if worker is not None:
                worker.klass = klass.lower()
                self.msg(4, codec[0], 'dispatched by class to', worker)
                return worker(codec)

        # try dispatching via 'cmd' named by prog=cmd key-value
        if len(keyvals) == 0:  # pf.get_value barks if keyvals == []
            self.msg(4, codec[0], 'dispatched by default', self)
            return self

        prog, _ = pf.get_value(keyvals, 'prog', '')
        worker = self.workers.get(prog.lower(), None)
        if worker is not None:
            self.msg(4, codec[0], 'dispatched by prog to', worker)
            return worker(codec)

        self.msg(4, codec[0], 'dispatched by default to', self)
        return self

    def __init__(self, codec):
        'init by decoding the CodeBlock-s value'
        # codeblock attributes: {#Identity .class1 .class2 k1=val1 k2=val2}
        self.codec = codec
        self._name = self.__class__.__name__  # the default inpfile extension
        self.output = '' # catches output by self.cmd, if any

        if codec is None:
            return # silently, no CodeBlock then nothing todo.

        (self.id_, self.classes, self.keyvals), self.code = codec
        self.caption, self.typef, self.keyvals = pf.get_caption(self.keyvals)

        # `Extract` Imagine's keyvals from codeblock's attributes
        self.options, self.keyvals = pf.get_value(self.keyvals, u'options', '')
        self.prog, self.keyvals = pf.get_value(self.keyvals, u'prog', None)
        self.keep, self.keyvals = pf.get_value(self.keyvals, u'keep', '')

        # prefer prog=cmd key-value over .cmd class attribute
        self.prog = self.prog if self.prog else self.codecs.get(self.klass, None)
        if self.prog is None:
            self.msg(0, self.klass, 'not listed in', self.codecs)
            raise Exception('worker has no cli command for %s' % self.klass)

        self.keep = True if self.keep.lower() == 'true' else False
        self.basename = pf.get_filename4code(IMG_BASEDIR, str(codec))
        self.outfile = self.basename + '.%s' % self.outfmt
        self.inpfile = self.basename + '.%s' % self._name.lower()

        self.codetxt = self.code.encode(sys.getfilesystemencoding())
        if not os.path.isfile(self.inpfile):
            self.write('w', self.codetxt, self.inpfile)

    def read(self, src):
        try:
            with open(src, 'r') as f:
                return f.read()
        except Exception as e:
            self.msg(0, 'fail: could not read %s' % src)
            return ''
        return ''


    def write(self, mode, dta, dst):
        if len(dta) == 0:
            self.msg(3, 'skipped writing 0 bytes to', dst)
            return False
        try:
            with open(dst, mode) as f:
                f.write(dta)
            self.msg(3, 'wrote', len(dta), 'bytes to', dst)
        except Exception as e:
            self.msg(0, 'fail: could not write', len(dta), 'bytes to', dst)
            self.msg(0, 'exception', e)
            return False
        return True

    def msg(self, level, *a):
        if level > self.level: return
        level %= len(self.severity)
        msg = '%s[%9s:%-5s] %s' % ('Imagine',
                                self._name,
                                self.severity[level],
                                ' '.join(str(s) for s in a))
        print >> sys.stderr, msg

    def fmt(self, fmt, **specials):
        '(re)set image file extension based on output document format'
        self.outfmt = pf.get_extension(fmt, self.outfmt, **specials)
        self.outfile = self.basename + '.%s' % self.outfmt

    def Url(self):
        'return an Image link for existing/new output image-file'
        # Since pf.Image is an Inline element, its usually wrapped in a pf.Para
        return pf.Image([self.id_, self.classes, self.keyvals],
                        self.caption, [self.outfile, self.typef])

    def Para(self):
        'return Para containing an Image link to the generated image'
        retval = pf.Para([self.Url()])
        if self.keep:
            return [self.AnonCodeBlock(), retval]
        return retval

    def CodeBlock(self, attr, code):
        'return as CodeBlock'
        retval = pf.CodeBlock(attr, code)
        if self.keep:
            return [self.AnonCodeBlock(), retval]
        return retval

    def AnonCodeBlock(self):
        'reproduce the original CodeBlock inside an anonymous CodeBlock'
        (id_, klasses, keyvals), code = self.codec
        id_ = '#' + id_ if id_ else id_
        klasses = ' '.join('.%s' % c for c in klasses)
        keyvals = ' '.join('%s="%s"' % (k,v) for k,v in keyvals)
        attr = '{%s}' % ' '.join(a for a in [id_, klasses, keyvals] if a)
        return pf.CodeBlock(['',[],[]], '```%s\n%s\n```'% (attr, self.code))


    def cmd(self, *args, **kwargs):
        'run, possibly forced, a cmd and return success indicator'
        forced = kwargs.get('forced', False) # no need to pop
        stdinput = kwargs.get('stdinput', None)

        if os.path.isfile(self.outfile) and forced is False:
            self.msg(3, 'exists:', *args)
            return True

        try:
            pipes = {'stdin': None if stdinput is None else PIPE,
                     'stdout': PIPE,
                     'stderr': PIPE}
            p = Popen(args, **pipes)
            self.output, err = p.communicate(stdinput)
            # self.output = check_output(args, stderr=STDOUT)
            if len(err):
                self.msg(1, 'ok?', *args)
                for line in err.splitlines():
                    self.msg(1, '>>:', line)
            else:
                self.msg(2, 'ok:', *args)
            return p.returncode == 0

        except CalledProcessError as e:
            try: os.remove(self.outfile)
            except: pass
            self.msg(1, 'fail:', *args)
            maxchars = min(70, e.output.find(os.linesep))
            self.msg(0, self.prog , e.output[0:maxchars])
            return False

    def image(self, fmt=None):
        'return an Image url or None to keep CodeBlock'
        # workers must override this method
        self.msg(4, self._name, 'keeping CodeBlock as-is (default)')
        return None


class Imagine(Handler):
    '''wraps self, yields new codeblock w/ Imagine __doc__ string'''
    codecs = {'imagine': 'imagine'}

    def image(self, fmt=None):
        # CodeBlock value = [(Identity, [classes], [(key, val)]), code]
        return pf.CodeBlock(('',['imagine'], []), __doc__)

class Flydraw(Handler):
    'flydraw < `codetxt` -> Image'
    codecs = {'flydraw': 'flydraw'}
    outfmt = 'gif'

    def image(self, fmt=None):
        args = self.options.split()
        if self.cmd(self.prog, stdinput=self.codetxt, *args):
            if len(self.output):
                self.write('w', self.output, self.outfile)
            return self.Para()

class Figlet(Handler):
    'figlet `codetxt` -> CodeBlock(ascii art)'
    codecs = {'figlet': 'figlet'}
    outfmt = 'figled'

    def image(self, fmt=None):
        args = self.options.split()
        if self.cmd(self.prog, stdinput=self.codetxt, *args):
            if len(self.output):
                # save figlet's stdout to outfile for next time around
                self.write('w', self.output, self.outfile)
            else:
                self.output = self.read(self.outfile)
            return self.CodeBlock(self.codec[0], self.output)


class Boxes(Handler):
    'boxes `codetxt` -> CodeBlock(boxed text)'
    codecs = {'boxes': 'boxes'}
    outfmt = 'boxed'

    def image(self, fmt=None):
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, *args):
            if len(self.output):
                self.write('w', self.output, self.outfile)
            else:
                self.output = self.read(self.outfile)
            return self.CodeBlock(self.codec[0], self.output)
            return self.CodeBlock(self.codec[0], self.output)


class Protocol(Handler):
    'protocol `codetxt` -> CodeBlock(packet format in ascii)'
    codecs = {'protocol': 'protocol'}
    outfmt = 'protocold'

    def image(self, fmt=None):
        args = self.options.split() + [self.codetxt]
        if self.cmd(self.prog, *args):
            if len(self.output):
                self.write('w', self.output, self.outfile)
            else:
                self.output = self.read(self.outfile)
            return self.CodeBlock(self.codec[0], self.output)
            return self.CodeBlock(self.codec[0], self.output)


class Gle(Handler):
    'gle -cairo -output <outfile> -> Para(Img(outfile))'
    codecs = {'gle': 'gle'}

    def image(self, fmt=None):
        self.outfmt = self.fmt(fmt)
        args = self.options.split()#  + ['-output', self.outfile, self.inpfile]
        args.extend(['-verbosity', '0'])
        args.extend(['-output', self.outfile, self.inpfile])

        if self.cmd(self.prog, *args):
            # remove ./gle ?
            return self.Para()


class GnuPlot(Handler):
    'gnuplot inpfile -> Para(Img(outfile))'
    codecs = {'gnuplot': 'gnuplot'}

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, *args):
            if len(self.output):
                self.write('wb', self.output, self.outfile)
            return self.Para()


class Plot(Handler):
    'plot `cat codetxt` -> Para(Img(outfile))'
    codecs = {'plot': 'plot'}

    def image(self, fmt=None):
        'interpret code as input filename of meta graphics file'
        self.fmt(fmt)
        if not os.path.isfile(self.codetxt):
            self.msg(0, 'fail: cannot read file %r' % self.codetxt)
            return
        args = self.options.split() + [self.codetxt]
        if self.cmd(self.prog, '-T', self.outfmt, *args):
            self.write('wb', self.output, self.outfile)
            return self.Para()


class Graph(Handler):
    codecs = {'graph': 'graph'}

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, '-T', self.outfmt, *args):
            self.write('wb', self.output, self.outfile)
            return self.Para()


class Pic2Plot(Handler):
    codecs = {'pic2plot': 'pic2plot', 'pic': 'pic2plot'}

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, '-T', self.outfmt, *args):
            self.write('wb', self.output, self.outfile)
            return self.Para()


class PyxPlot(Handler):
    codecs = {'pyxplot': 'pyxplot'}

    # need to set output format and output filename in the script...
    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        self.codetxt = '%s\n%s\n%s' % ('set terminal %s' % self.outfmt,
                                       'set output %s' % self.outfile,
                                       self.codetxt)
        self.write('w', self.codetxt, self.inpfile)
        if self.cmd(self.prog, self.inpfile, *args):
            return self.Para()


class Asy(Handler):
    codecs = {'asy': 'asy', 'asymptote': 'asy'}
    outfmt = 'png'

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, '-o', self.outfile, *args):
            return self.Para()


class Ploticus(Handler):
    codecs = {'ploticus': 'ploticus'}

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, '-%s' % self.outfmt, '-o', self.outfile, *args):
            return self.Para()


class PlantUml(Handler):
    codecs = {'plantuml': 'plantuml'}

    def image(self, fmt=None):
        self.fmt(fmt)
        if self.cmd(self.prog, '-t%s' % self.outfmt, self.inpfile):
            return self.Para()

class Mermaid(Handler):
    codecs = {'mermaid': 'mermaid'}

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split() + [self.inpfile]
        if self.cmd(self.prog, '-o', IMG_BASEDIR+'-images', *args):
            # latex chokes on filename.txt.png
            try: os.rename(self.inpfile+'.'+self.outfmt, self.outfile)
            except: pass
            return self.Para()

class Ditaa(Handler):
    codecs = {'ditaa': 'ditaa'}

    def image(self, fmt=None):
        self.fmt(fmt)
        if self.cmd(self.prog, self.inpfile, self.outfile, '-T', self.options):
            return self.Para()


class MscGen(Handler):
    codecs = {'mscgen': 'mscgen'}

    def image(self, fmt=None):
        self.fmt(fmt)
        if self.cmd(self.prog, '-T', self.outfmt,
                    '-o', self.outfile, self.inpfile):
            return self.Para()


class BlockDiag(Handler):
    progs = 'blockdiag seqdiag rackdiag nwdiag packetdiag actdiag'.split()
    codecs = dict(zip(progs,progs))

    def image(self, fmt=None):
        self.fmt(fmt)
        if self.cmd(self.prog, '-T', self.outfmt, self.inpfile,
                    '-o', self.outfile):
            return self.Para()


class Graphviz(Handler):
    progs = ['dot', 'neato', 'twopi', 'circo', 'fdp', 'sfdp']
    codecs = dict(zip(progs,progs))
    codecs['graphviz'] = 'dot'

    def image(self, fmt=None):
        self.fmt(fmt)
        args = self.options.split()
        args.append('-T%s' % self.outfmt)
        args.extend([self.inpfile, '-o', self.outfile])
        if self.cmd(self.prog, *args):
            return self.Para()

from textwrap import wrap
__doc__ = __doc__ % {'cmds':'\n    '.join(wrap(', '.join(sorted(Handler.workers.keys()))))}


def walker(key, value, fmt, meta):
    if key == u'CodeBlock':
        worker = dispatch(value)
        return worker.image(fmt)


if __name__ == '__main__':
    dispatch = Handler(None)
    pf.toJSONFilter(walker)

