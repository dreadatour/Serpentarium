# -*- coding: utf-8 -*-
"""
Work with ctags file
"""
import time  # profiling


class CTags(object):
    """
    Work with ctags file
    """

    def __init__(self, tags_file=None, debug=False):
        """
        Initialize
        """
        # this is for ctags list
        self._tags = None
        self._debug = debug

        if tags_file is not None:
            # load ctags if ctags file given
            self.load_file(tags_file)

    def load_file(self, tags_file):
        """
        Load or reload tags from ctags file
        """
        if self._debug:  # profiling
            timing = time.time()

        try:
            # read ctags file and get all lines from file
            all_tags = tuple(l.strip() for l in open(tags_file, 'r'))
        except IOError:
            return False

        tags = list()
        for tag_line in all_tags:
            # skip empty lines and ctags comments
            if not tag_line or tag_line.startswith('!_'):
                continue

            # split tags line into fields
            tagname, tagfile, tagaddress, tagfields = tag_line.split('\t', 3)

            # parse tagfields
            if tagfields:
                fields = {}
                for field in tagfields.split('\t'):
                    # parse tagfield name and value
                    if ':' in field:
                        field_name, field_value = field.split(':', 1)
                        if not field_value:
                            if field_name == 'file':
                                field_value = tagfile
                            else:
                                field_value = None
                    elif len(field) == 1:
                        field_name = 'kind'
                        field_value = field
                    else:
                        # Something goes wrong!
                        print "[%s] Can't parse line '%s'" % (__name__,
                                                              tagfields)
                        continue
                    fields[field_name] = field_value

                tagfields = fields
            else:
                tagfields = {}

            # append parsed tagfield into tags list
            tags.append((
                tagname.decode('utf-8'),
                tagfile.decode('utf-8'),
                int(tagfields.get('line', 0)),
                tagaddress.decode('utf-8'),
                tagfields
            ))
        self._tags = tags

        if self._debug:  # profiling
            timing = (time.time() - timing) * 1000
            print "[ctags] rebuild: %.02fms" % timing

    def get_definitions(self, symbol=None):
        """
        Find all definitions of word under a cursor and return list of it
        """
        if self._debug:  # profiling
            timing = time.time()

        definitions = []

        if symbol is None:
            # return all tags
            definitions = self._tags
        else:
            # check all tags and search for given symbol
            found = False
            for tag in self._tags:
                if tag[0] == symbol:
                    definitions.append(tag)
                    found = True
                elif found:
                    break

        if self._debug:  # profiling
            timing = (time.time() - timing) * 1000
            print "[ctags] definitions: %.02fms" % timing

        return definitions

    def autocomplete(self, prefix):
        """
        Autocomplete: find all tags with prefix
        """
        if self._debug:  # profiling
            timing = time.time()

        completions = []
        found = False

        # check all tags and search for given prefix
        for tag in self._tags:
            if tag[0].startswith(prefix):
                completions.append([tag[0]])
                found = True
            elif found:
                break

        # prepare completions list for sublime
        completions = [(i, i) for sublist in completions for i in sublist]
        completions = list(set(completions))
        completions.sort()

        if self._debug:  # profiling
            timing = (time.time() - timing) * 1000
            print "[ctags] autocomplete: %.02fms" % timing

        return completions
