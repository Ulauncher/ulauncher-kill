import os
import logging
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')

from gi.repository import Notify
from itertools import islice
from subprocess import Popen, PIPE, check_call, CalledProcessError
from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionSmallResultItem import ExtensionSmallResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction


logger = logging.getLogger(__name__)
ext_icon = 'images/icon.png'
exec_icon = 'images/executable.png'
dead_icon = 'images/dead.png'


class ProcessKillerExtension(Extension):

    def __init__(self):
        super(ProcessKillerExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

    def show_notification(self, title, text=None, icon=ext_icon):
        logger.debug('Show notification: %s' % text)
        Notify.init("KillerExtension")
        Notify.Notification.new(title, text, icon).show()


class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        return RenderResultListAction(list(islice(self.generate_results(event), 15)))

    def generate_results(self, event):
        for (pid, cpu, cmd) in get_process_list():
            name = '%s %%CPU %s' % (cpu, cmd) if cpu > 1 else cmd
            on_enter = {'alt_enter': False, 'pid': pid, 'cmd': cmd}
            on_alt_enter = on_enter.copy()
            on_alt_enter['alt_enter'] = True
            if event.get_argument():
                if event.get_argument() in cmd:
                    yield ExtensionSmallResultItem(icon=exec_icon,
                                                   name=name,
                                                   on_enter=ExtensionCustomAction(on_enter),
                                                   on_alt_enter=ExtensionCustomAction(on_alt_enter, keep_app_open=True))
            else:
                yield ExtensionSmallResultItem(icon=exec_icon,
                                               name=name,
                                               on_enter=ExtensionCustomAction(on_enter),
                                               on_alt_enter=ExtensionCustomAction(on_alt_enter, keep_app_open=True))


class ItemEnterEventListener(EventListener):

    def kill(self, extension, pid, signal):
        cmd = ['kill', '-s', signal, str(pid)]
        logger.info(' '.join(cmd))

        try:
            check_call(cmd) == 0
            extension.show_notification("Done", "It's dead now", icon=dead_icon)
        except CalledProcessError:
            extension.show_notification("Sorry", "I couldn't do that :(")
        except Exception:
            extension.show_notification("Error", "Check the logs")
            raise

    def show_signal_options(self, data):
        result_items = []
        options = [('TERM', '15 TERM (default)'), ('KILL', '9 KILL'), ('HUP', '1 HUP')]
        for sig, name in options:
            on_enter = data.copy()
            on_enter['alt_enter'] = False
            on_enter['signal'] = sig
            result_items.append(ExtensionSmallResultItem(icon=dead_icon,
                                                         name=name,
                                                         highlightable=False,
                                                         on_enter=ExtensionCustomAction(on_enter)))
        return RenderResultListAction(result_items)

    def on_event(self, event, extension):
        data = event.get_data()
        if data['alt_enter']:
            return self.show_signal_options(data)
        else:
            self.kill(extension, data['pid'], data.get('signal', 'TERM'))


def get_process_list():
    """
    Returns a list of tuples (PID, %CPU, COMMAND)
    """
    env = os.environ.copy()
    env['COLUMNS'] = '200'
    process = Popen(['top', '-bn1', '-cu', os.getenv('USER')], stdout=PIPE, env=env)
    out = process.communicate()[0]
    for line in out.split('\n'):
        col = line.split()
        try:
            int(col[0])
        except (ValueError, IndexError):
            # not a number
            continue

        pid = col[0]
        cpu = float(col[8])
        cmd = ' '.join(col[11:])
        if 'top -bn' in cmd:
            continue

        yield (pid, cpu, cmd)


if __name__ == '__main__':
    ProcessKillerExtension().run()
