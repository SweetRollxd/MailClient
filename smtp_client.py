import base64
import socket
import ssl
import traceback
import getpass

from logger import FileLogger

log_filename = "smtp_3.log"
host = 'mail2.nstu.ru'
# host = 'smtp.freesmtpservers.com'
port = 587

"""
Разработайте клиентское приложение для отправки текстовых сообщений по протоколу SMTP с учетом следующих требований:
    1. все команды и данные должен вводить пользователь (адреса получателя и отправителя, текст сообщения);  
    2. подключение к почтовому серверу реализовать на основе сокетов;
    3. приложение должно формировать строки команд в соответствии с протоколом SMTP, выводить их на экран и 
        отправлять на сервер. Ответы сервера также должны выводиться на экран. 
    4. весь процесс почтовой сессии должен сохраняться в файле журнала smtp_Х.log
"""


class SMTPClientException(Exception):
    """
    Собственное исключение, чтобы вызывать его при ответах сервера об ошибке
    """
    pass


class SMTPClient:
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

    def __create_socket_connection(self):
        """
        Создание сокета и подключение к серверу
        """
        self.__client_sock = socket.socket()
        self.__client_sock.settimeout(10)

        self.__client_sock.connect((self.server_host, self.server_port))
        self.__logfile.write_log(f"Successfully connected to {self.server_host}:{self.server_port}")
        # получаем ответ от сервера о подключении
        server_response = self.__client_sock.recv(1024).decode('utf-8')
        server_log = f"Server: {server_response}"
        self.__logfile.write_log(server_log)

        # использовать шифрование или нет определяется по порту
        self.use_tls = True if self.server_port == 587 else False

    def __create_ssl_socket(self):
        """
        Заменить обычный сокет на TLS сокет
        """
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        # используем временный сокет, закрыть обычный сокет, так как он больше не нужен
        tmp_sock = self.__client_sock
        self.__client_sock = ssl_context.wrap_socket(sock=self.__client_sock, server_hostname=host)
        tmp_sock.close()

    def __send_cmd(self, command, no_response=False):
        """
        Отправить команду на сервер

        :param command: команда в виде строки
        :param no_response: признак "не ждать ответа от сервера"
        :return: ответ от сервера
        """
        # логируем команду клиента
        client_log = f"Client: {command}"
        self.__logfile.write_log(client_log)
        self.__client_sock.send((command + "\r\n").encode())
        if no_response:
            # если "не ждать ответа", то выходим из метода
            return

        else:
            # иначе получаем ответ от сервера
            server_response = self.__client_sock.recv(1024).decode('utf-8')
            # записываем код ответа от сервера (первые 3 символа)
            status_code = server_response[0:3]

            # if b64decode_response is True:
            #     server_response = base64.b64decode(server_response[4:] + b'==').decode('utf-8')
            # else:
            #     server_response = server_response.decode('utf-8')

            # логируем ответ от сервера
            server_log = f"Server: {server_response}"
            self.__logfile.write_log(server_log)
            # если код ответа от сервера начинается не с 2 (успешно) или 3 (ожидает команды),
            # то выбрасываем исключение об ошибке от сервера
            if status_code[0] not in ('2', '3'):
                raise SMTPClientException(
                    f"Error while sending command {command}.\nStatus code: {status_code}.\nResponse from server: {server_response}")
            return server_response

    def send_letter(self, sender, recipients, subj, msg):
        """
        Метод отправки письма

        :param sender: отправитель
        :param recipients: получатели (список)
        :param subj: тема письма
        :param msg: тело письма
        :return: 0, если письмо успешно отправлено и 1, если произошла ошибка и письимо не было отправлено
        """
        try:
            # создаем соединение и здороваемся
            self.__create_socket_connection()
            self.__send_cmd("EHLO localhost")

            if self.use_tls is True:
                # если используется шифрование, то даем команду на начало шифрования
                self.__send_cmd("STARTTLS")
                # и создаем TLS сокет
                self.__create_ssl_socket()
                # ещё раз здороваемся
                self.__send_cmd("EHLO localhost")

                # авторизуемся
                self.__send_cmd("AUTH LOGIN")
                self.__send_cmd(base64.b64encode(self.login.encode()).decode())

                # отключаем логирование на период передачи пароля
                # TODO: отключить логирование только на момент передачи сообщение клиента о пароле. Ответ от сервера должен логироваться
                self.__logfile.change_active_state(False)
                self.__send_cmd(base64.b64encode(self.password.encode()).decode())
                self.__logfile.change_active_state(True)

            # указываем отправителя
            self.__send_cmd(f"MAIL FROM:{sender}")
            # получателей в цикле передаем каждого отдельной командой
            for recipient in recipients:
                self.__send_cmd(f"RCPT TO:{recipient}")

            # отправляем тело с нужными заголовками
            self.__send_cmd("DATA")
            self.__send_cmd(f"FROM:{sender}\r\n" +
                            f"TO:{', '.join(recipients)}\r\n" +
                            f"SUBJECT:{subj}", no_response=True)
            self.__send_cmd(f"\n{msg}", no_response=True)
            self.__send_cmd(".")
            # закрываем соединение
            self.__send_cmd("QUIT")
            self.__logfile.write_log("Letter was sent successfully!")

            self.close()
            return 0
        except SMTPClientException as e:
            # TODO: обработка различных ответов от сервера об ошибке, чтобы говорить о них пользователю
            self.__logfile.write_log(f"SMTPClientException: {e}", msg_type="ERROR")
            return 1
        except TimeoutError:
            self.__logfile.write_log("SMTP command timeout", msg_type="ERROR")
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
    print(f"Welcome to SMTP Client!\nYou are going to connect to this SMTP server: {host}:{port}")
    # считываем логин и пароль пользователя
    login = input("Enter login from the server: ")
    password = getpass.getpass()
    # создаем экземпляр класса
    client = SMTPClient(host, port, login, password)

    # в бесконечном цикле отправляем письма, запрашивая у пользователя куда их отправлять
    # выход из цикла производится нажатием Ctrl-D или Ctrl-Z
    while True:
        print("You're writing a new letter.\nUse Ctrl-D or Ctrl-Z (Windows) to close SMTP client.")
        try:
            from_address = input("From: ")

            to_addresses = input("To (separated by commas): ")
            # разбиваем введенные адреса получателей на элементы списка, убираем все пробелы
            to_address_list = to_addresses.replace(" ", "").split(',')

            subject = input("Subject: ")

            # просим ввести тело письма
            # завершение письима производится командой EOF
            print("Enter your letter body. To save the message enter 'EOF' line.")
            message = ""
            while True:
                line = input()
                if line == "EOF":
                    break

                # elif line != '' and line[0] == '.':
                #     message += "." + line + "\n"
                # else:
                message += line + "\n"

            # отправляем письмо
            status_code = client.send_letter(sender=from_address,
                                             recipients=to_address_list,
                                             subj=subject,
                                             msg=message)
            if status_code == 0:
                print("Hell yeah! The letter was sent.")
            else:
                print("This is very sad. Letter wasn't sent.")
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print("Unexpected exception caught:", e)
            print("Terminating...")
            exit(code=1)
