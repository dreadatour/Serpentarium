# -*- coding: utf-8 -*-
import os
import json
import tempfile
import functools
import threading
import subprocess

import sublime
import sublime_plugin

settings = sublime.load_settings("Serpentarium.sublime-settings")


def threaded(finish=None, msg="Thread already running"):
    """
    This decorator is stealed from Sublime Text 2 'CTags' plugin ;)
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

        if not config_file:
            if not os.path.isdir(path):
                path = os.path.dirname(path)
            config_file = os.path.join(path, self.get_config_filename)

            default_config = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "Serpentarium.default-config"
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

    def build_is_done(self, finished=False, tmpfile=None, silent=False):
        """
        Build tags os over - cleanup
        """
        if tmpfile is not None and os.path.exists(tmpfile):
            os.unlink(tmpfile)

        if not finished:
            sublime.status_message(
                'Tags NOT rebuilded! See console for more information.'
            )
        elif not silent:
            sublime.status_message('Tags rebuilded')

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
            cmd = "%s -L '%s' -f '%s'" % (ctags['cmd'], tmpfile, ctags['out'])
            p = subprocess.Popen(cmd, shell=1, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            ret = p.wait()
            if ret:
                raise EnvironmentError((cmd, ret, p.stdout.read()))

        return True, tmpfile, silent


class SerpentariumJumpToDefinition(sublime_plugin.TextCommand, Serpentarium):
    """
    Jump to tag under cursor definition
    """
    pass


class SerpentariumBackground(sublime_plugin.EventListener, Serpentarium):
    """
    Sublime event actions
    """
    def on_post_save(self, view):
        """
        Rebuild ctags and cscope on save if needed
        """
        # TODO: respect 'XXX_rebuild_on_save' setting
        view.window().run_command('serpentarium_rebuild', {'silent': True})

    def on_query_completions(self, view, prefix, locations):
        """
        Autocomplete
        Example: https://gist.github.com/1825401
        """
        results = []

        ctags_file = self.get_ctags_file(view.file_name())
        if ctags_file is None or not os.path.exists(ctags_file):
            return results

        f = os.popen("grep -i '^%s' '%s' | awk '{print $1}'" % (prefix,
                                                                ctags_file))
        for line in f.readlines():
            results.append([line.strip()])

        results = [(i, i) for sublist in results for i in sublist]  # flatten
        results = list(set(results))  # make unique
        results.sort()  # sort

        return results
