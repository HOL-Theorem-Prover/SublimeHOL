from __future__ import absolute_import, unicode_literals, print_function, division

import os
import os.path
import sys
import json
import sublime
import sublime_plugin

SUBLIMEHOL_DIR = None
SUBLIMEHOL_USER_DIR = None

def plugin_loaded():
    global SUBLIMEHOL_DIR
    global SUBLIMEHOL_USER_DIR
    SUBLIMEHOL_DIR = "Packages/HOL"
    SUBLIMEHOL_USER_DIR = os.path.join(sublime.packages_path(), "User", "HOL")

PY2 = False
if sys.version_info[0] == 2:
    SUBLIMEHOL_DIR = os.getcwdu()
    SUBLIMEHOL_USER_DIR = os.path.join(sublime.packages_path(), "User", "HOL")
    PY2 = True

# yes, CommandCommmand :) 
class HolRunExistingWindowCommandCommand(sublime_plugin.WindowCommand):
    def run(self, id, file):
        """Find and run existing command with id in specified file. 
        SUBLIMEHOL_USER_DIR is consulted first, and then SUBLIMEHOL_DIR""" 
        for prefix in (SUBLIMEHOL_USER_DIR, SUBLIMEHOL_DIR):
            path = os.path.join(prefix, file)
            json_cmd = self._find_cmd(id, path)
            if json_cmd:
                break
        if not json_cmd:
            return
        args = json_cmd["args"] if "args" in json_cmd else None
        self.window.run_command(json_cmd["command"], args)
    
    def _find_cmd(self, id, file):
        return self._find_cmd_in_file(id, file)
                
    def _find_cmd_in_file(self, id, file):
        try:
            if PY2 or os.path.isfile(file):
                with open(file) as f:
                    bytes = f.read()
            else:
                bytes = sublime.load_resource(file)
        except (IOError, ValueError):
            return None
        else:
            data = json.loads(bytes)
            return self._find_cmd_in_json(id, data)

    def _find_cmd_in_json(self, id, json_object):
        if isinstance(json_object, list):
            for elem in json_object:
                cmd = self._find_cmd_in_json(id, elem)
                if cmd:
                    return cmd
        elif isinstance(json_object, dict):
            if "id" in json_object and json_object["id"] == id:
                return json_object
            elif "children" in json_object:
                return self._find_cmd_in_json(id, json_object["children"])
        return None