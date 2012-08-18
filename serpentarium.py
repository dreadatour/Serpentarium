# -*- coding: utf-8 -*-
import os
import re
import json
import tempfile
import functools
import threading
import subprocess

import sublime
import sublime_plugin

from ctags import CTags

settings = sublime.load_settings("Serpentarium.sublime-settings")

ctags = None
history = []


def threaded(finish=None, msg="Thread already running"):
    """
    Run procedure in thread
    """
    def decorator(func):
        func.running = 0

        @functools.wraps(func)
        def threaded(*args, **kwargs):
            def run():
                try:
                    result = func(*args, **kwargs)
                    if result is None:
                        result = ()

                    elif not isinstance(result, tuple):
                        result = (result,)

                    if finish:
                        sublime.set_timeout(
                            functools.partial(finish, args[0], *result),
                            0
                        )
                finally:
                    func.running = 0
            if not func.running:
                func.running = 1
                t = threading.Thread(target=run)
                t.setDaemon(True)
                t.start()
            else:
                sublime.status_message(msg)
        threaded.func = func
        return threaded
    return decorator


class Serpentarium(object):
    """
    Serpentarium base class
    """
    @property
    def get_config_filename(self):
        """
        Some kind of paranoia =)
        """
        try:
            return self._config_filename
        except AttributeError:
            pass

        self._config_filename = settings.get('project_config_filename',
                                             'serpentarium.json')
        return self._config_filename

    def check_ctags(self):
        """
        Check for ctags installed if ctags enabled
        """
        ctags_cmd = settings.get('ctags_cmd')
        if ctags_cmd:
            if not os.path.exists(ctags_cmd):
                sublime.error_message((
                    "Ctags is not found in '%s'. Please, install ctags."
                ) % ctags_cmd)
                return False
        else:
            sublime.error_message(
                "Ctags are enabled, but ctags_cmd is not defined in config"
            )
            return False
        return True

    def get_path(self, paths=None):
        """
        Get first path from paths list or current view path
        """
        try:
            path = paths[0]
        except TypeError:
            path = self.window.active_view().file_name()

        path = os.path.abspath(os.path.normpath(path))
        if os.path.isfile(path):
            path = os.path.dirname(path)

        return path

    def get_config_file(self, path=None):
        """
        Get config file absolute path
        """
        # get current file name
        if path is None:
            path = self.window.active_view().file_name()

        try:
            if path in self._config_file:
                return self._config_file.get(path)
        except AttributeError:
            self._config_file = dict()

        # normalize path and get dirname
        path = os.path.abspath(os.path.normpath(path))
        if os.path.isfile(path):
            path = os.path.dirname(path)

        # go upwards to root and search for project config
        path_before = None
        while path != path_before:
            config_file = os.path.join(path, self.get_config_filename)

            if os.path.exists(config_file) and os.path.isfile(config_file):
                self._config_file[path] = config_file
                return config_file

            path_before = path
            path = os.path.dirname(path)

        return None

    def parse_config(self, path=None):
        """
        Parse project config file
        """
        config_file = self.get_config_file(path)
        if config_file is None:
            return None

        try:
            with open(config_file) as f:
                config = f.read()
            return json.loads(config)
        except ValueError:
            sublime.error_message(
                "%s: Error parsing config file %s" % (__name__, config_file)
            )
        return None

    def get_ctags_file(self, path=None):
        config_file = self.get_config_file(path)
        if config_file is None:
            return None
        config_dir = os.path.dirname(config_file)

        config = self.parse_config(path)
        if config is None:
            return None

        ctags_file = config.get('ctags_file')
        if not ctags_file:
            return None

        ctags_file = os.path.join(config_dir, ctags_file)
        return os.path.abspath(os.path.normpath(ctags_file))

    def goto_file(self, view, filename, row, col=0):
        """
        Open file and scroll to line number
        """
        view.window().open_file("%s:%d:%d" % (filename, row, col),
                                sublime.ENCODED_POSITION)


class SerpentariumSetupCommand(sublime_plugin.WindowCommand, Serpentarium):
    """
    Setup project - add config file to selected folder
    """
    def run(self, paths=None):
        """
        Run build command
        """
        path = self.get_path(paths)
        config_file = self.get_config_file(path)

        if settings.get('ctags_enabled') and not self.check_ctags():
            return False

        # clone default project config file if not exists
        if not config_file:
            if not os.path.isdir(path):
                path = os.path.dirname(path)
            config_file = os.path.join(path, self.get_config_filename)

            default_config = os.path.join(
                sublime.packages_path(),
                'Serpentarium',
                'Serpentarium.default-config'
            )
            with open(default_config, 'r') as read_config:
                with open(config_file, 'w') as write_config:
                    write_config.write(read_config.read())

        sublime.active_window().open_file(config_file)


class SerpentariumRebuildCommand(sublime_plugin.WindowCommand, Serpentarium):
    """
    Rebuild ctags and/or cscope tags
    """
    def is_visible(self, paths=None):
        """
        Is "Rebuild tags" command is visible?
        """
        return self.get_config_file(self.get_path(paths)) is not None

    def run(self, paths=None, silent=False):
        """
        Run build command
        """
        build_ctags = settings.get('ctags_enabled')
        build_cscope = settings.get('cscope_enabled')

        if not build_ctags and not build_cscope:
            return

        path = self.get_path(paths)

        config_file = self.get_config_file(path)
        if config_file is None:
            return

        if build_ctags and not self.check_ctags():
            return False

        config = self.parse_config(path)
        if config is None:
            return

        # prepare folders list for build
        config_dir = os.path.dirname(config_file)
        folders = [path.rstrip('/'), config_dir.rstrip('/')]
        if 'include_dirs' in config:
            for d in config.get('include_dirs'):
                dirname = os.path.join(config_dir, d)
                if os.path.exists(dirname) and os.path.isdir(dirname):
                    folders.append(os.path.normpath(dirname).rstrip('/'))
                else:
                    sublime.error_message(
                        "%s: directory '%s' is not found %s" % (__name__, d)
                    )

        # get ctags params
        if build_ctags:
            ctags = {
                "cmd": settings.get('ctags_cmd'),
                "args": settings.get('ctags_args'),
                "out": self.get_ctags_file(path),
            }
        else:
            ctags = None

        # get cscope params
        if build_cscope:
            cscope = {
                "cmd": settings.get('cscope_cmd'),
                #"out": self.get_cscope_file(path)
            }
        else:
            cscope = None

        self.build_tags(folders, ctags, cscope, silent)

    def build_is_done(self, is_ok=False, tags=None, silent=False):
        """
        Build tags os over - cleanup
        """
        if is_ok:
            global ctags
            ctags = tags
            if not silent:
                sublime.status_message('Tags rebuilded')
        else:
            sublime.status_message(
                'Tags NOT rebuilded! See console for more information.'
            )

    @threaded(finish=build_is_done, msg="Build process is running alredy")
    def build_tags(self, folders=None, ctags=None, cscope=None, silent=False):
        """
        Do build tags hard work in thread
        """
        tmpfile = tempfile.NamedTemporaryFile(delete=False).name

        cmd = "find '%s' -type f -name '*.py' > '%s'" % ("' '".join(folders),
                                                         tmpfile)
        p = subprocess.Popen(cmd, shell=1, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        ret = p.wait()
        if ret:
            raise EnvironmentError((cmd, ret, p.stdout.read()))

        if ctags is not None:
            cmd = "%s %s --fields=+nz -L '%s' -f '%s'" % (
                ctags['cmd'],
                ' '.join(ctags['args']),
                tmpfile,
                ctags['out'],
            )
            p = subprocess.Popen(cmd, shell=1, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            ret = p.wait()
            if ret:
                raise EnvironmentError((cmd, ret, p.stdout.read()))

        tags = CTags(tags_file=ctags['out'])

        if tmpfile is not None and os.path.exists(tmpfile):
            os.unlink(tmpfile)

        return True, tags, silent


class SerpentariumJumpToDefinition(sublime_plugin.TextCommand, Serpentarium):
    """
    Jump to word under cursor definition
    """
    def is_visible(self):
        """
        Is command visible?
        """
        # skip non-python files
        return self.view.match_selector(0, 'source.python')

    def is_enabled(self):
        """
        Is command active?
        """
        # check ctags is exists
        ctags_file = self.get_ctags_file(self.view.file_name())
        if ctags_file is None or not os.path.exists(ctags_file):
            return False
        return True

    def run(self, edit):
        """
        Run command - let's jump to word under cursor definition!
        """
        # skip non-python files
        if not self.view.match_selector(0, 'source.python'):
            return

        # check ctags is exists
        ctags_file = self.get_ctags_file(self.view.file_name())
        if ctags_file is None or not os.path.exists(ctags_file):
            return []

        # check ctags is prepared - prepare if needed
        global ctags
        if ctags is None:
            ctags = CTags(tags_file=ctags_file)

        symbol = self.view.substr(self.view.word(self.view.sel()[0]))

        definitions = ctags.get_definitions(symbol, self.view)
        if not definitions:
            return sublime.status_message("Can't find '%s'" % symbol)

        def select_definition(choose):
            if choose == -1:
                return

            row, col = self.view.rowcol(self.view.sel()[0].begin())
            history.append((self.view.file_name(), row + 1, col + 1))

            self.goto_file(
                view=self.view,
                filename=definitions[choose][1],
                row=definitions[choose][2],
                col=0
            )

        instant_jump = settings.get('instant_jump_to_definition', False)
        if len(definitions) == 1 and instant_jump:
            select_definition(0)
        else:
            self.view.window().show_quick_panel(
                [[d[0], "%d: %s" % (d[2], d[1])] for d in definitions],
                select_definition
            )


class SerpentariumJumpBack(sublime_plugin.TextCommand, Serpentarium):
    """
    Jump back from definition
    """
    def is_visible(self):
        """
        Is command visible?
        """
        # skip non-python files
        return self.view.match_selector(0, 'source.python')

    def is_enabled(self):
        """
        Is command active?
        """
        return True if history else False

    def run(self, edit):
        """
        Run command - jump back
        """
        if not history:
            return sublime.status_message("Jump history is empty")

        filename, row, col = history.pop()
        self.goto_file(view=self.view, filename=filename, row=row, col=col)


class SerpentariumBackground(sublime_plugin.EventListener, Serpentarium):
    """
    Sublime event actions
    """
    def on_post_save(self, view):
        """
        Rebuild ctags and cscope on python source file save
        """
        # skip non-python files
        if not view.match_selector(0, 'source.python'):
            return

        # TODO: respect 'XXX_rebuild_on_save' setting
        view.window().run_command('serpentarium_rebuild', {'silent': True})

    def on_query_completions(self, view, prefix, locations):
        """
        Extend autocomplete results with ctags
        """
        # skip non-python files
        if not view.match_selector(0, 'source.python'):
            return []

        # check ctags is exists
        ctags_file = self.get_ctags_file(view.file_name())
        if ctags_file is None or not os.path.exists(ctags_file):
            return []

        # check ctags is prepared - prepare if needed
        global ctags
        if ctags is None:
            ctags = CTags(tags_file=ctags_file)

        # do autocomplete work
        return ctags.autocomplete(view, prefix, locations)
