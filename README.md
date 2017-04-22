Imagine
=======

``` {.imagine}
Imagine
  A pandoc filter that turns fenced codeblocks into graphics or ascii art by
  wrapping some external command line utilities, such as:

    actdiag, asy, asymptote, blockdiag, boxes, circo, ditaa, dot, fdp,
    figlet, flydraw, gle, gnuplot, graph, graphviz, imagine, mermaid,
    mscgen, neato, nwdiag, packetdiag, pic, pic2plot, plantuml, plot,
    ploticus, protocol, pyxplot, rackdiag, seqdiag, sfdp, twopi

Installation

  1. Put `imagine.py` anywhere along $PATH (pandoc's search path for filters).
  2. % sudo pip install (mandatory):
       - pandocfilters
  3. % sudo apt-get install (1 or more of):
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

     % sudo pip install:
       - blockdiag,  http://blockdiag.com
       - phantomjs,  http://phantomjs.org/ (for mermaid)

     % git clone
       - protocol,   https://github.com/luismartingarcia/protocol.git

     % npm install:
       - -g mermaid, https://knsv.github.io/mermaid (and pip install phantomjs)


Pandoc usage

    % pandoc --filter imagine.py document.md -o document.pdf


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

     % cmd <options> <inputfile> <outputfile>

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
```
