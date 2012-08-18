# -*- coding: utf-8 -*-
import time  # XXX: debug

import sublime


class CTags(object):
    """
    Work with ctags file
    """

    def __init__(self, tags_file=None):
        """
        Initialize
        """
        self._tags = None

        if tags_file is not None:
            self.load_file(tags_file)

    def load_file(self, tags_file):
        """
        Load or reload tags from ctags file
        """
        time_run = time.time()  # XXX: debug

        try:
            all_tags = tuple(l.strip() for l in open(tags_file, 'r'))
        except IOError:
            return False

        tags = list()
        for tag_line in all_tags:
            # skip ctags comments
            if tag_line.startswith('!_'):
                continue

            tagname, tagfile, tagaddress, tagfields = tag_line.split('\t', 3)

            if tagfields:
                fields = {}
                for field in tagfields.split('\t'):
                    if ':' in field:
                        field_name, field_value = field.split(':', 1)
                        if not field_value:
                            if field_name == 'file':
                                field_value = tagfile
                            else:
                                field_value = None
                    else:
                        # Something goes wrong!
                        print "[%s] Can't parse line '%s'" % (__name__,
                                                              tagfields)
                        continue
                    fields[field_name] = field_value

                tagfields = fields
            else:
                tagfields = {}

            tags.append((tagname, tagfile, tagaddress, tagfields))
        self._tags = tags

        print "Profiling rebuild ctags: %.02fms" % (
            (time.time() - time_run) * 1000
        )  # XXX: debug

    def get_definitions(self, symbol, view):
        """
        Find all definitions of word under a cursor and return list of it
        """
        time_run = time.time()  # XXX: debug
        print "Jump to definition:", symbol

        definitions = []

        found = False
        for tag in self._tags:
            # if tag[0] == symbol and tag[3]['kind'] != 'v':
            if tag[0] == symbol:
                definitions.append([
                    tag[2][2:-4].strip(),
                    tag[1],
                    int(tag[3].get('line', 0))
                ])
                found = True
            elif found:
                break

        print "Profiling definitions: %.02fms" % (
            (time.time() - time_run) * 1000
        )  # XXX: debug

        return definitions

    def autocomplete(self, view, prefix, locations):
        """
        Autocomplete: find all tags with prefix
        """
        print "Autocomplete", prefix, locations, view.file_name()
        time_run = time.time()  # XXX: debug

        completions = []

        pt = locations[0] - len(prefix) - 1
        ch = view.substr(sublime.Region(pt, pt + 1))
        is_dot = (ch == '.')

        found = False
        for tag in self._tags:
            if tag[0].startswith(prefix):
                completions.append([tag[0]])
                found = True
            elif found:
                break

        completions = [(i, i) for sublist in completions for i in sublist]
        completions = list(set(completions))
        completions.sort()

        print "Profiling autocomplete: %.02fms" % (
            (time.time() - time_run) * 1000
        )  # XXX: debug

        return completions
