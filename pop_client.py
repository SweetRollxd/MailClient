import base64
import socket
import ssl
import traceback
import getpass
import email
from email import header as email_header
import quopri

from logger import FileLogger

log_filename = "pop_3.log"
# host = 'mail2.nstu.ru'
# host = 'smtp.freesmtpservers.com'
host = 'pop.yandex.ru'
port = 995
bufsize = 1024

"""
Разработайте клиентское приложение для отправки текстовых сообщений по протоколу SMTP с учетом следующих требований:
    1. все команды и данные должен вводить пользователь (адреса получателя и отправителя, текст сообщения);  
    2. подключение к почтовому серверу реализовать на основе сокетов;
    3. приложение должно формировать строки команд в соответствии с протоколом SMTP, выводить их на экран и 
        отправлять на сервер. Ответы сервера также должны выводиться на экран. 
    4. весь процесс почтовой сессии должен сохраняться в файле журнала smtp_Х.log
"""


class POPClientException(Exception):
    """
    Собственное исключение, чтобы вызывать его при ответах сервера об ошибке
    """
    pass


class POPClient:
    """
    Класс SMTP клиента.
    Атрибуты класса:
    __logfile - объект класса FileLogger для логирования сообщений между клиентом и сервером;
    server_host - адрес SMTP сервера;
    server_port - порт SMTP сервера;
    login - логин пользователя отправителя;
    password - его пароль
    client_sock - сокет клиента
    use_tls - признак использования шифрования
    Двойное подчеркивание __ означает приватный атрибут или метод
    """
    __logfile = FileLogger(log_filename)
    messages_dir = '.msg/'

    def __init__(self, server_host, server_port, login, password):
        """
        Конструктор класса. Инициализирует объект класса при вызове SMTPClient() c переданными параметрами

        :param server_host: адрес сервера
        :param server_port: порт сервера
        :param login: логин пользователя
        :param password: пароль
        """
        self.server_host = server_host
        self.server_port = server_port
        self.login = login
        self.password = password
        self.use_tls = True if self.server_port == 995 else False

    def __create_socket_connection(self):
        """
        Создание сокета и подключение к серверу
        """
        self.__client_sock = socket.socket()
        self.__client_sock.settimeout(10)
        print("Creating socket connection")
        self.__client_sock.connect((self.server_host, self.server_port))
        if self.use_tls:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            # используем временный сокет, закрыть обычный сокет, так как он больше не нужен
            tmp_sock = self.__client_sock
            self.__client_sock = ssl_context.wrap_socket(sock=self.__client_sock, server_hostname=host)
            tmp_sock.close()

        self.__logfile.write_log(f"Successfully connected to {self.server_host}:{self.server_port}")
        # получаем ответ от сервера о подключении
        server_response = self.__client_sock.recv(1024).decode('utf-8')
        server_log = f"Server: {server_response}"
        self.__logfile.write_log(server_log)

        # использовать шифрование или нет определяется по порту
        self.use_tls = True if self.server_port == 995 else False

    def __send(self, text):
        client_log = f"Client: {text}"
        self.__logfile.write_log(client_log)
        self.__client_sock.send((text + "\r\n").encode())

    def __recv(self):
        server_response = self.__client_sock.recv(bufsize).decode('utf-8')
        server_log = f"Server: {server_response}"
        self.__logfile.write_log(server_log.rstrip())
        return server_response

    def __send_cmd(self, command, no_response=False):
        """
        Отправить команду на сервер

        :param command: команда в виде строки
        :param no_response: признак "не ждать ответа от сервера"
        :return: ответ от сервера
        """
        self.__send(command)
        if no_response:
            # если "не ждать ответа", то выходим из метода
            return

        else:
            # иначе получаем ответ от сервера
            server_response = self.__recv()
            status_code, msg = server_response.split(' ', 1)

            if status_code != '+OK':
                raise POPClientException(
                    f"Error while sending command {command}.\nResponse from server: {server_response}")
            return status_code, msg

    def save_message_to_file(self, msg_id, msg_data):
        with open(self.messages_dir + msg_id, 'w') as file:
            file.write(msg_data)

    def read_message_from_file(self, msg_id):
        message_file = open(self.messages_dir + msg_id, 'r')
        email_msg = email.message_from_file(message_file)
        msg_data = {}
        for key in ('from', 'to', 'subject', 'date'):
            if key == 'subject':
                header, encoding = email_header.decode_header(email_msg[key])[0]
                if encoding:
                    msg_data[key] = header.decode(encoding)
                else:
                    msg_data[key] = email_msg[key]
            else:
                msg_data[key] = email_msg[key]

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
        print(msg_data)

    def retrieve_message(self, msg_id, msg_size):
        msg_info = self.__send_cmd(f"RETR {msg_id}")
        size_readed = 0
        msg_string = ''
        self.__logfile.change_active_state(False)
        # while size_readed < msg_size:
        global_message_id = ''
        while True:
            data = self.__recv()
            if data == '.\r\n':
                if size_readed != msg_size:
                    self.__logfile.write_log(f"Unexpected end of message. Message ID: {msg_id}, message size: {msg_size}, readed: {size_readed}", "WARNING")
                    # raise POPClientException()

                break
            elif data[:10].lower() == 'message-id':
                global_message_id = data.split(':', 1)[1].strip(' <>\r\n')
            # elif not data[0].isspace() and ':' in data:
            #     tag, value = data.split(':', 1)
            #     if tag in ('From', 'To', 'Subject', 'Date'):
            #         msg_data[tag.lower()] = value.strip()
            msg_string += data
            size_readed += len(data)
        self.__logfile.change_active_state(True)

        self.save_message_to_file(global_message_id, msg_string)

        return global_message_id

    def get_messages(self):
        try:
            # создаем соединение и здороваемся
            self.__create_socket_connection()

            self.__send_cmd(f"USER {self.login}")

            self.__logfile.change_active_state(False)
            self.__send_cmd(f"PASS {self.password}")
            self.__logfile.change_active_state(True)

            inbox_info = self.__send_cmd("LIST")
            msg_count, total_size = inbox_info[1].split(' ')
            print(f"Msg count: {msg_count}, total size: {total_size}")

            msg_list = []
            # for i in range(1, int(msg_count) + 1):
            while True:
                msg_info = self.__recv()
                if msg_info == '.\r\n':
                    break
                msg_info = msg_info.split(' ')
                msg_list.append({'id': int(msg_info[0]), 'size': int(msg_info[1].rstrip())})
            # self.__recv()
            # self.__client_sock.recv(bufsize).decode('utf-8')
            print(f"Msg list: {msg_list}")

            for msg in msg_list:
                self.retrieve_message(msg['id'], msg['size'])
                self.__send_cmd(f"DELE {msg['id']}")

            self.__send_cmd("QUIT", no_response=True)

            self.close()
            return 0
        except POPClientException as e:
            self.__logfile.write_log(f"POPClientException: {e}", msg_type="ERROR")
            return 1
        except TimeoutError:
            self.__logfile.write_log("POP3 command timeout", msg_type="ERROR")
            return 1
        except Exception as e:
            self.__logfile.write_log(f"Unexpected exception: {e}", msg_type="ERROR")
            print(traceback.format_exc())
            self.close()
            raise
            # exit()

    def close(self):
        """
        Метод закрытия соединения и файлов
        """
        print("Connection closed")
        self.__logfile.write_log("Connection closed\n___________________\n\n\n")
        self.__client_sock.close()
        self.__logfile.close()


if __name__ == "__main__":
    print(f"Welcome to POP3 Client!\nYou are going to connect to this POP3 server: {host}:{port}")
    # считываем логин и пароль пользователя
    login = input("Enter login from the server: ")
    password = getpass.getpass()
    # создаем экземпляр класса
    client = POPClient(host, port, login, password)
    client.get_messages()

    client.read_message_from_file('4849151669057440@mail.yandex.ru')
