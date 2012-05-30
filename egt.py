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
            print v.name, v.path


if __name__ == '__main__':
    EgtApp().run()

