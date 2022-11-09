from datetime import datetime as dt


def current_time():
    return dt.now().strftime('%Y-%m-%d %H:%M:%S')


class FileLogger:
    def __init__(self, filename):
        self.logfile = open(filename, 'a')
        self.active = True

    def change_active_state(self, state):
        if state is True:
            self.active = True
            self.write_log("Logging was enabled.")
        else:
            self.write_log("Disable logging...")
            self.active = False

    def write_log(self, message, msg_type="INFO"):
        log_string = f'{current_time()} [{msg_type}]: {message}\n'
        print(log_string)
        if self.active:
            self.logfile.write(log_string)

    def close(self):
        self.logfile.close()
