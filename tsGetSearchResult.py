#!/usr/bin/env python
# coding=utf-8

import sublime
import sublime_plugin

_caption = {
    0: 'search regex',
    sublime.IGNORECASE: 'search regex|ignorecase',
    sublime.LITERAL: 'search literal',
    sublime.IGNORECASE|sublime.LITERAL: 'search literal|ignorecase'
}

def _setting_get(key):
    return sublime.load_settings('stGetSearchResult.sublime-settings').get(key)

class CommandProcessorBase:
    def __init__(self, parent, name):
        self.name = name
        self.parent = parent

    def process(self):
        pass

    def highlight(self):
        pass


class CommandCopyLines(CommandProcessorBase):
    def __init__(self, parent):
        CommandProcessorBase.__init__(self, parent, '< copy lines >')

    def process(self):
        text = ''
        for line in self.parent.result_lines:
            text += '%s\n' % (line)
        if _setting_get('copy_to_clipboard'):
            sublime.set_clipboard(text)
        if _setting_get('copy_to_new_window'):
            newview = self.parent.view.window().new_file()
            newview.run_command("insert_snippet", {"contents": text})


class CommandCopyMatches(CommandProcessorBase):
    def __init__(self, parent):
        CommandProcessorBase.__init__(self, parent, '< copy matches >')

    def process(self):
        text = ''
        for line in self.parent.result_words:
            text += '%s\n' % (line)
        if _setting_get('copy_to_clipboard'):
            sublime.set_clipboard(text)
        if _setting_get('copy_to_new_window'):
            newview = self.parent.view.window().new_file()
            newview.run_command("insert_snippet", {"contents": text})


class GetSearchResult(sublime_plugin.TextCommand):

    def run(self, edit, **args):
        self.edit = edit
        self.search_flag = 0
        if 'LITERAL' in args:
            self.search_flag = self.search_flag|sublime.LITERAL
        if 'IGNORECASE' in args:
            self.search_flag = self.search_flag|sublime.IGNORECASE
        self.msg = StatusMessage(self.view)
        self.result = Result(self, CommandCopyLines, CommandCopyMatches)
        initstr = self.view.substr(self.view.sel()[0])
        try:
            self.input_panel = self.view.window().show_input_panel(
                _caption[self.search_flag],
                initstr if _setting_get('init_input_panel') else '',
                self.on_input_panel_done,
                self.on_input_panel_change,
                self.on_input_panel_cancel
            )
        except Exception as e:
            print(e)
        finally:
            self.msg.clear()

    def on_input_panel_done(self, pattern):
        self.msg.clear()
        if not self.result.doSearch(self.view, pattern, self.search_flag):
            self.view.window().show_input_panel(
                _caption[self.search_flag],
                pattern,
                self.on_input_panel_done,
                self.on_input_panel_change,
                self.on_input_panel_cancel
            )
            msg = '"%s" not found' % pattern
            self.msg.message(msg)
            sublime.error_message(msg)
            return

        self.msg.message("Found %d" % self.result.count)
        self.view.window().show_quick_panel(
            items = self.result.panelItems,
            on_select = self.on_quick_panle_done,
            selected_index = -1,
            on_highlight = self.on_quick_panle_highlighted,
        )

    def on_input_panel_change(self, input):
        pass

    def on_input_panel_cancel(self):
        if hasattr(self, 'msg') and self.msg:
            self.msg.clear()

    def on_quick_panle_done(self, index):
        if index == -1:
            return
        if not self.result.process(index):
            self.view.sel().clear()
            curr_range = self.result.resultRange(index)
            self.view.show(curr_range)
            self.view.sel().add(curr_range)

    def on_quick_panle_highlighted(self, index):
        if not self.result.highlight(index):
            self.view.sel().clear()
            curr_range = self.result.resultRange(index)
            self.view.show(curr_range)
            self.view.sel().add(curr_range)


class StatusMessage:
    def __init__(self, view):
        self.view = view

    def message(self, msg):
        self.view.set_status('search_results_msg', msg)
        sublime.set_timeout(self.clear, 3000)

    def clear(self):
        self.view.set_status('search_results_msg', '')


class Result:
    def __init__(self, parent, *processors):
        self.parent = parent
        self.processors = []
        for processor in processors:
            self.processors.append(processor(self))
        self.panelItems = [p.name for p in self.processors]
        self.success = False

    def doSearch(self, view, pattern, flag):
        self.view = view
        self.pattern = pattern
        self.result_words = []
        self.result_lines = []
        self.result_regions = self.view.find_all(pattern, flag)
        if view.has_non_empty_selection_region():
            self_finding = False
            if len(view.sel()) == 1:
                sel = self.view.substr(view.sel()[0])
                if flag < sublime.IGNORECASE:
                    self_finding = sel == pattern
                else:
                    self_finding = sel.lower() == pattern.lower()
            if not self_finding:
                self.result_regions = [
                    region for region in self.result_regions
                    if view.sel().contains(region)
                ]
        self.count = len(self.result_regions)
        if self.count == 0:
            self.success = False
            return False
        for r in self.result_regions:
            word = self.view.substr(r)
            line = self.view.substr(self.view.line(r))
            self.result_words.append(word)
            self.result_lines.append(line)
        self.panelItems += self.result_lines
        self.success = True
        return True

    def resultRange(self, index):
        return self.result_regions[index - len(self.processors)]

    def process(self, index):
        if index >= len(self.processors):
            return False
        self.processors[index].process()
        return True

    def highlight(self, index):
        if index >= len(self.processors):
            return False
        self.processors[index].highlight()
        return True
