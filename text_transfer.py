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
        if scope == "selection":
            lN,cN,text = self.selected_text()
        elif scope == "lines":
            lN,cN,text = self.selected_lines()
        elif scope == "file":
            lN,cN,text = self.selected_file()
        else:
            lN,cN,text = (0,0,"")
        #Delete things off front dependent on type of selection sent
        #TACTIC HANDLING
        if prepend[-2:] == "e(":
            #Get rid of leading whitespace and keep track
            ntext = text.lstrip()
            #Whilst we have leading tactic concatenators
            while (ntext[0:2] in [r'>-',r'>|',r'>>',r'\\']) or (ntext[0:5] in ['THEN1','THENL', 'THEN ']):
                #get rid of them
                if ntext[0:2] in [r'>-',r'>|',r'>>',r'\\']:
                    ntext = ntext[2:]
                if ntext[0:5] in ['THEN1','THENL','THEN ']:
                    ntext = ntext[5:]
                #and any revealed whitespace
                ntext = ntext.lstrip()
            #Record deletion off front
            dL = len(text) - len(ntext)
            #Get rid of trailing whitespace
            ntext = ntext.rstrip()
            #Whilst we have trailing tactic concatenators
            while (ntext[-2:] in [r'>-',r'>|',r'>>',r'\\']) or (ntext[-5:] in ['THEN1','THENL']) or (ntext[-4:] == 'THEN'):
                #get rid of them
                if ntext[-2:] in [r'>-',r'>|',r'>>',r'\\']:
                    ntext = ntext[:-2]
                if ntext[-5:] in ['THEN1','THENL']:
                    ntext = ntext[:-5]
                if ntext[-4:] == 'THEN':
                    ntext = ntext[:-4]
                #and any revealed whitespace
                ntext = ntext.rstrip()
        elif prepend[-2:] == "g(":
            #find goals by either indentifying complete, or half marked terms
            matches = re.findall(r'\‘([^’]*?)\’|`([^`]*?)`',text)
            possible_goals = [t[0] for t in matches] + [t[1] for t in matches]
            if possible_goals == []:
                possible_goals = re.split('\‘|\’|`', text)
            #take the largest possible goal and find how much deleted to get it
            ntext = max(possible_goals,key=len)
            dL    = text.find(ntext)
            #augment prepend and append
            prepend += "‘"
            append = "’" + append
        #OTHER HANDLING
        else:
            dL = 0
            ntext = text
        #handle if front stuff deleted
        if dL > 0:
            #find number of lines and characters deleted
            deleted_text = text[:dL]
            deleted_lines = deleted_text.split('\n')
            nu_lines = len(deleted_lines) - 1
            nu_chars = len(deleted_lines[-1])
            #Adjust line number and character number based on deletion
            if nu_lines > 0:
                lN += nu_lines
                cN  = nu_chars
            else:
                cN -= nu_chars
        #construct location string based on line and character number (accounting for definition syntax)
        if ntext[:10] == "Definition":
            locString = "(*#loc " + str(lN - 1) + " 0 *)\n"
        else:
            locString = "(*#loc " + str(lN) + " " + str(cN) + " *)\n"

        if prepend != "" and ntext == "" and append == "":
            text = locString + prepend
        elif prepend != "" or ntext != "" or append != "":
            text = prepend + locString + ntext + append
        cmd = "hol_repl_" + action
        self.view.window().run_command(cmd, {"external_id": self.repl_external_id(), "text": text})

    def repl_external_id(self):
        return self.view.scope_name(0).split(" ")[0].split(".", 1)[1]

    def selected_text(self):
        v = self.view
        parts = [v.substr(region) for region in v.sel()]
        lN,cN = v.rowcol(min([region.a for region in v.sel()]+[region.b for region in v.sel()]))
        lN += 1
        return (lN,cN,"".join(parts))

    def selected_lines(self):
        v = self.view
        parts = []
        region_pts = []
        for sel in v.sel():
            for line in v.lines(sel):
                parts.append(v.substr(line))
                region_pts.append(line.a)
                region_pts.append(line.b)
        lN,cN = v.rowcol(min(region_pts))
        lN += 1
        return (lN,cN,"\n".join(parts))

    def selected_file(self):
        v = self.view
        return (1,0,v.substr(sublime.Region(0, v.size())))
