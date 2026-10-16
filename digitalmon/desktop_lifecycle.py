"""Loopback-only single-instance wakeup; no model credentials cross this channel."""
import socket
import threading

class InstanceBridge:
    REQUEST=b'DIGITALMONSTER_SHOW_V1\n'
    ACK=b'DIGITALMONSTER_SHOW_ACK\n'

    def __init__(self,on_message,port):
        self.socket=socket.socket()
        try:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            self.socket.bind(('127.0.0.1',port))
            self.socket.listen(4)
            self.socket.settimeout(.3)
        except BaseException:
            self.socket.close()
            raise
        self.port=self.socket.getsockname()[1]
        self.callback=on_message
        self.closed=threading.Event()
        self.thread=threading.Thread(target=self.listen,daemon=True)
        self.thread.start()

    def listen(self):
        while not self.closed.is_set():
            try:
                connection,_=self.socket.accept()
                with connection:
                    connection.settimeout(1)
                    if connection.recv(128)==self.REQUEST:
                        self.callback('show')
                        connection.sendall(self.ACK)
            except socket.timeout:continue
            except OSError:
                if self.closed.is_set():return

    @classmethod
    def notify(cls,port):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=1) as connection:
                connection.sendall(cls.REQUEST)
                return connection.recv(128)==cls.ACK
        except OSError:return False

    def close(self):
        self.closed.set()
        self.socket.close()
        self.thread.join(timeout=2)
