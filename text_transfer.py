from __future__ import absolute_import, unicode_literals, print_function, division

import re
import sublime_plugin
import sublime
from collections import defaultdict
import tempfile
import binascii

try:
    from .sublimehol import manager, SETTINGS_FILE
except (ImportError, ValueError):
    from sublimehol import manager, SETTINGS_FILE


def default_sender(repl, text, view=None, repl_view=None):
    if repl.apiv2:
        repl.write(text, location=repl_view.view.size() - len(text))
    else:
        repl.write(text)

    if view is None or not sublime.load_settings(SETTINGS_FILE).get('focus_view_on_transfer'):
        return
    active_window = sublime.active_window()
    active_view = active_window.active_view()
    target_view = repl_view.view
    if target_view == active_view:
        return  #
    active_group = sublime.active_window().active_group()
    if target_view in active_window.views_in_group(active_group):
        return  # same group, dont switch
    active_window.focus_view(target_view)
    active_window.focus_view(view)


"""Senders is a dict of functions used to transfer text to repl as a repl
   specific load_file action"""
SENDERS = defaultdict(lambda: default_sender)


def sender(external_id,):
    def wrap(func):
        SENDERS[external_id] = func
    return wrap

class HolReplViewWrite(sublime_plugin.TextCommand):
    def run(self, edit, external_id, text):
        for rv in manager.find_repl(external_id):
            rv.append_input_text(text)
            break  # send to first repl found
        else:
            sublime.error_message("Cannot find REPL for '{0}'".format(external_id))


class HolReplSend(sublime_plugin.TextCommand):
    def run(self, edit, external_id, text, with_auto_postfix=True):
        for rv in manager.find_repl(external_id):
            if with_auto_postfix:
                text += rv.repl.cmd_postfix
            if sublime.load_settings(SETTINGS_FILE).get('show_transferred_text'):
                rv.append_input_text(text)
                rv.adjust_end()
            SENDERS[external_id](rv.repl, text, self.view, rv)
            break
        else:
            sublime.error_message("Cannot find REPL for '{}'".format(external_id))


class HolReplTransferCurrent(sublime_plugin.TextCommand):
    def run(self, edit, scope="selection", action="send", prepend="", append=""):
        text = ""
        if scope == "selection":
            text = self.selected_text()
        elif scope == "lines":
            text = self.selected_lines()
        elif scope == "function":
            text = self.selected_functions()
        elif scope == "file":
            text = self.selected_file()
        text = prepend + text + append
        cmd = "hol_repl_" + action
        self.view.window().run_command(cmd, {"external_id": self.repl_external_id(), "text": text})

    def repl_external_id(self):
        return self.view.scope_name(0).split(" ")[0].split(".", 1)[1]

    def selected_text(self):
        v = self.view
        parts = [v.substr(region) for region in v.sel()]
        return "".join(parts)

    def selected_lines(self):
        v = self.view
        parts = []
        for sel in v.sel():
            for line in v.lines(sel):
                parts.append(v.substr(line))
        return "\n".join(parts)

    def selected_file(self):
        v = self.view
        return v.substr(sublime.Region(0, v.size()))
