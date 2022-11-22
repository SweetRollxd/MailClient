import os

from PyQt5.uic import loadUi
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLineEdit
import sys
import email
from email import header as email_header
import datetime

import smtp_client
import smtp_client as smtp
import pop_client as pop


def read_message_from_file(path, without_body=False):
    message_file = open(path, 'r')
    email_msg = email.message_from_file(message_file)
    msg_data = {}
    for key in ('from', 'to', 'subject', 'date'):
        if key == 'subject':
            header, encoding = email_header.decode_header(email_msg[key])[0]
            if encoding:
                msg_data[key] = header.decode(encoding)
            else:
                msg_data[key] = email_msg[key]
        # elif key == 'date':
        #     msg_data[key] = datetime.datetime.strptime(email_msg[key].rstrip(), '%a, %d %b %Y %H:%M:%S %z')
        else:
            msg_data[key] = email_msg[key]

    if not without_body:
        msg_body = ''
        if email_msg.is_multipart():
            for msg in email_msg.walk():
                if msg.get_content_type() == 'text/plain':
                    email_msg = msg
                    break

        if email_msg['Content-Transfer-Encoding'] in ('base64', 'quoted-printable'):
            msg_body = email_msg.get_payload(decode=True).decode('utf-8')
        else:
            msg_body = msg_body = email_msg.get_payload()

        msg_data['body'] = msg_body
    return msg_data


class ClientWindow(QMainWindow):
    settings = QtCore.QSettings("SIT Brigade 3", "Mail Client")
    msg_dir = ".msg/"
    # smtp_host = settings.va
    # smtp_port = ''
    # pop_host = ''
    # pop_port = ''
    # login = ''
    # password = ''

    def __init__(self):
        super(ClientWindow, self).__init__()
        loadUi("design/main.ui", self)
        self.msgTable.setColumnWidth(0, 250)
        self.msgTable.setColumnWidth(1, 400)
        self.msgTable.setColumnWidth(2, 150)
        self.btn_settings.clicked.connect(self.settings_open)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_send.clicked.connect(self.msg_form)
        self.btn_delete.clicked.connect(self.msg_delete)
        self.msgTable.doubleClicked.connect(self.msg_open)

        self.msg_info_list = []

        print(self.settings.value('smtp_host'))

    def settings_open(self):
        self.settings_window = SettingsWindow()
        # self.settings.saveClicked.connect(self.update_settings)
        self.settings_window.show()
        
    def refresh(self):
        self.download_messages()
        self.msgTable.clear()
        self.get_messages()

    def msg_open(self):
        # QtWidgets.QTableWidget.click
        local_id = self.msgTable.currentRow()
        # msg_file =
        self.message_inspector = MessageInspector(self.msg_dir + self.msg_info_list[local_id]['msg_file'])
        self.message_inspector.show()
        # print(msg_file)

    def msg_form(self):
        self.message_form = MessageForm()
        self.message_form.show()

    def msg_delete(self):
        local_id = self.msgTable.currentRow()
        os.remove(self.msg_dir + self.msg_info_list[local_id]['msg_file'])
        self.refresh()

    def get_messages(self):
        msg_list = os.listdir(self.msg_dir)
        if not msg_list:
            return
        self.msgTable.setRowCount(len(msg_list))

        self.msg_info_list = []
        for row, file in enumerate(msg_list):
            print(file)
            msg_data = read_message_from_file(self.msg_dir + file, without_body=True)
            self.msgTable.setItem(row, 0, QtWidgets.QTableWidgetItem(msg_data['from']))
            self.msgTable.setItem(row, 1, QtWidgets.QTableWidgetItem(msg_data['subject']))
            self.msgTable.setItem(row, 2, QtWidgets.QTableWidgetItem(msg_data['date']))
            msg_data['local_id'] = row
            msg_data['msg_file'] = file
            self.msg_info_list.append(msg_data)

    def download_messages(self):
        pop_client = pop.POPClient(server_host=self.settings.value('pop_host'),
                                   server_port=int(self.settings.value('pop_port')),
                                   login=self.settings.value('login'),
                                   password=self.settings.value('password'))
        pop_client.get_messages()
        # pop_client.close()
        return


class SettingsWindow(QWidget):
    # saveClicked = QtCore.pyqtSignal(dict)
    settings = QtCore.QSettings("SIT Brigade 3", "Mail Client")

    def __init__(self):
        super(SettingsWindow, self).__init__()
        loadUi("design/settings.ui", self)
        self.password.setEchoMode(QLineEdit.Password)
        self.btn_save.clicked.connect(self.save)
        self.btn_cancel.clicked.connect(self.cancel)
        self.smtp_host.setText(self.settings.value('smtp_host'))
        self.smtp_port.setText(self.settings.value('smtp_port'))
        self.pop_host.setText(self.settings.value('pop_host'))
        self.pop_port.setText(self.settings.value('pop_port'))
        self.email_address.setText(self.settings.value('login'))
        self.password.setText(self.settings.value('password'))

    def save(self):
        # settings = {
        #     'smtp_host': self.smtp_host.text(),
        #     'smtp_port': self.smtp_port.text(),
        #     'pop_host': self.pop_host.text(),
        #     'pop_port': self.pop_port.text(),
        #     'login': self.email_address.text(),
        #     'password': self.password.text()
        # }
        self.settings.setValue('smtp_host', self.smtp_host.text())
        self.settings.setValue('smtp_port', self.smtp_port.text())
        self.settings.setValue('pop_host', self.pop_host.text())
        self.settings.setValue('pop_port', self.pop_port.text())
        self.settings.setValue('login', self.email_address.text())
        self.settings.setValue('password', self.password.text())
        # self.saveClicked.emit(settings)
        self.close()

    def cancel(self):
        self.close()


class MessageInspector(QWidget):
    def __init__(self, msg_file):
        super(MessageInspector, self).__init__()
        loadUi("design/message_inspector.ui", self)
        msg_data = read_message_from_file(msg_file)
        self.txtbox_from.setText(msg_data['from'])
        self.txtbox_to.setText(msg_data['to'])
        self.txtbox_subj.setText(msg_data['subject'])
        self.txtbox_body.setText(msg_data['body'])


class MessageForm(QWidget):
    settings = QtCore.QSettings("SIT Brigade 3", "Mail Client")

    def __init__(self):
        super(MessageForm, self).__init__()
        loadUi("design/message_form.ui", self)
        self.btn_send.clicked.connect(self.send_message)

    def send_message(self):
        client = smtp_client.SMTPClient(self.settings.value('smtp_host'),
                                        int(self.settings.value('smtp_port')),
                                        self.settings.value('login'),
                                        self.settings.value('password'))
        print(self.txtbox_to.text())
        res = client.send_letter(self.txtbox_from.text(),
                                 self.txtbox_to.text(),
                                 self.txtbox_subj.text(),
                                 self.txtbox_body.toPlainText())
        if res == 0:
            self.close()

def application():
    app = QApplication(sys.argv)
    window = ClientWindow()
    window.show()
    if not window.settings.value('login'):
        window.settings_open()
    window.get_messages()


    window.refresh()
    sys.exit(app.exec_())


if __name__ == "__main__":
    application()
