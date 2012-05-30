#!/usr/bin/python
import cliapp
import egt

class EgtApp(cliapp.Application):
    def cmd_scan(self, args):
        e = egt.Egt()
        e.scan()

    def cmd_list(self, args):
        e = egt.Egt()
        for k, v in e.state.projects.iteritems():
            print "%s\t%s" % (v.name, v.path)

    def cmd_term(self, args):
        e = egt.Egt()
        for name in args:
            proj = e.project_by_name(name)
            proj.spawn_terminal()

    def cmd_work(self, args):
        e = egt.Egt()
        for name in args:
            proj = e.project_by_name(name)
            proj.spawn_terminal(with_editor=True)

if __name__ == '__main__':
    EgtApp().run()

