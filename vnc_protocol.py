import struct
import zlib
import json
from enum import IntEnum

class MessageType(IntEnum):
    # Agent -> Server
    AGENT_CONNECT = 1
    SCREEN_UPDATE = 2
    AGENT_DISCONNECT = 3
    
    # Controller -> Server  
    CONTROLLER_CONNECT = 10
    MOUSE_MOVE = 11
    MOUSE_CLICK = 12
    KEY_PRESS = 13
    CONTROLLER_DISCONNECT = 14
    
    # Server -> Agent/Controller
    COMMAND_MOUSE = 20
    COMMAND_KEY = 21
    SCREEN_DATA = 22
    CONNECTION_INFO = 23
    ERROR = 99

class VNCProtocol:
    @staticmethod
    def pack_message(msg_type, data=b''):
        """Impacchetta un messaggio con header: [tipo:4][lunghezza:4][dati]"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, dict):
            data = json.dumps(data).encode('utf-8')
        
        header = struct.pack('>II', int(msg_type), len(data))
        return header + data
    
    @staticmethod
    def unpack_message(data):
        """Spacchetta un messaggio dal buffer"""
        if len(data) < 8:
            return None, None, data
        
        msg_type, length = struct.unpack('>II', data[:8])
        
        if len(data) < 8 + length:
            return None, None, data
        
        message_data = data[8:8+length]
        remaining = data[8+length:]
        
        return MessageType(msg_type), message_data, remaining
    
    @staticmethod
    def compress_screen_data(image_data):
        """Comprimi i dati dello schermo"""
        return zlib.compress(image_data, level=6)
    
    @staticmethod
    def decompress_screen_data(compressed_data):
        """Decomprimi i dati dello schermo"""
        return zlib.decompress(compressed_data) 